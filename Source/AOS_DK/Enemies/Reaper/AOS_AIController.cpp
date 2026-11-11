#include "AOS_AIController.h"
#include "AOS_AIEnemyCharacter.h"
#include "AI/AOS_ReaperBehaviorTree.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "Perception/AIPerceptionComponent.h"
#include "Perception/AISenseConfig_Sight.h"
#include "Perception/AISenseConfig_Hearing.h"
#include "Perception/AISenseConfig_Damage.h"
#include "Perception/AISense_Sight.h"
#include "Perception/AISense_Hearing.h"
#include "Perception/AISense_Damage.h"
#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "BehaviorTree/BlackboardData.h"
#include "BrainComponent.h"
#include "Navigation/PathFollowingComponent.h"
#include "NavigationSystem.h"
#include "Components/BoxComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"

AAOS_AIController::AAOS_AIController()
{
	PrimaryActorTick.bCanEverTick = true;   // AAIController::Tick applies the focus / control rotation every frame
	SetGenericTeamId(FGenericTeamId(static_cast<uint8>(ReaperTeamId)));

	PerceptionComp = CreateDefaultSubobject<UAIPerceptionComponent>(TEXT("PerceptionComp"));
	SetPerceptionComponent(*PerceptionComp);

	SightConfig = CreateDefaultSubobject<UAISenseConfig_Sight>(TEXT("SightConfig"));
	SightConfig->SightRadius = SightRadius;
	SightConfig->LoseSightRadius = LoseSightRadius;
	SightConfig->PeripheralVisionAngleDegrees = SightHalfAngle;
	SightConfig->AutoSuccessRangeFromLastSeenLocation = 400.f;
	SightConfig->SetMaxAge(4.f);
	SightConfig->DetectionByAffiliation.bDetectEnemies = true;
	SightConfig->DetectionByAffiliation.bDetectNeutrals = true;
	SightConfig->DetectionByAffiliation.bDetectFriendlies = true;

	HearingConfig = CreateDefaultSubobject<UAISenseConfig_Hearing>(TEXT("HearingConfig"));
	HearingConfig->HearingRange = HearingRange;
	HearingConfig->SetMaxAge(4.f);
	HearingConfig->DetectionByAffiliation.bDetectEnemies = true;
	HearingConfig->DetectionByAffiliation.bDetectNeutrals = true;
	HearingConfig->DetectionByAffiliation.bDetectFriendlies = true;

	DamageConfig = CreateDefaultSubobject<UAISenseConfig_Damage>(TEXT("DamageConfig"));
	DamageConfig->SetMaxAge(6.f);

	PerceptionComp->ConfigureSense(*SightConfig);
	PerceptionComp->ConfigureSense(*HearingConfig);
	PerceptionComp->ConfigureSense(*DamageConfig);
	PerceptionComp->SetDominantSense(SightConfig->GetSenseImplementation());
	PerceptionComp->OnTargetPerceptionUpdated.AddDynamic(this, &AAOS_AIController::HandleTargetPerceptionUpdated);
}

void AAOS_AIController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	Reaper = Cast<AAOS_AIEnemyCharacter>(InPawn);
	HomeLocation = InPawn ? InPawn->GetActorLocation() : FVector::ZeroVector;
	TargetShell = nullptr;
	bHasLineOfSight = false;
	SetThreatLevel(EAOSThreatLevel::None);
	StartBehaviorTree();
}

void AAOS_AIController::StartBehaviorTree()
{
	// Spec 4.1: BehaviorTreeAsset if a designer assigned one, otherwise the native BT_OOMReaper (spec 5.1).
	UBehaviorTree* Tree = BehaviorTreeAsset;
	if (!Tree)
	{
		RuntimeTree = AOSReaperBT::BuildBehaviorTree(this);
		Tree = RuntimeTree;
	}
	if (!Tree || !Tree->BlackboardAsset)
	{
		UE_LOG(LogAOSAI, Error, TEXT("%s: no Behavior Tree / Blackboard, the Reaper will stand still"), *GetNameSafe(GetPawn()));
		return;
	}

	UBlackboardComponent* BlackboardComp = nullptr;
	if (!UseBlackboard(Tree->BlackboardAsset, BlackboardComp) || !BlackboardComp)
	{
		UE_LOG(LogAOSAI, Error, TEXT("%s: UseBlackboard failed"), *GetNameSafe(GetPawn()));
		return;
	}

	// Seed every key before the tree starts (the service refreshes them at 10 Hz).
	BlackboardComp->SetValueAsObject(AOSReaperBB::SelfActor, GetPawn());
	BlackboardComp->SetValueAsInt(AOSReaperBB::PatrolNodeIndex, -1);
	BlackboardComp->SetValueAsBool(AOSReaperBB::bInStrikeEnvelope, false);
	BlackboardComp->SetValueAsBool(AOSReaperBB::bTargetAboveReach, false);
	BlackboardComp->SetValueAsBool(AOSReaperBB::bIsEvading, false);
	BlackboardComp->SetValueAsBool(AOSReaperBB::bInHazard, false);
	BlackboardComp->SetValueAsFloat(AOSReaperBB::TargetDistance, 0.f);
	MirrorToBlackboard();

	bRunningBT = RunBehaviorTree(Tree);
	UE_LOG(LogAOSAI, Log, TEXT("%s: Behavior Tree %s (%s)"), *GetNameSafe(GetPawn()), bRunningBT ? TEXT("running") : TEXT("FAILED to start"),
		BehaviorTreeAsset ? TEXT("asset") : TEXT("native BT_OOMReaper"));
}

