#include "AOS_DK/Submarine/Subdrones/Attacker/MicroTorpedo.h"

#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBase.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneMath.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneTypes.h"
#include "Components/PointLightComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	FName SheathRateParam()
	{
		static const FName Name(TEXT("SheathRate"));
		return Name;
	}

	/** Custom Primitive Data of the FX materials: 0 = intensity (0..1), 1..3 = tint RGB. */
	namespace FxCPD
	{
		constexpr int32 Intensity = 0;
		constexpr int32 TintR = 1;
		constexpr int32 TintG = 2;
		constexpr int32 TintB = 3;
	}

	/** Purely visual child mesh: no collision / shadows / navigation, invisible until used. */
	UStaticMeshComponent* MakeFxMesh(AActor* Owner, const TCHAR* Name, USceneComponent* Parent, UStaticMesh* StaticMesh, int32 SortPriority)
	{
		UStaticMeshComponent* C = Owner->CreateDefaultSubobject<UStaticMeshComponent>(Name);
		C->SetupAttachment(Parent);
		C->SetMobility(EComponentMobility::Movable);
		C->SetStaticMesh(StaticMesh);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetGenerateOverlapEvents(false);
		C->SetCanEverAffectNavigation(false);
		C->SetCastShadow(false);
		C->bAffectDistanceFieldLighting = false;
		C->bAffectDynamicIndirectLighting = false;
		C->SetReceivesDecals(false);
		C->SetTranslucentSortPriority(SortPriority);
		C->SetVisibility(false);
		return C;
	}
}
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/DamageType.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"

AMicroTorpedo::AMicroTorpedo()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false; // ticks only while in flight (pooled)

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetCastShadow(false);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->SetCanEverAffectNavigation(false);
	Mesh->bAffectDistanceFieldLighting = false;
	Mesh->SetReceivesDecals(false);
	RootComponent = Mesh;

	TrailFX = CreateDefaultSubobject<UNiagaraComponent>(TEXT("TrailFX"));
	TrailFX->SetupAttachment(Mesh);
	TrailFX->SetRelativeLocation(FVector(-5.5f, 0.f, 0.f)); // nozzle of SM_MicroTorpedo (11 cm, pivot at centre)
	TrailFX->SetAutoActivate(false);
	TrailFX->SetCastShadow(false);

	// Visibility + hit feedback. Engine basic shapes (always present); materials are assigned on BP_MicroTorpedo.
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderAsset(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereAsset(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneAsset(TEXT("/Engine/BasicShapes/Plane.Plane"));

	TracerMesh = MakeFxMesh(this, TEXT("TracerMesh"), Mesh, CylinderAsset.Object, 10);
	// Cylinder axis (local Z) -> torpedo X: length is scaled on Z, the head stays at the nose.
	TracerMesh->SetRelativeRotation(FRotationMatrix::MakeFromZ(FVector::ForwardVector).Rotator());

	ImpactFlashMesh = MakeFxMesh(this, TEXT("ImpactFlashMesh"), Mesh, SphereAsset.Object, 12);
	ImpactFlashMesh->SetUsingAbsoluteScale(true);
	ImpactFlashMesh->SetUsingAbsoluteRotation(true);

	ImpactRingMesh = MakeFxMesh(this, TEXT("ImpactRingMesh"), Mesh, PlaneAsset.Object, 11);
	ImpactRingMesh->SetUsingAbsoluteScale(true);
	ImpactRingMesh->SetUsingAbsoluteRotation(true);

	ImpactLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("ImpactLight"));
	ImpactLight->SetupAttachment(Mesh);
	ImpactLight->SetMobility(EComponentMobility::Movable);
	ImpactLight->SetCastShadows(false);
	ImpactLight->SetIntensityUnits(ELightUnits::Candelas);
	ImpactLight->SetIntensity(0.f);
	ImpactLight->SetAttenuationRadius(ImpactLightRadius);
	ImpactLight->SetVolumetricScatteringIntensity(2.f);
	ImpactLight->SetAffectTranslucentLighting(false);
	ImpactLight->SetUsingAbsoluteScale(true);
	ImpactLight->SetVisibility(false);

	DamageType = UDamageType::StaticClass();
}

void AMicroTorpedo::BeginPlay()
{
	Super::BeginPlay();
	if (!bInFlight)
	{
		Mesh->SetVisibility(false);
		TracerMesh->SetVisibility(false);
		EndImpact();
	}
}

