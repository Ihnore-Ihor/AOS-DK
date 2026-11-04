#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBase.h"

#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneMath.h"
#include "Components/SphereComponent.h"
#include "GameFramework/Pawn.h"

DEFINE_LOG_CATEGORY(LogSubDrone);

using namespace SubDroneMath;

ASubDroneBase::ASubDroneBase()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;
	// Read the Shell transform AFTER its physics step -> no one-frame lag jitter.
	PrimaryActorTick.TickGroup = TG_PostPhysics;

	CollisionSphere = CreateDefaultSubobject<USphereComponent>(TEXT("CollisionSphere"));
	CollisionSphere->InitSphereRadius(24.f);
	CollisionSphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	CollisionSphere->SetCollisionObjectType(ECC_WorldDynamic);
	CollisionSphere->SetCollisionResponseToAllChannels(ECR_Ignore);
	CollisionSphere->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
	CollisionSphere->SetGenerateOverlapEvents(false);
	CollisionSphere->SetCanEverAffectNavigation(false);
	CollisionSphere->SetShouldUpdatePhysicsVolume(false);
	RootComponent = CollisionSphere;

	VisualRoot = CreateDefaultSubobject<USceneComponent>(TEXT("VisualRoot"));
	VisualRoot->SetupAttachment(CollisionSphere);

	// Passive crescent: tight and calm so the drone stays at the same spot of the screen.
	FormationMotion.ComfortHalfLife = 0.25f;
	FormationMotion.CatchUpHalfLife = 0.10f;
	FormationMotion.ComfortRadius = 25.f;
	FormationMotion.LeashRadius = 250.f;
	FormationMotion.HostFrameHalfLife = 0.12f;
	FormationMotion.HostRollInfluence = 0.35f;
	FormationMotion.OrientationHalfLife = 0.18f;
	FormationMotion.BobAmplitude = 4.f;
	FormationMotion.BobFrequency = 0.3f;

	// Active working position: looser hover with more inertia, fast nose tracking.
	DeployedMotion.ComfortHalfLife = 0.45f;
	DeployedMotion.CatchUpHalfLife = 0.14f;
	DeployedMotion.ComfortRadius = 60.f;
	DeployedMotion.LeashRadius = 400.f;
	DeployedMotion.HostFrameHalfLife = 0.3f;
	DeployedMotion.HostRollInfluence = 0.15f;
	DeployedMotion.OrientationHalfLife = 0.1f;
	DeployedMotion.BobAmplitude = 2.5f;
	DeployedMotion.BobFrequency = 0.45f;
}

void ASubDroneBase::InitializeDrone(USubDroneBayComponent* InBay, int32 InSlotIndex)
{
	Bay = InBay;
	SlotIndex = InSlotIndex;
	HostPawn = InBay ? InBay->GetHostPawn() : nullptr;
}

void ASubDroneBase::BeginPlay()
{
	Super::BeginPlay();

	BobSeed = FMath::FRandRange(0.f, 100.f);

	if (APawn* Host = HostPawn.Get())
	{
		FilteredHostFrame = Host->GetActorQuat();
		CollisionSphere->IgnoreActorWhenMoving(Host, true);
		Velocity = Bay.IsValid() ? Bay->GetHostVelocity() : FVector::ZeroVector;
	}
	else
	{
		UE_LOG(LogSubDrone, Warning, TEXT("%s spawned without a Shell host - spawn it through USubDroneBayComponent."), *GetName());
		SetActorTickEnabled(false);
	}
}

bool ASubDroneBase::IsDeployed() const
{
	return MobilityState == ESubDroneMobilityState::Deployed ||
		((MobilityState == ESubDroneMobilityState::Docking || MobilityState == ESubDroneMobilityState::Docked) && bDeployAfterResupply);
}

// ------------------------------------------------------------------------------- FSM control
void ASubDroneBase::RequestDeploy()
{
	switch (MobilityState)
	{
	case ESubDroneMobilityState::Formation: SetMobilityState(ESubDroneMobilityState::Deployed); break;
	case ESubDroneMobilityState::Docking:
	case ESubDroneMobilityState::Docked:    bDeployAfterResupply = true; break;
	default: break;
	}
}

void ASubDroneBase::RequestRecall()
{
	switch (MobilityState)
	{
	case ESubDroneMobilityState::Deployed:  SetMobilityState(ESubDroneMobilityState::Formation); break;
	case ESubDroneMobilityState::Docking:
	case ESubDroneMobilityState::Docked:    bDeployAfterResupply = false; break;
	default: break;
	}
}

void ASubDroneBase::ToggleDeployment()
{
	IsDeployed() ? RequestRecall() : RequestDeploy();
}

void ASubDroneBase::RequestDock()
{
	if (MobilityState == ESubDroneMobilityState::Docking || MobilityState == ESubDroneMobilityState::Docked)
	{
		return;
	}
	bDeployAfterResupply = MobilityState == ESubDroneMobilityState::Deployed;
	SetMobilityState(ESubDroneMobilityState::Docking);
}

