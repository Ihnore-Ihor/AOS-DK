#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBase.h"

#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneMath.h"
#include "Components/SphereComponent.h"
#include "Engine/World.h"
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
	SetPhasing(false);
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

	// Slot on the Shell's side of any wall (a rock between Shell and slot never becomes the goal).
	const FVector Goal = ClipGoalToShell(HostPawn->GetActorLocation() + FilteredHostFrame.RotateVector(Offset));
	const FVector GoalVel = Bay->GetHostVelocity() * VelocityFeedForward;
	const float Dist = static_cast<float>(FVector::Dist(GetActorLocation(), Goal));

	if (Dist > TeleportDistance)
	{
		SetActorLocationAndRotation(FindRescuePoint(Goal), FilteredHostFrame, false, nullptr, ETeleportType::TeleportPhysics);
		Velocity = GoalVel;
		SetPhasing(false);
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
	const float MaxRel = bPhasing ? FMath::Min(MaxRelativeSpeed, PhaseSpeed) : MaxRelativeSpeed;
	if (Rel.SizeSquared() > FMath::Square(MaxRel))
	{
		V = GoalVel + Rel.GetSafeNormal() * MaxRel;
		if (bPhasing)
		{
			X = OldPos + V * Dt; // steady glide through the obstacle
		}
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

	if (bPhasing)
	{
		// Unstuck: follow the spring path WITHOUT collision until the drone is in free water again.
		SetActorLocationAndRotation(X, NewRot, false, nullptr, ETeleportType::TeleportPhysics);
		Velocity = V;
		CollisionSphere->ComponentVelocity = Velocity;
		UpdatePhasing(Goal, Dt);
		return;
	}

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

	if (bEnableUnstuck)
	{
		UpdateStuckWatchdog(OldPos, X, Hit.bBlockingHit, Goal, Dt);
	}
}

// -------------------------------------------------------------------------------------- unstuck
FCollisionQueryParams ASubDroneBase::MakeUnstuckQueryParams() const
{
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SubDroneUnstuck), false, this);
	if (const APawn* Host = HostPawn.Get())
	{
		Params.AddIgnoredActor(Host);
	}
	return Params;
}

bool ASubDroneBase::IsBlockedAt(const FVector& Location) const
{
	const UWorld* World = GetWorld();
	return World && World->OverlapBlockingTestByChannel(Location, FQuat::Identity, CollisionSphere->GetCollisionObjectType(),
		FCollisionShape::MakeSphere(CollisionSphere->GetScaledSphereRadius()), MakeUnstuckQueryParams(),
		FCollisionResponseParams(CollisionSphere->GetCollisionResponseToChannels()));
}

bool ASubDroneBase::SweepBlocked(const FVector& From, const FVector& To, FHitResult& OutHit) const
{
	const UWorld* World = GetWorld();
	return World && World->SweepSingleByChannel(OutHit, From, To, FQuat::Identity, CollisionSphere->GetCollisionObjectType(),
		FCollisionShape::MakeSphere(CollisionSphere->GetScaledSphereRadius()), MakeUnstuckQueryParams(),
		FCollisionResponseParams(CollisionSphere->GetCollisionResponseToChannels()));
}

FVector ASubDroneBase::ClipGoalToShell(const FVector& Goal) const
{
	const APawn* Host = HostPawn.Get();
	if (!bClipGoalToShellVisibility || !Host)
	{
		return Goal;
	}
	const FVector From = Host->GetActorLocation();
	FHitResult Hit;
	if (!SweepBlocked(From, Goal, Hit) || Hit.bStartPenetrating)
	{
		return Goal; // clear line (or the Shell itself scrapes geometry: keep the nominal slot)
	}
	// Free spot just before the first obstacle, on the Shell's side.
	return FVector(Hit.Location) - (Goal - From).GetSafeNormal() * 5.0;
}