// ------------------------------------------------------------------------------------- tracer / impact / warm-up
void AMicroTorpedo::UpdateTracer(float Speed, float Brightness)
{
	const float Length = FMath::Clamp(Speed * TracerLengthSeconds, TracerMinLength, TracerMaxLength);
	const float Width = FMath::Max(0.1f, TracerWidth);
	// Unit cylinder: 100 cm tall, 100 cm diameter. Head at the nozzle-to-nose centre line, tail trails behind.
	TracerMesh->SetRelativeScale3D(FVector(Width * 0.01f, Width * 0.01f, Length * 0.01f));
	TracerMesh->SetRelativeLocation(FVector(5.5f - Length * 0.5f, 0.f, 0.f));
	TracerMesh->SetCustomPrimitiveDataFloat(FxCPD::Intensity, Brightness);
}

void AMicroTorpedo::StartImpact(const FVector& Location, const FVector& Normal, ESubDroneImpactKind Kind)
{
	ImpactKind = Kind;
	ImpactAge = 0.f;
	ImpactScale = Kind == ESubDroneImpactKind::Target ? 1.f
		: (Kind == ESubDroneImpactKind::Surface ? SurfaceImpactScale : ExpiredImpactScale);

	const FLinearColor Tint = Kind == ESubDroneImpactKind::Target ? TargetImpactColor : SurfaceImpactColor;
	const FVector N = Normal.GetSafeNormal();

	ImpactFlashMesh->SetWorldLocation(Location + N * 3.f);
	ImpactFlashMesh->SetCustomPrimitiveDataFloat(FxCPD::TintR, Tint.R);
	ImpactFlashMesh->SetCustomPrimitiveDataFloat(FxCPD::TintG, Tint.G);
	ImpactFlashMesh->SetCustomPrimitiveDataFloat(FxCPD::TintB, Tint.B);
	ImpactFlashMesh->SetVisibility(true);

	if (Kind != ESubDroneImpactKind::Expired)
	{
		ImpactRingMesh->SetWorldLocationAndRotation(Location + N * 2.f, FRotationMatrix::MakeFromZ(N).Rotator());
		ImpactRingMesh->SetCustomPrimitiveDataFloat(FxCPD::TintR, Tint.R);
		ImpactRingMesh->SetCustomPrimitiveDataFloat(FxCPD::TintG, Tint.G);
		ImpactRingMesh->SetCustomPrimitiveDataFloat(FxCPD::TintB, Tint.B);
		ImpactRingMesh->SetVisibility(true);

		ImpactLight->SetWorldLocation(Location + N * 45.f);
		ImpactLight->SetLightColor(Tint);
		ImpactLight->SetAttenuationRadius(ImpactLightRadius * ImpactScale);
		ImpactLight->SetIntensity(ImpactLightIntensity * ImpactScale);
		ImpactLight->SetVisibility(true);
	}
	TickImpact(0.f);
	UpdateTickState();
}

void AMicroTorpedo::TickImpact(float DeltaSeconds)
{
	ImpactAge += DeltaSeconds;
	const float T = ImpactAge / FMath::Max(0.05f, ImpactDuration);
	if (T >= 1.f)
	{
		EndImpact();
		UpdateTickState();
		return;
	}
	const float Fade = FMath::Square(1.f - T);          // hard flash, fast decay
	const float Grow = 1.f - FMath::Square(1.f - T);    // ease-out expansion

	const float FlashDiameter = 2.f * ImpactFlashRadius * ImpactScale * FMath::Lerp(0.2f, 1.f, Grow);
	ImpactFlashMesh->SetWorldScale3D(FVector(FlashDiameter * 0.01f));
	ImpactFlashMesh->SetCustomPrimitiveDataFloat(FxCPD::Intensity, Fade);

	if (ImpactKind != ESubDroneImpactKind::Expired)
	{
		const float RingDiameter = 2.f * ImpactRingRadius * ImpactScale * Grow;
		ImpactRingMesh->SetWorldScale3D(FVector(FMath::Max(RingDiameter, 1.f) * 0.01f));
		ImpactRingMesh->SetCustomPrimitiveDataFloat(FxCPD::Intensity, FMath::Pow(1.f - T, 1.5f));
		ImpactLight->SetIntensity(ImpactLightIntensity * ImpactScale * Fade);
	}
}

