#include "AOS_DK/Submarine/Subdrones/Attacker/MicroTorpedo.h"

#include "AOS_DK/Submarine/Subdrones/Core/SubDroneMath.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneTypes.h"

namespace
{
	FName SheathRateParam()
	{
		static const FName Name(TEXT("SheathRate"));
		return Name;
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

	DamageType = UDamageType::StaticClass();
}

void AMicroTorpedo::BeginPlay()
{
	Super::BeginPlay();
	if (!bInFlight)
	{
		Mesh->SetVisibility(false);
	}
}

void AMicroTorpedo::Launch(const FVector& Location, const FQuat& Rotation, const FVector& InitialVelocity,
	const FVector& TargetPoint, AActor* InTargetActor)
{
	SetActorLocationAndRotation(Location, Rotation, false, nullptr, ETeleportType::TeleportPhysics);

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

	if (Age >= Ballistics.ArmingTime)
	{
		FCollisionQueryParams Params(SCENE_QUERY_STAT(MicroTorpedoSweep), false, this);
		Params.AddIgnoredActor(GetOwner());
		Params.AddIgnoredActor(GetInstigator());
		for (const TWeakObjectPtr<AActor>& Ignored : PenetrationIgnores)
		{
			Params.AddIgnoredActor(Ignored.Get());
		}

		FHitResult Hit;
		if (GetWorld()->SweepSingleByChannel(Hit, StartPos, Pos, FQuat::Identity, CollisionChannel,
			FCollisionShape::MakeSphere(Ballistics.CollisionRadius), Params))
		{
			if (Hit.bStartPenetrating && Hit.GetActor() != TargetActor.Get())
			{
				PenetrationIgnores.Add(Hit.GetActor()); // born inside a volume: ignore it from now on
			}
			else
			{
				SetActorLocation(Hit.Location, false, nullptr, ETeleportType::TeleportPhysics);
				Detonate(Hit, true);
				return;
			}
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

void AMicroTorpedo::Detonate(const FHitResult& Hit, bool bHitSomething)
{
	const FVector Location = bHitSomething ? FVector(Hit.ImpactPoint) : GetActorLocation();
	const FVector Dir = Vel.GetSafeNormal();

	if (bHitSomething && Hit.GetActor())
	{
		UGameplayStatics::ApplyPointDamage(Hit.GetActor(), Damage, Dir, Hit, GetInstigatorController(), this, DamageType);
	}

	if (ImpactFX)
	{
		const FRotator FxRot = (bHitSomething ? FVector(Hit.ImpactNormal) : -Dir).Rotation();
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, ImpactFX, Location, FxRot, FVector(1.f), true, true, ENCPoolMethod::AutoRelease);
	}

	BP_OnDetonated(Hit, bHitSomething);
	Retire();
}

void AMicroTorpedo::Retire()
{
	bInFlight = false;
	bCavitating = false;
	SetActorTickEnabled(false);
	Mesh->SetVisibility(false);
	TrailFX->Deactivate(); // stop spawning; world-space bubbles fade out naturally
	TargetActor.Reset();
	PenetrationIgnores.Reset();
	ReuseAvailableTime = GetWorld()->GetTimeSeconds() + TrailLingerTime;
}