FVector ASubDroneBase::FindRescuePoint(const FVector& PreferredGoal) const
{
	const FVector Clipped = ClipGoalToShell(PreferredGoal);
	if (!IsBlockedAt(Clipped))
	{
		return Clipped;
	}
	const APawn* Host = HostPawn.Get();
	const FVector H = Host ? Host->GetActorLocation() : GetActorLocation();
	const FVector Up = FilteredHostFrame.GetUpVector();
	const FVector Right = FilteredHostFrame.GetRightVector();
	const FVector Forward = FilteredHostFrame.GetForwardVector();
	const FVector Candidates[] = { H + Up * 220.0, H + Right * 260.0, H - Right * 260.0, H + Forward * 450.0, H - Up * 220.0 };
	for (const FVector& Candidate : Candidates)
	{
		const FVector Point = ClipGoalToShell(Candidate);
		if (!IsBlockedAt(Point))
		{
			return Point;
		}
	}
	return H + Up * 220.0;
}

void ASubDroneBase::SetPhasing(bool bNewPhasing)
{
	StuckTime = 0.f;
	LostTime = 0.f;
	PhaseTime = 0.f;
	PhaseCheckTimer = 0.f;
	if (bPhasing == bNewPhasing)
	{
		return;
	}
	bPhasing = bNewPhasing;
	UE_LOG(LogSubDrone, Log, TEXT("%s %s"), *GetName(), bPhasing ? TEXT("stuck -> phasing through geometry") : TEXT("free water again"));
	BP_OnPhaseShift(bPhasing);
}

void ASubDroneBase::RescueTeleport(const FVector& PreferredGoal)
{
	const FVector From = GetActorLocation();
	const FVector To = FindRescuePoint(PreferredGoal);
	SetActorLocation(To, false, nullptr, ETeleportType::TeleportPhysics);
	Velocity = Bay.IsValid() ? Bay->GetHostVelocity() : FVector::ZeroVector;
	CollisionSphere->ComponentVelocity = Velocity;
	UE_LOG(LogSubDrone, Log, TEXT("%s rescue teleport (%.0f cm)"), *GetName(), FVector::Dist(From, To));
	SetPhasing(false);
	BP_OnRescueTeleport(From, To);
}

void ASubDroneBase::UpdateStuckWatchdog(const FVector& OldPos, const FVector& IntendedPos, bool bBlocked, const FVector& Goal, float Dt)
{
	const FVector Pos = GetActorLocation();
	const double GoalDistSq = FVector::DistSquared(Pos, Goal);
	if (GoalDistSq <= FMath::Square(StuckGoalTolerance))
	{
		StuckTime = 0.f;
		LostTime = 0.f;
		return;
	}

	// 1) Pressed against geometry: the swept move achieves only a fraction of the spring step.
	const double Intended = FVector::Dist(OldPos, IntendedPos);
	const double Achieved = FVector::Dist(OldPos, Pos);
	const bool bNoProgress = bBlocked && Intended > 0.2 && Achieved < Intended * StuckProgressRatio;
	StuckTime = bNoProgress ? StuckTime + Dt : FMath::Max(0.f, StuckTime - 2.f * Dt);

	// 2) Lost: far behind with an obstacle in between (e.g. endlessly sliding along a cliff face).
	LostCheckTimer -= Dt;
	if (LostCheckTimer <= 0.f)
	{
		LostCheckTimer = 0.25f;
		FHitResult Hit;
		bLastPathClear = !SweepBlocked(Pos, Goal, Hit);
	}
	const float Leash = FMath::Max(FormationMotion.LeashRadius, DeployedMotion.LeashRadius);
	LostTime = (GoalDistSq > FMath::Square(Leash) && !bLastPathClear) ? LostTime + Dt : 0.f;

	if (StuckTime >= StuckTimeToPhase || LostTime >= LostTimeToPhase)
	{
		SetPhasing(true);
	}
}

void ASubDroneBase::UpdatePhasing(const FVector& Goal, float Dt)
{
	PhaseTime += Dt;
	PhaseCheckTimer -= Dt;
	if (PhaseCheckTimer <= 0.f)
	{
		PhaseCheckTimer = 0.08f;
		const FVector Pos = GetActorLocation();
		if (!IsBlockedAt(Pos))
		{
			FHitResult Hit;
			if (FVector::DistSquared(Pos, Goal) <= FMath::Square(StuckGoalTolerance) || !SweepBlocked(Pos, Goal, Hit))
			{
				SetPhasing(false); // out of the rock with a clear run to the slot
				return;
			}
		}
	}
	if (PhaseTime >= MaxPhaseTime)
	{
		RescueTeleport(Goal);
	}
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
