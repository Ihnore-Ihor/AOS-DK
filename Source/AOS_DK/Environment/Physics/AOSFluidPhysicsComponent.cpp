#include "AOSFluidPhysicsComponent.h"

#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "PhysicsEngine/PhysicsSettings.h"

DEFINE_LOG_CATEGORY_STATIC(LogAOSFluid, Log, All);

namespace AOSFluid
{
	// Deep-water dispersion constant used by the analytic spectrum (cm/s^2).
	constexpr float DispersionGravity = 981.0f;
}

UAOSFluidPhysicsComponent::UAOSFluidPhysicsComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	PrimaryComponentTick.TickGroup = TG_PrePhysics;

	// Analytic spectrum matching the level's Gerstner water (amplitudes 10-200 cm, wavelengths 8-140 m, dominant 35 deg).
	WaveHarmonics.Emplace(200.0f, 14000.0f, 35.0f, 0.0f);   // Dominant long wave
	WaveHarmonics.Emplace(80.0f,   6000.0f, 55.0f, 1.5f);   // Mid-range crossing wave
	WaveHarmonics.Emplace(30.0f,   2000.0f, 15.0f, 3.14f);  // Shorter chop
	WaveHarmonics.Emplace(10.0f,    800.0f, 45.0f, 0.7f);   // Capillary/small waves
}

void UAOSFluidPhysicsComponent::OnRegister()
{
	Super::OnRegister();
	RebuildWaveSpectrum();
}

void UAOSFluidPhysicsComponent::BeginPlay()
{
	Super::BeginPlay();
	RebuildWaveSpectrum();
	ApplyMassOverride();

	if (ResponseModel == EAOSFluidResponseModel::Newtonian)
	{
		// Weight comes from the engine (m*g); the component only adds buoyancy, drag and wave forcing.
		if (UPrimitiveComponent* Body = GetDrivenBody())
		{
			Body->SetEnableGravity(true);
		}
	}
	SetComponentTickEnabled(bAutoSimulate);
}

void UAOSFluidPhysicsComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (bAutoSimulate)
	{
		StepFluidPhysics(DeltaTime);
	}
}

#if WITH_EDITOR
void UAOSFluidPhysicsComponent::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);
	RebuildWaveSpectrum();
}
#endif

// ==================================================================================================
// API
// ==================================================================================================
UPrimitiveComponent* UAOSFluidPhysicsComponent::GetDrivenBody() const
{
	if (UPrimitiveComponent* Body = DrivenBody.Get())
	{
		return Body;
	}
	const AActor* Owner = GetOwner();
	return Owner ? Cast<UPrimitiveComponent>(Owner->GetRootComponent()) : nullptr;
}

void UAOSFluidPhysicsComponent::SetDrivenBody(UPrimitiveComponent* NewBody)
{
	DrivenBody = NewBody;
	bWarnedNotSimulating = false;
	if (HasBegunPlay())
	{
		ApplyMassOverride();
	}
}

void UAOSFluidPhysicsComponent::SetAutoSimulate(bool bEnabled)
{
	bAutoSimulate = bEnabled;
	SetComponentTickEnabled(bEnabled);
}

void UAOSFluidPhysicsComponent::SetWaveHarmonics(const TArray<FAOSWaveHarmonic>& NewHarmonics)
{
	WaveHarmonics = NewHarmonics;
	RebuildWaveSpectrum();
}

void UAOSFluidPhysicsComponent::ApplyMassOverride()
{
	UPrimitiveComponent* Body = GetDrivenBody();
	if (Body && MassOverrideKg > 0.f)
	{
		Body->SetMassOverrideInKg(NAME_None, MassOverrideKg, true);
	}
}

float UAOSFluidPhysicsComponent::GetEffectiveMass() const
{
	if (MassOverrideKg > 0.f)
	{
		return MassOverrideKg;
	}
	const UPrimitiveComponent* Body = GetDrivenBody();
	return (Body && Body->IsSimulatingPhysics()) ? Body->GetMass() : 0.f;
}