void AMicroTorpedo::EndImpact()
{
	ImpactAge = -1.f;
	if (ImpactFlashMesh) { ImpactFlashMesh->SetVisibility(false); }
	if (ImpactRingMesh) { ImpactRingMesh->SetVisibility(false); }
	if (ImpactLight) { ImpactLight->SetIntensity(0.f); ImpactLight->SetVisibility(false); }
}

void AMicroTorpedo::BeginWarmup(bool bSpawnImpactFx, const FVector& WorldLocation)
{
	if (bInFlight || bWarming)
	{
		return;
	}
	bWarming = true;
	WarmupFramesLeft = 8; // Niagara needs ~6 frames from Activate to its first particle draw
	WarmupSavedScale = Mesh->GetRelativeScale3D();

	// The engine only draws what the camera can see: park the torpedo right in front of the camera for the warm-up.
	WarmupSavedLocation = GetActorLocation();
	SetActorLocation(WorldLocation, false, nullptr, ETeleportType::TeleportPhysics);

	// Real draws at ~zero size: PSOs, material uniform buffers, Niagara simulations and render state get
	// created now, but nothing is visible. The tiny scale propagates to the attached trail (local-space sheath).
	// 2 %: below ~1 % the engine culls the primitive (verified: Niagara stops rendering after 2 frames at 0.001).
	const FVector Tiny(0.02f);
	Mesh->SetRelativeScale3D(Tiny);
	Mesh->SetVisibility(true);

	TracerMesh->SetRelativeScale3D(Tiny);
	TracerMesh->SetCustomPrimitiveDataFloat(FxCPD::Intensity, 0.f);
	TracerMesh->SetVisibility(true);

	for (UStaticMeshComponent* Fx : { ImpactFlashMesh.Get(), ImpactRingMesh.Get() })
	{
		Fx->SetWorldScale3D(Tiny);
		Fx->SetCustomPrimitiveDataFloat(FxCPD::Intensity, 0.f);
		Fx->SetVisibility(true);
	}

	if (TrailFX->GetAsset())
	{
		TrailFX->SetVariableFloat(SheathRateParam(), SheathCoastRate);
		TrailFX->Activate(true);
	}
	if (bSpawnImpactFx && ImpactFX)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, ImpactFX, GetActorLocation(), FRotator::ZeroRotator, Tiny, true, true, ENCPoolMethod::AutoRelease);
	}
	UpdateTickState();
}

void AMicroTorpedo::TickWarmup()
{
	if (--WarmupFramesLeft <= 0)
	{
		EndWarmup();
		UpdateTickState();
	}
}

void AMicroTorpedo::EndWarmup()
{
	if (!bWarming)
	{
		return;
	}
	bWarming = false;
	SetActorLocation(WarmupSavedLocation, false, nullptr, ETeleportType::TeleportPhysics);
	Mesh->SetRelativeScale3D(WarmupSavedScale);
	Mesh->SetVisibility(false);
	TracerMesh->SetVisibility(false);
	EndImpact();
	TrailFX->Deactivate();
}

void AMicroTorpedo::UpdateTickState()
{
	SetActorTickEnabled(bInFlight || bWarming || ImpactAge >= 0.f);
}

void AMicroTorpedo::Launch(const FVector& Location, const FQuat& Rotation, const FVector& InitialVelocity,
	const FVector& TargetPoint, AActor* InTargetActor)
{
	SetActorLocationAndRotation(Location, Rotation, false, nullptr, ETeleportType::TeleportPhysics);

	EndWarmup();
	EndImpact();

	Vel = InitialVelocity;
	Heading = Rotation;
	Age = 0.f;
	RollDeg = 0.f;
	CavitationAlpha = 0.f;
	bCavitating = false;
	bInFlight = true;
	PenetrationIgnores.Reset();

	TargetPointWorld = TargetPoint;
	TargetActor = InTargetActor;
	if (InTargetActor)
	{
		// Track the exact aimed spot on a moving target.
		TargetLocalOffset = InTargetActor->GetActorTransform().InverseTransformPosition(TargetPoint);
	}

	Mesh->SetVisibility(true);
	Mesh->SetCustomPrimitiveDataFloat(SubDroneCPD::TorpedoCharge, 1.f); // fully charged tip in flight
	UpdateTracer(InitialVelocity.Size(), 0.45f);
	TracerMesh->SetVisibility(true);
	SetActorTickEnabled(true);

	if (TrailFX->GetAsset())
	{
		TrailFX->SetVariableFloat(SheathRateParam(), SheathCoastRate);
		LastSheathRate = SheathCoastRate;
		TrailFX->Activate(true);
	}

	BP_OnLaunched();
}