void ASubDroneBase::RequestUndock()
{
	if (MobilityState != ESubDroneMobilityState::Docking && MobilityState != ESubDroneMobilityState::Docked)
	{
		return;
	}
	if (MobilityState == ESubDroneMobilityState::Docked && Bay.IsValid())
	{
		const FTransform Dock = Bay->GetDockWorldTransform(SlotIndex);
		DetachFromDock();
		Velocity = Bay->GetHostVelocity() + Dock.GetRotation().GetUpVector() * UndockKickSpeed;
	}
	SetMobilityState(bDeployAfterResupply ? ESubDroneMobilityState::Deployed : ESubDroneMobilityState::Formation);
	bDeployAfterResupply = false;
}

void ASubDroneBase::SetMobilityState(ESubDroneMobilityState NewState)
{
	if (NewState == MobilityState)
	{
		return;
	}
	const ESubDroneMobilityState OldState = MobilityState;
	MobilityState = NewState;
	MobilityStateTime = 0.f;

	UE_LOG(LogSubDrone, Verbose, TEXT("%s mobility %s -> %s"), *GetName(),
		*UEnum::GetValueAsString(OldState), *UEnum::GetValueAsString(NewState));

	OnMobilityStateEntered(NewState, OldState);
	BP_OnMobilityStateChanged(NewState, OldState);
	OnMobilityChanged.Broadcast(this, NewState, OldState);
}

void ASubDroneBase::AttachToDock()
{
	USceneComponent* HostRoot = Bay.IsValid() ? Bay->GetHostRoot() : nullptr;
	if (!HostRoot)
	{
		return;
	}
	AttachToComponent(HostRoot, FAttachmentTransformRules::KeepWorldTransform);
	Velocity = FVector::ZeroVector;
	CollisionSphere->ComponentVelocity = FVector::ZeroVector;
	bDockSettled = false;
}

void ASubDroneBase::DetachFromDock()
{
	if (GetAttachParentActor())
	{
		DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
	}
}

// -------------------------------------------------------------------------------------- tick
void ASubDroneBase::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!HostPawn.IsValid() || !Bay.IsValid() || DeltaSeconds <= 0.f)
	{
		return;
	}
	MobilityStateTime += DeltaSeconds;

	const float TargetBlend = MobilityState == ESubDroneMobilityState::Deployed ? 1.f : 0.f;
	DeployBlend = FMath::IsNearlyEqual(DeployBlend, TargetBlend, 1e-3f) ? TargetBlend : DampTo(DeployBlend, TargetBlend, DeployTransitionHalfLife, DeltaSeconds);
	const FSubDroneMotionProfile Profile = FSubDroneMotionProfile::Lerp(FormationMotion, DeployedMotion, FMath::SmoothStep(0.f, 1.f, DeployBlend));

	UpdateHostFrame(DeltaSeconds, Profile);

	switch (MobilityState)
	{
	case ESubDroneMobilityState::Docked:  TickDocked(DeltaSeconds);         break;
	case ESubDroneMobilityState::Docking: TickDocking(DeltaSeconds);        break;
	default:                              TickFree(DeltaSeconds, Profile);  break;
	}
}

void ASubDroneBase::UpdateHostFrame(float Dt, const FSubDroneMotionProfile& Profile)
{
	// Pitch + yaw of the Shell are followed, roll only partially; the result is low-pass filtered,
	// so a violent Shell turn becomes a smooth orbit of the slot instead of a jerk.
	const FQuat HostQ = HostPawn->GetActorQuat();
	const FQuat Leveled = MakeLookQuat(HostQ.GetForwardVector(), FVector::UpVector, FilteredHostFrame);
	const FQuat Target = FQuat::Slerp(Leveled, HostQ, Profile.HostRollInfluence);
	FilteredHostFrame = DampQuat(FilteredHostFrame, Target, Profile.HostFrameHalfLife, Dt);
}