float UAOSFluidPhysicsComponent::GetWaveCoupling() const
{
	return ComputeWaveCoupling(GetEffectiveMass());
}

FAOSFluidSample UAOSFluidPhysicsComponent::SampleFluidAt(const FVector& WorldLocation) const
{
	FAOSFluidSample Sample;
	EvaluateWaves(WorldLocation, GetWaveTime(), ResponseModel == EAOSFluidResponseModel::Newtonian,
		Sample.SurfaceZ, Sample.FluidVelocity, Sample.WaveNormal);
	Sample.bInWater = WorldLocation.Z <= Sample.SurfaceZ;
	Sample.Submersion = Sample.bInWater ? 1.f : 0.f;
	Sample.WaveCoupling = 1.f;
	return Sample;
}

float UAOSFluidPhysicsComponent::GetWaveHeightAt(const FVector& WorldLocation) const
{
	return SampleFluidAt(WorldLocation).SurfaceZ;
}

FAOSFluidSample UAOSFluidPhysicsComponent::StepFluidPhysics(float DeltaTime)
{
	UPrimitiveComponent* Body = GetDrivenBody();
	if (!Body)
	{
		LastSample = FAOSFluidSample();
		return LastSample;
	}

	LastSample = (ResponseModel == EAOSFluidResponseModel::VehicleAcceleration)
		? StepVehicle(Body, DeltaTime)
		: StepNewtonian(Body, DeltaTime);
	return LastSample;
}

// ==================================================================================================
// Sea state
// ==================================================================================================
float UAOSFluidPhysicsComponent::GetWaveTime() const
{
	const UWorld* World = GetWorld();
	return World ? World->GetTimeSeconds() : 0.f;
}

void UAOSFluidPhysicsComponent::RebuildWaveSpectrum()
{
	WaveRuntime.Reset(WaveHarmonics.Num());
	for (const FAOSWaveHarmonic& Desc : WaveHarmonics)
	{
		FWaveRuntime& H = WaveRuntime.AddDefaulted_GetRef();
		H.Amplitude = Desc.Amplitude;
		H.K = 2.0f * PI / FMath::Max(1.0f, Desc.Wavelength);
		H.Omega = FMath::Sqrt(AOSFluid::DispersionGravity * H.K);
		const float Rad = FMath::DegreesToRadians(Desc.DirectionDeg);
		H.Direction = FVector2D(FMath::Cos(Rad), FMath::Sin(Rad));
		H.PhaseOffset = Desc.Phase;
	}
}

void UAOSFluidPhysicsComponent::EvaluateWaves(const FVector& Location, float Time, bool bDecayNormalWithDepth,
	float& OutSurfaceZ, FVector& OutFluidVel, FVector& OutWaveNormal) const
{
	OutSurfaceZ = OceanSurfaceZ;
	OutFluidVel = FVector::ZeroVector;

	// Depth below the mean sea level (capped at 0 for surface calculations)
	float ZDepth = FMath::Min(0.0f, Location.Z - OceanSurfaceZ);
	FVector2D Pos2D(Location.X, Location.Y);

	float GradX = 0.0f;
	float GradY = 0.0f;

	for (const FWaveRuntime& H : WaveRuntime)
	{
		float Phase = FVector2D::DotProduct(H.Direction, Pos2D) * H.K - H.Omega * Time + H.PhaseOffset;
		float CosP = FMath::Cos(Phase);
		float SinP = FMath::Sin(Phase);

		// Surface elevation
		OutSurfaceZ += H.Amplitude * CosP;

		// Kinematic exponential decay e^(k*z)
		float DepthDecay = FMath::Exp(H.K * ZDepth);

		// Orbital velocity field
		float VelMag = H.Amplitude * H.Omega * DepthDecay;
		OutFluidVel.X += H.Direction.X * VelMag * CosP;
		OutFluidVel.Y += H.Direction.Y * VelMag * CosP;
		OutFluidVel.Z += VelMag * SinP;

		// Surface gradient (derivative of elevation) for the normal; optionally attenuated with depth
		float D = -H.Amplitude * H.K * SinP;
		if (bDecayNormalWithDepth)
		{
			D *= DepthDecay;
		}
		GradX += H.Direction.X * D;
		GradY += H.Direction.Y * D;
	}

	OutWaveNormal = FVector(-GradX, -GradY, 1.0f).GetSafeNormal();
}