void AMicroTorpedo::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bWarming)
	{
		TickWarmup();
	}
	if (ImpactAge >= 0.f)
	{
		TickImpact(DeltaSeconds);
	}
	if (!bInFlight || DeltaSeconds <= 0.f)
	{
		return;
	}

	// Integrate all sub-steps in local variables, then ONE sweep along the frame's path and ONE
	// transform update (previously: a sweep + actor move per sub-step).
	const FVector StartPos = GetActorLocation();
	FVector Pos = StartPos;
	FVector FuseTarget = FVector::ZeroVector;
	bool bFuse = false;

	const int32 Steps = FMath::Clamp(FMath::CeilToInt32(DeltaSeconds / Ballistics.MaxSubstep), 1, 8);
	const float H = DeltaSeconds / Steps;
	for (int32 Step = 0; Step < Steps; ++Step)
	{
		if (!IntegrateStep(H, Pos, FuseTarget))
		{
			bFuse = true;
			break;
		}
	}

	// Hit registration, every frame from the first one (also inside the arming window - a launch at
	// point-blank range must not tunnel through the target):
	//  1) direct impact: thin sphere sweep along the frame's path;
	//  2) continuous proximity fuse: fat sphere sweep that only reacts to fuse targets, so a fast
	//     needle passing BESIDE a daemon (or through its halo/tendrils) still detonates on it.
	{
		FCollisionQueryParams Params(SCENE_QUERY_STAT(MicroTorpedoSweep), false, this);
		Params.AddIgnoredActor(GetOwner());
		Params.AddIgnoredActor(GetInstigator());
		for (const TWeakObjectPtr<AActor>& Ignored : PenetrationIgnores)
		{
			Params.AddIgnoredActor(Ignored.Get());
		}

		FHitResult Hit;
		bool bDirect = GetWorld()->SweepSingleByChannel(Hit, StartPos, Pos, FQuat::Identity, CollisionChannel,
			FCollisionShape::MakeSphere(Ballistics.CollisionRadius), Params);
		if (bDirect && Hit.bStartPenetrating && !IsFuseTarget(Hit.GetActor()))
		{
			// Born inside a non-target volume (water body, trigger-like blockers): ignore it from now on.
			PenetrationIgnores.Add(Hit.GetActor());
			bDirect = false;
		}

		FHitResult ProxHit;
		const bool bProx = Age >= Ballistics.ArmingTime && FindProximityHit(StartPos, Pos, Params, ProxHit);

		if (bDirect || bProx)
		{
			const FHitResult& First = (bDirect && (!bProx || Hit.Time <= ProxHit.Time)) ? Hit : ProxHit;
			SetActorLocation(First.bStartPenetrating ? StartPos : FVector(First.Location), false, nullptr, ETeleportType::TeleportPhysics);
			Detonate(First, true);
			return;
		}
	}

	if (bFuse)
	{
		SetActorLocation(Pos, false, nullptr, ETeleportType::TeleportPhysics);
		FHitResult ProxHit(TargetActor.Get(), nullptr, FuseTarget, -Vel.GetSafeNormal());
		Detonate(ProxHit, TargetActor.IsValid());
		return;
	}

	// Body aligned with the velocity (cavity axis) + cosmetic roll; single transform update.
	if (Vel.SizeSquared() > 1.0)
	{
		Heading = SubDroneMath::DampQuat(Heading, FRotationMatrix::MakeFromX(Vel).ToQuat(), 0.03f, DeltaSeconds);
	}
	RollDeg = static_cast<float>(SubDroneMath::WrapDegrees(RollDeg + Ballistics.VisualRollDegPerSec * DeltaSeconds));
	SetActorLocationAndRotation(Pos, Heading * FQuat(FVector::XAxisVector, FMath::DegreesToRadians(RollDeg)), false, nullptr, ETeleportType::TeleportPhysics);

	if (Age >= Ballistics.MaxLifetime)
	{
		Detonate(FHitResult(), false);
		return;
	}

	// Streak grows with speed and brightens as the cavity forms; its head rides the nose.
	UpdateTracer(static_cast<float>(Vel.Size()), FMath::Lerp(0.45f, 1.f, CavitationAlpha));

	if (TrailFX->IsActive())
	{
		const float Rate = FMath::Lerp(SheathCoastRate, SheathMaxRate, CavitationAlpha);
		if (FMath::Abs(Rate - LastSheathRate) > FMath::Max(5.f, LastSheathRate * 0.05f))
		{
			TrailFX->SetVariableFloat(SheathRateParam(), Rate);
			LastSheathRate = Rate;
		}
	}
}