void AAOS_AIController::OnUnPossess()
{
	ShutDown();
	Super::OnUnPossess();
}

void AAOS_AIController::ShutDown()
{
	bShutDown = true;
	if (BrainComponent)
	{
		BrainComponent->StopLogic(TEXT("Dead"));
	}
	StopMovement();
	if (PerceptionComp)
	{
		PerceptionComp->SetSenseEnabled(UAISense_Sight::StaticClass(), false);
		PerceptionComp->SetSenseEnabled(UAISense_Hearing::StaticClass(), false);
		PerceptionComp->SetSenseEnabled(UAISense_Damage::StaticClass(), false);
	}
	SetActorTickEnabled(false);
}

ETeamAttitude::Type AAOS_AIController::GetTeamAttitudeTowards(const AActor& Other) const
{
	// Shell-1 is hostile; everything else (Lab 3 daemons, drones, torpedoes, other reapers) is ignored.
	return Cast<AShellPawn>(&Other) ? ETeamAttitude::Hostile : ETeamAttitude::Neutral;
}

bool AAOS_AIController::IsHostileActor(const AActor* Actor) const
{
	const AShellPawn* Shell = Cast<AShellPawn>(Actor);
	if (!Shell || Shell->IsSystemsHalted() || Shell->IsInLARSCradle())
	{
		return false;
	}
	return Cast<APlayerController>(Shell->GetController()) != nullptr;
}

AAOS_AIEnemyCharacter* AAOS_AIController::GetReaper() const
{
	return Reaper.Get();
}

AShellPawn* AAOS_AIController::GetTargetShell() const
{
	return TargetShell.Get();
}

float AAOS_AIController::GetSecondsSinceHeard() const
{
	return GetWorld() ? static_cast<float>(GetWorld()->GetTimeSeconds() - LastHeardTime) : 1000.f;
}

// ---------------------------------------------------------------------------------------------------------------------
// Perception
// ---------------------------------------------------------------------------------------------------------------------
void AAOS_AIController::SetSightDegradation(float RadiusScale, float HalfAngleDegrees)
{
	if (!SightConfig || !PerceptionComp)
	{
		return;
	}
	SightConfig->SightRadius = SightRadius * RadiusScale;
	SightConfig->LoseSightRadius = LoseSightRadius * RadiusScale;
	SightConfig->PeripheralVisionAngleDegrees = HalfAngleDegrees;
	PerceptionComp->ConfigureSense(*SightConfig);
	PerceptionComp->RequestStimuliListenerUpdate();
}

void AAOS_AIController::ResetSightDegradation()
{
	SetSightDegradation(1.f, SightHalfAngle);
}

void AAOS_AIController::HandleTargetPerceptionUpdated(AActor* Actor, FAIStimulus Stimulus)
{
	AAOS_AIEnemyCharacter* R = Reaper.Get();
	if (!R || R->IsDead() || bShutDown || !IsHostileActor(Actor))
	{
		return;
	}
	AShellPawn* Shell = Cast<AShellPawn>(Actor);
	const double Now = GetWorld()->GetTimeSeconds();

	if (Stimulus.Type == UAISense::GetSenseID<UAISense_Sight>())
	{
		if (Stimulus.WasSuccessfullySensed())
		{
			const bool bWasHostile = ThreatLevel == EAOSThreatLevel::Hostile;
			TargetShell = Shell;
			bHasLineOfSight = true;
			SetThreatLevel(EAOSThreatLevel::Hostile);
			R->SetLocomotionMode(EAOSLocomotionMode::Scuttle);   // same frame, no BT tick wait
			SetFocus(Actor, EAIFocusPriority::Gameplay);
			if (!bWasHostile)
			{
				R->PlaySpotReaction();
				R->ReportToShell(FString::Printf(TEXT("target acquired: shell-1 (%.0f m)"),
					FVector::Dist(Actor->GetActorLocation(), R->GetActorLocation()) / 100.f), EAOSHudLogSeverity::Warning);
			}
		}
		else
		{
			bHasLineOfSight = false;
			LastKnownLocation = Stimulus.StimulusLocation;
			LostSightTime = Now;
			LastSeenVelocity = Actor->GetVelocity();
		}
	}
	else
	{
		LastHeardTime = Now;
		if (ThreatLevel != EAOSThreatLevel::Hostile)
		{
			InvestigateLocation = ProjectToNavBelow(Stimulus.StimulusLocation);
			TargetShell = Shell;
			SetThreatLevel(EAOSThreatLevel::Suspicious);
			R->SetLocomotionMode(EAOSLocomotionMode::Investigate);
		}
		R->SetMastLookPoint(Stimulus.StimulusLocation);   // mast snaps toward the sound
	}
}