float UAOSFluidPhysicsComponent::ComputeWaveCoupling(float Mass) const
{
	if (ResponseModel == EAOSFluidResponseModel::VehicleAcceleration)
	{
		// Vehicle handling is tuned in accelerations: the wave field acts as authored.
		return WaveInfluenceScale;
	}

	// Newton: the wave exerts a force F_wave = m_ref * a_ref on any body of this size class, so the
	// resulting acceleration is a = F_wave / m = a_ref * (m_ref / m). It saturates at 1 (a light body cannot
	// move faster than the water that carries it).
	const float M = FMath::Max(Mass, KINDA_SMALL_NUMBER);
	const float Inertia = FMath::Min(1.f, WaveReferenceMassKg / M);

	// Heavy bodies (cargo pods, wrecks): wave forcing is cut to exactly zero at WaveImmuneMassKg.
	const float Immunity = (WaveImmuneMassKg > 0.f)
		? 1.f - FMath::SmoothStep(0.5f * WaveImmuneMassKg, WaveImmuneMassKg, M)
		: 1.f;

	return WaveInfluenceScale * Inertia * Immunity;
}

void UAOSFluidPhysicsComponent::ApplyWaveCoupling(float Coupling, float& InOutSurfaceZ, FVector& InOutFluidVel, FVector& InOutNormal) const
{
	if (Coupling == 1.f)
	{
		return; // Full coupling: field used verbatim (keeps the vehicle path bit-exact).
	}
	InOutSurfaceZ = OceanSurfaceZ + (InOutSurfaceZ - OceanSurfaceZ) * Coupling;
	InOutFluidVel *= Coupling;
	InOutNormal = FMath::Lerp(FVector::UpVector, InOutNormal, double(FMath::Min(Coupling, 1.f))).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
}