void ASubDroneBase::TickFree(float Dt, const FSubDroneMotionProfile& Profile)
{
	const float B = FMath::SmoothStep(0.f, 1.f, DeployBlend);

	// Formation crescent -> working position, with a swoop arc only while transitioning.
	FVector Offset = FMath::Lerp(Bay->GetFormationOffset(SlotIndex), Bay->GetCombatOffset(SlotIndex), B);
	Offset.Z += DeployArcHeight * FMath::Sin(PI * B);

	// Organic float folded into the goal: the spring smooths it, no extra transform updates.
	BobTime += Dt;
	const float T = BobTime * Profile.BobFrequency;
	Offset += FVector(0.5f * FMath::PerlinNoise1D(T + BobSeed), FMath::PerlinNoise1D(0.83f * T + BobSeed + 17.f),
		FMath::Sin(2.f * PI * T + BobSeed)) * Profile.BobAmplitude;

	const FVector Goal = HostPawn->GetActorLocation() + FilteredHostFrame.RotateVector(Offset);
	const FVector GoalVel = Bay->GetHostVelocity() * VelocityFeedForward;
	const float Dist = static_cast<float>(FVector::Dist(GetActorLocation(), Goal));

	if (Dist > TeleportDistance)
	{
		SetActorLocationAndRotation(Goal, FilteredHostFrame, false, nullptr, ETeleportType::TeleportPhysics);
		Velocity = GoalVel;
		return;
	}

	const float Zone = FMath::SmoothStep(Profile.ComfortRadius, FMath::Max(Profile.LeashRadius, Profile.ComfortRadius + 1.f), Dist);
	const float HalfLife = FMath::Lerp(Profile.ComfortHalfLife, Profile.CatchUpHalfLife, Zone);

	FQuat Facing = FilteredHostFrame;
	GetDesiredFacing(Facing);
	MoveKinematic(Goal, GoalVel, HalfLife, Dt, /*bApplyCeiling*/ true, Facing, Profile.OrientationHalfLife);
}

void ASubDroneBase::TickDocking(float Dt)
{
	const FTransform Dock = Bay->GetDockWorldTransform(SlotIndex);
	// No water ceiling: the dock may be above water when the Shell is surfaced.
	MoveKinematic(Dock.GetLocation(), Bay->GetHostVelocity(), DockingHalfLife, Dt, false, Dock.GetRotation(), 0.15f);

	if (FVector::DistSquared(GetActorLocation(), Dock.GetLocation()) < FMath::Square(DockSnapDistance))
	{
		AttachToDock();
		SetMobilityState(ESubDroneMobilityState::Docked);
	}
}

void ASubDroneBase::TickDocked(float Dt)
{
	if (bDockSettled)
	{
		return;
	}
	const FTransform Target = Bay->GetDockRelativeTransform(SlotIndex);
	const FTransform Current = RootComponent->GetRelativeTransform();

	FVector Loc = DampTo(Current.GetLocation(), Target.GetLocation(), DockSettleHalfLife, Dt);
	FQuat Rot = DampQuat(Current.GetRotation(), Target.GetRotation(), DockSettleHalfLife, Dt);
	if (FVector::DistSquared(Loc, Target.GetLocation()) < 0.01 && Rot.AngularDistance(Target.GetRotation()) < 1e-3)
	{
		Loc = Target.GetLocation();
		Rot = Target.GetRotation();
		bDockSettled = true;
	}
	RootComponent->SetRelativeLocationAndRotation(Loc, Rot);
}

void ASubDroneBase::MoveKinematic(const FVector& Goal, const FVector& GoalVel, float HalfLife, float Dt, bool bApplyCeiling, const FQuat& FacingTarget, float FacingHalfLife)
{
	const FVector OldPos = GetActorLocation();
	FVector X = OldPos;
	FVector V = Velocity;

	CriticalSpring(X, V, Goal, GoalVel, HalfLife, Dt);

	const FVector Rel = V - GoalVel;
	if (Rel.SizeSquared() > FMath::Square(MaxRelativeSpeed))
	{
		V = GoalVel + Rel.GetSafeNormal() * MaxRelativeSpeed;
	}

	if (bApplyCeiling)
	{
		const double Ceiling = GetCachedWaterSurfaceZ(X, Dt) - SurfaceClearance;
		if (X.Z > Ceiling)
		{
			X.Z = Ceiling;
			V.Z = FMath::Min(V.Z, 0.0);
		}
	}

	const FQuat NewRot = DampQuat(GetActorQuat(), FacingTarget, FacingHalfLife, Dt);

	// Single swept move per frame (location + rotation together -> one hierarchy update).
	FHitResult Hit;
	SetActorLocationAndRotation(X, NewRot, true, &Hit);
	if (Hit.bBlockingHit)
	{
		if (Hit.bStartPenetrating)
		{
			SetActorLocation(X, false, nullptr, ETeleportType::TeleportPhysics);
		}
		else
		{
			const FVector N = Hit.Normal;
			V -= N * FMath::Min(0.0, FVector::DotProduct(V, N));
			const FVector Remaining = (X - OldPos) * (1.0 - Hit.Time);
			AddActorWorldOffset(FVector::VectorPlaneProject(Remaining, N), true);
		}
	}

	Velocity = V;
	CollisionSphere->ComponentVelocity = Velocity; // makes AActor::GetVelocity() meaningful
}

float ASubDroneBase::GetCachedWaterSurfaceZ(const FVector& At, float Dt)
{
	WaterCacheTimer -= Dt;
	if (!bHasWaterCache || WaterCacheTimer <= 0.f || FVector::DistSquared2D(At, LastWaterQueryPos) > FMath::Square(300.0))
	{
		CachedWaterZ = Bay->QueryWaterSurfaceZ(At);
		LastWaterQueryPos = At;
		WaterCacheTimer = 0.2f;
		bHasWaterCache = true;
	}
	return CachedWaterZ;
}