FVector AAOS_AIController::ProjectToNavBelow(const FVector& Location) const
{
	if (UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
	{
		FNavLocation Projected;
		if (Nav->ProjectPointToNavigation(Location, Projected, FVector(300.f, 300.f, 3000.f)))
		{
			return Projected.Location;
		}
	}
	return Location;
}

void AAOS_AIController::SetThreatLevel(EAOSThreatLevel NewLevel)
{
	ThreatLevel = NewLevel;
	if (NewLevel == EAOSThreatLevel::Suspicious)
	{
		SuspiciousSince = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	}
	if (NewLevel == EAOSThreatLevel::None)
	{
		ClearFocus(EAIFocusPriority::Gameplay);
	}
	MirrorToBlackboard();
}

void AAOS_AIController::MirrorToBlackboard()
{
	UBlackboardComponent* BB = GetBlackboardComponent();
	if (!BB)
	{
		return;
	}
	BB->SetValueAsEnum(AOSReaperBB::ThreatLevel, static_cast<uint8>(ThreatLevel));
	BB->SetValueAsObject(AOSReaperBB::TargetActor, TargetShell.Get());
	BB->SetValueAsBool(AOSReaperBB::bHasLineOfSight, bHasLineOfSight);
	BB->SetValueAsVector(AOSReaperBB::LastKnownLocation, LastKnownLocation);
	BB->SetValueAsVector(AOSReaperBB::InvestigateLocation, InvestigateLocation);
}

// ---------------------------------------------------------------------------------------------------------------------
// Behavior Tree support (spec 5.3)
// ---------------------------------------------------------------------------------------------------------------------
bool AAOS_AIController::ComputeEnvelope(const AShellPawn* Shell, FVector& OutClosest, bool& bOutInEnvelope, bool& bOutAboveReach) const
{
	const AAOS_AIEnemyCharacter* R = Reaper.Get();
	if (!R || !Shell)
	{
		return false;
	}
	const FVector A = R->GetArmTurretLocation();
	OutClosest = Shell->GetActorLocation();
	if (const UPrimitiveComponent* Root = Cast<UPrimitiveComponent>(Shell->GetRootComponent()))
	{
		FVector P;
		if (Root->GetClosestPointOnCollision(A, P) >= 0.f)
		{
			OutClosest = P;
		}
	}
	const FVector D = OutClosest - A;
	const double Dist = D.Size();
	const double ElevationDeg = FMath::RadiansToDegrees(FMath::Atan2(D.Z, FMath::Max(D.Size2D(), 1.0)));
	const double Azimuth = FMath::Abs(FMath::FindDeltaAngleDegrees(R->GetActorRotation().Yaw, FRotator(D.Rotation()).Yaw));
	bOutInEnvelope = Dist <= StrikeReach && ElevationDeg >= -10.0 && Azimuth <= 110.0;
	bOutAboveReach = !bOutInEnvelope && D.Size2D() <= ShadowRadius && OutClosest.Z > A.Z;
	return true;
}

void AAOS_AIController::LoseTarget(const FVector& InvestigateAt)
{
	AAOS_AIEnemyCharacter* R = Reaper.Get();
	TargetShell = nullptr;
	bHasLineOfSight = false;
	InvestigateLocation = InvestigateAt;
	SetThreatLevel(EAOSThreatLevel::Suspicious);
	if (R)
	{
		R->SetLocomotionMode(EAOSLocomotionMode::Investigate);
	}
	ClearFocus(EAIFocusPriority::Gameplay);
}

void AAOS_AIController::ClearThreat()
{
	AAOS_AIEnemyCharacter* R = Reaper.Get();
	TargetShell = nullptr;
	bHasLineOfSight = false;
	SetThreatLevel(EAOSThreatLevel::None);   // also clears the focus and mirrors to the Blackboard
	if (R)
	{
		R->SetLocomotionMode(EAOSLocomotionMode::Walk);
	}
}