// ==================================================================================================
// Vehicle model (original AShellPawn hydrodynamics, mass-agnostic)
// ==================================================================================================
FAOSFluidSample UAOSFluidPhysicsComponent::StepVehicle(UPrimitiveComponent* Body, float DeltaTime)
{
	FAOSFluidSample S;
	const FVector Location = Body->GetComponentLocation();
	const FVector CurrentVelocity = Body->GetComponentVelocity();

	float LocalWaveZ = OceanSurfaceZ;
	FVector FluidVelocity = FVector::ZeroVector;
	FVector TargetNormal = FVector::UpVector;

	// Absolute fluid velocity at the current depth
	EvaluateWaves(Location, GetWaveTime(), false, LocalWaveZ, FluidVelocity, TargetNormal);
	S.WaveCoupling = ComputeWaveCoupling(0.f);
	ApplyWaveCoupling(S.WaveCoupling, LocalWaveZ, FluidVelocity, TargetNormal);

	S.SurfaceZ = LocalWaveZ;
	S.FluidVelocity = FluidVelocity;
	S.WaveNormal = TargetNormal;
	S.bInWater = (Location.Z <= LocalWaveZ);
	S.Submersion = S.bInWater ? 1.f : 0.f;

	if (!S.bInWater)
	{
		// AIR STATE: full engine gravity
		Body->SetEnableGravity(true);
		return S;
	}

	// Native gravity off: buoyancy and surface penetration are handled here
	Body->SetEnableGravity(false);

	// Archimedes volume penetration: gravity fades to 0 as the hull sinks through the entry band
	float SubmergedDepth = LocalWaveZ - Location.Z;
	float EntryGravityFraction = FMath::Clamp(1.0f - (SubmergedDepth / SurfaceEntryDepth), 0.0f, 1.0f);
	if (EntryGravityFraction > 0.01f)
	{
		Body->AddForce(FVector(0.f, 0.f, -SurfaceEntryGravity * EntryGravityFraction), NAME_None, true);
	}

	// Morison: hydrodynamic drag opposing the relative velocity
	FVector RelativeVelocity = CurrentVelocity - FluidVelocity;
	float RelSpeed = RelativeVelocity.Size();
	float DragCoeff = FluidDrag + (FluidQuadraticDrag * RelSpeed);

	float MaxSafeDrag = 0.5f / FMath::Max(DeltaTime, 0.0001f);
	DragCoeff = FMath::Min(DragCoeff, MaxSafeDrag);

	FVector DragAccel = -RelativeVelocity * DragCoeff;
	Body->AddForce(DragAccel, NAME_None, true);

	// Angular hydrodynamic damping
	S.AngularVelocity = Body->GetPhysicsAngularVelocityInRadians();
	float SafeAngularDrag = FMath::Min(AngularFluidDrag, MaxSafeDrag);
	Body->AddTorqueInRadians(-S.AngularVelocity * SafeAngularDrag, NAME_None, true);

	if (bPassiveFlotation)
	{
		if (Location.Z > LocalWaveZ - FlotationCaptureDepth)
		{
			// Archimedes spring riding the local wave
			float TargetZ = LocalWaveZ - FlotationDraft;
			float ZError = TargetZ - Location.Z;
			float BuoyancyAccelZ = (ZError * FlotationStiffness) - (CurrentVelocity.Z * FlotationDamping);
			Body->AddForce(FVector(0.f, 0.f, BuoyancyAccelZ), NAME_None, true);
		}
		else
		{
			// Deep underwater parking brake
			Body->AddForce(FVector(0.f, 0.f, -CurrentVelocity.Z * DeepHeaveBrake), NAME_None, true);
		}

		// Align the hull with the waves
		FVector BodyUp = Body->GetUpVector();
		FVector RestoringTorqueAxis = FVector::CrossProduct(BodyUp, TargetNormal);
		Body->AddTorqueInRadians(RestoringTorqueAxis * RightingStiffness, NAME_None, true);
	}
	return S;
}