void AMicroTorpedo::Retarget(AActor* NewAimActor, const FVector& NewPoint)
{
	if (!bInFlight)
	{
		return;
	}
	TargetPointWorld = NewPoint;
	TargetActor = NewAimActor;
	TargetLocalOffset = NewAimActor ? NewAimActor->GetActorTransform().InverseTransformPosition(NewPoint) : FVector::ZeroVector;
}

FVector AMicroTorpedo::GetGuidanceTarget(FVector& OutTargetVelocity) const
{
	if (const AActor* Target = TargetActor.Get())
	{
		OutTargetVelocity = Target->GetVelocity();
		return Target->GetActorTransform().TransformPosition(TargetLocalOffset);
	}
	OutTargetVelocity = FVector::ZeroVector;
	return TargetPointWorld;
}

bool AMicroTorpedo::IntegrateStep(float H, FVector& Pos, FVector& OutFuseTarget)
{
	const FMicroTorpedoBallistics& B = Ballistics;
	Age += H;

	FVector V = Vel;
	const float Speed = static_cast<float>(V.Size());
	const FVector Fwd = Speed > 1.f ? V / Speed : Heading.GetForwardVector();

	FVector TargetVel;
	const FVector Target = GetGuidanceTarget(TargetVel);

	if (Age <= B.EjectDuration)
	{
		// 1) Magnetic sling release: coasting, wetted body bleeds speed.
		V *= FMath::Exp(-B.EjectDragPerSec * H);
	}
	else
	{
		// 2) Ignition + supercavitation.
		const float ThrustAlpha = FMath::Clamp((Age - B.EjectDuration) / B.ThrustRampTime, 0.f, 1.f);
		CavitationAlpha = FMath::SmoothStep(B.CavitationOnsetSpeed - B.CavitationBlendWidth, B.CavitationOnsetSpeed, Speed);
		if (!bCavitating && CavitationAlpha > 0.5f)
		{
			bCavitating = true;
			BP_OnCavitationStarted();
		}

		const FVector R = Target - Pos;
		const double Dist = R.Size();
		const FVector Los = Dist > 1.0 ? R / Dist : Fwd;

		// Thrust vectoring towards the line of sight (bounded) - keeps the release bloom compact.
		FVector ThrustDir = Fwd;
		{
			const FQuat Between = FQuat::FindBetweenNormals(Fwd, Los);
			const double Angle = Between.GetAngle();
			if (Angle > 1e-4)
			{
				const double K = FMath::Min(1.0, FMath::DegreesToRadians(static_cast<double>(B.MaxThrustVectorAngle)) / Angle);
				ThrustDir = FQuat::Slerp(FQuat::Identity, Between, K).RotateVector(Fwd);
			}
		}
		FVector Accel = ThrustDir * (B.ThrustAccel * ThrustAlpha);

		// 3) Guidance: true proportional navigation a = N * Vc * Vr_perp / |R| + pursuit blend.
		if (Dist > 1.0)
		{
			const FVector Vr = TargetVel - V;
			const double Closing = -FVector::DotProduct(Vr, Los);
			FVector Lateral = FVector::ZeroVector;
			if (Closing > 0.0)
			{
				const FVector VrPerp = Vr - Los * FVector::DotProduct(Vr, Los);
				Lateral += VrPerp * (B.NavigationConstant * Closing / Dist);
			}
			const float CosErr = static_cast<float>(FVector::DotProduct(Fwd, Los));
			const float PursuitWeight = 1.f - FMath::SmoothStep(0.6f, 0.98f, CosErr);
			Lateral += (Los * Speed - V) * (B.PursuitGain * PursuitWeight);
			Lateral -= Fwd * FVector::DotProduct(Lateral, Fwd);
			const float Authority = FMath::Clamp(Speed / B.CavitationOnsetSpeed, 0.25f, 1.f) * ThrustAlpha;
			Accel += Lateral.GetClampedToMaxSize(B.MaxLateralAccel * Authority);
		}

		V += Accel * H;
		// Semi-implicit quadratic drag v /= (1 + C|v|h): unconditionally stable at any speed.
		const float C = FMath::Lerp(B.WettedDragCoeff, B.CavitatingDragCoeff, CavitationAlpha);
		V /= (1.0 + C * V.Size() * H);
	}

	Vel = V;
	Pos += V * H;

	if (Age >= B.ArmingTime && FVector::DistSquared(Pos, Target) < FMath::Square(B.ProximityFuseRadius))
	{
		OutFuseTarget = Target;
		return false;
	}
	return true;
}