// ==================================================================================================
// Newtonian model (mass-scaled props)
// ==================================================================================================
FAOSFluidSample UAOSFluidPhysicsComponent::StepNewtonian(UPrimitiveComponent* Body, float DeltaTime)
{
	FAOSFluidSample S;
	if (!Body->IsSimulatingPhysics())
	{
		if (!bWarnedNotSimulating)
		{
			bWarnedNotSimulating = true;
			UE_LOG(LogAOSFluid, Warning, TEXT("%s: driven body %s does not simulate physics - fluid forces skipped."),
				*GetNameSafe(GetOwner()), *GetNameSafe(Body));
		}
		return S;
	}

	const float Mass = GetEffectiveMass();
	S.WaveCoupling = ComputeWaveCoupling(Mass);

	// Sample at the bounds centre (mesh pivots are often at the base)
	const FBoxSphereBounds& Bounds = Body->Bounds;
	const FVector Center = Bounds.Origin;
	const float HalfHeight = FMath::Max(SubmersionHalfHeight > 0.f ? SubmersionHalfHeight : float(Bounds.BoxExtent.Z), 1.f);

	float SurfaceZ = OceanSurfaceZ;
	FVector FluidVelocity = FVector::ZeroVector;
	FVector WaveNormal = FVector::UpVector;
	EvaluateWaves(Center, GetWaveTime(), true, SurfaceZ, FluidVelocity, WaveNormal);
	ApplyWaveCoupling(S.WaveCoupling, SurfaceZ, FluidVelocity, WaveNormal);

	S.SurfaceZ = SurfaceZ;
	S.FluidVelocity = FluidVelocity;
	S.WaveNormal = WaveNormal;
	S.Submersion = FMath::Clamp(float(SurfaceZ - (Center.Z - HalfHeight)) / (2.f * HalfHeight), 0.f, 1.f);
	S.bInWater = S.Submersion > 0.f;
	S.AngularVelocity = Body->GetPhysicsAngularVelocityInRadians();

	if (!S.bInWater)
	{
		return S; // Airborne: engine gravity only
	}

	const UWorld* World = GetWorld();
	const float G = World ? -World->GetGravityZ() : 980.f;

	// The forces below are held for one physics step; without substepping Chaos clamps it to MaxPhysicsDeltaTime.
	float PhysicsStep = FMath::Max(DeltaTime, 0.0001f);
	if (const UPhysicsSettings* Settings = UPhysicsSettings::Get(); Settings && !Settings->bSubstepping)
	{
		PhysicsStep = FMath::Min(PhysicsStep, FMath::Max(Settings->MaxPhysicsDeltaTime, 0.0001f));
	}
	const float MaxSafeRate = 0.5f / PhysicsStep;
	const FVector Velocity = Body->GetComponentVelocity();

	// 1) Archimedes: F_b = BuoyancyFactor * m * g * submersion  ->  a = BuoyancyFactor * g * submersion.
	//    Against engine weight (m*g): B < 1 sinks to the seabed, B > 1 settles at submersion = 1/B.
	//    Submersion is taken at the step midpoint (semi-implicit) so the waterline spring cannot gain energy.
	const float MidCenterZ = float(Center.Z) + 0.5f * float(Velocity.Z) * PhysicsStep;
	const float Sub = FMath::Clamp((SurfaceZ - (MidCenterZ - HalfHeight)) / (2.f * HalfHeight), 0.f, 1.f);
	Body->AddForce(FVector(0.f, 0.f, BuoyancyFactor * G * Sub), NAME_None, true);

	// 2) Morison drag against the mass-coupled orbital flow. The wave-induced part of this term,
	//    Rate * Coupling * u_fluid, carries the a = F_wave / m scaling through Coupling.
	const FVector RelativeVelocity = Velocity - FluidVelocity;
	const float DragRate = FMath::Min((FluidDrag + FluidQuadraticDrag * float(RelativeVelocity.Size())) * Sub, MaxSafeRate);
	Body->AddForce(-RelativeVelocity * DragRate, NAME_None, true);

	// 3) Waterline heave damping while piercing the surface (fraction of critical for the buoyancy spring)
	if (Sub > 0.f && Sub < 1.f && HeaveDampingRatio > 0.f)
	{
		const float HeaveOmega = FMath::Sqrt(BuoyancyFactor * G / (2.f * HalfHeight));
		const float HeaveRate = FMath::Min(2.f * HeaveDampingRatio * HeaveOmega, MaxSafeRate);
		Body->AddForce(FVector(0.f, 0.f, -RelativeVelocity.Z * HeaveRate), NAME_None, true);
	}

	// 4) Rotational damping
	const float AngularRate = FMath::Min(AngularFluidDrag * Sub, MaxSafeRate);
	Body->AddTorqueInRadians(-S.AngularVelocity * AngularRate, NAME_None, true);

	// 5) Metacentric righting towards the mass-coupled wave normal: rocking ~ Coupling, upright otherwise
	if (RightingStiffness > 0.f)
	{
		const FVector Axis = FVector::CrossProduct(Body->GetUpVector(), WaveNormal);
		Body->AddTorqueInRadians(Axis * (RightingStiffness * Sub), NAME_None, true);
	}
	return S;
}