bool AMicroTorpedo::IsFuseTarget(const AActor* Actor) const
{
	if (!IsValid(Actor) || Actor == GetOwner() || Actor == GetInstigator() || !Actor->CanBeDamaged())
	{
		return false;
	}
	return ProximityTargetTag.IsNone() || Actor->ActorHasTag(ProximityTargetTag);
}

bool AMicroTorpedo::FindProximityHit(const FVector& From, const FVector& To, const FCollisionQueryParams& Params, FHitResult& OutHit) const
{
	if (Ballistics.ProximityFuseRadius <= 0.f)
	{
		return false;
	}
	// Object-type query: returns EVERY touched object along the path (no early stop on walls).
	FCollisionObjectQueryParams Objects;
	Objects.AddObjectTypesToQuery(ECC_WorldDynamic);
	Objects.AddObjectTypesToQuery(ECC_Pawn);
	Objects.AddObjectTypesToQuery(ECC_PhysicsBody);

	TArray<FHitResult> Hits;
	if (!GetWorld()->SweepMultiByObjectType(Hits, From, To, FQuat::Identity, Objects,
		FCollisionShape::MakeSphere(Ballistics.ProximityFuseRadius), Params))
	{
		return false;
	}
	bool bFound = false;
	for (const FHitResult& Candidate : Hits)
	{
		if (IsFuseTarget(Candidate.GetActor()) && (!bFound || Candidate.Time < OutHit.Time))
		{
			OutHit = Candidate;
			bFound = true;
		}
	}
	return bFound;
}

void AMicroTorpedo::Detonate(const FHitResult& Hit, bool bHitSomething)
{
	const FVector Location = bHitSomething ? FVector(Hit.ImpactPoint) : GetActorLocation();
	const FVector Dir = Vel.GetSafeNormal();

	const ESubDroneImpactKind Kind = !bHitSomething ? ESubDroneImpactKind::Expired
		: (IsFuseTarget(Hit.GetActor()) ? ESubDroneImpactKind::Target : ESubDroneImpactKind::Surface);

	if (bHitSomething && Hit.GetActor())
	{
		UGameplayStatics::ApplyPointDamage(Hit.GetActor(), Damage, Dir, Hit, GetInstigatorController(), this, DamageType);
	}

	const FVector Normal = (bHitSomething && !Hit.ImpactNormal.IsNearlyZero()) ? FVector(Hit.ImpactNormal) : -Dir;
	if (ImpactFX)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, ImpactFX, Location, Normal.Rotation(),
			FVector(ImpactFxScale * (Kind == ESubDroneImpactKind::Target ? 1.f : 0.7f)), true, true, ENCPoolMethod::AutoRelease);
	}

	// Readable feedback: flash + ring + light at the point of impact, crosshair hit-marker via the bay.
	StartImpact(Location, Normal, Kind);
	if (ASubDroneBase* Drone = Cast<ASubDroneBase>(GetOwner()))
	{
		if (USubDroneBayComponent* Bay = Drone->GetBay())
		{
			Bay->NotifyProjectileImpact(Drone, Kind, Location, bHitSomething ? Damage : 0.f);
		}
	}

	BP_OnDetonated(Hit, bHitSomething);
	Retire();
}

void AMicroTorpedo::Retire()
{
	bInFlight = false;
	bCavitating = false;
	Mesh->SetVisibility(false);
	TracerMesh->SetVisibility(false);
	TrailFX->Deactivate(); // stop spawning; world-space bubbles fade out naturally
	TargetActor.Reset();
	PenetrationIgnores.Reset();
	ReuseAvailableTime = GetWorld()->GetTimeSeconds() + FMath::Max(TrailLingerTime, ImpactDuration);
	UpdateTickState(); // stays on while the impact flash animates
}
