#include "BTTask_AOS_PatrolSurvey.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIController.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIEnemyCharacter.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperTypes.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Navigation/PathFollowingComponent.h"
#include "NavigationSystem.h"

namespace
{
	enum EStage : uint8 { StageMove = 0, StageTurn = 1, StageHold = 2 };

	// Spec 5.5 tables.
	constexpr float PatrolHeadings[5] = { -75.f, -35.f, 0.f, 35.f, 75.f };
	constexpr float InvestigateHeadings[7] = { -120.f, -80.f, -40.f, 0.f, 40.f, 80.f, 120.f };
	constexpr float PatrolTurnRate = 60.f;        // deg/s
	constexpr float InvestigateTurnRate = 90.f;   // deg/s
	constexpr float PatrolHold = 0.55f;           // s per heading (+ 0..0.2 s seeded jitter)
	constexpr float InvestigateHold = 0.45f;
	constexpr float PatrolMastAmp = 40.f;         // deg, at 0.8 Hz
	constexpr float InvestigateMastAmp = 50.f;    // deg, at 1.2 Hz
	constexpr float PatrolMastHz = 0.8f;
	constexpr float InvestigateMastHz = 1.2f;
	constexpr float PatrolLookUpPitch = 45.f;     // deg, 0.4 s at the start of the hold
	constexpr float InvestigateLookUpPitch = 55.f;
	constexpr float LookUpDuration = 0.4f;
	constexpr float MoveStuckTimeout = 45.f;      // s, then survey where we stand
	constexpr float TurnTimeout = 3.5f;           // s
	constexpr float TurnToleranceDeg = 4.f;
}

UBTTask_AOS_PatrolSurvey::UBTTask_AOS_PatrolSurvey()
{
	NodeName = TEXT("Patrol + Survey");
	INIT_TASK_NODE_NOTIFY_FLAGS();
}

FString UBTTask_AOS_PatrolSurvey::GetStaticDescription() const
{
	return Mode == EAOSSurveyMode::Patrol
		? TEXT("Walk to next patrol node, survey 5 headings\nmast sweep + look-up on alternate headings")
		: TEXT("Walk to InvestigateLocation, survey 7 headings\nlook-up on every heading, then clear suspicion");
}

bool UBTTask_AOS_PatrolSurvey::PickDestination(AAOS_AIController* AIC, AAOS_AIEnemyCharacter* R, UBlackboardComponent* BB, FVector& OutDestination) const
{
	if (Mode == EAOSSurveyMode::Investigate)
	{
		OutDestination = BB->GetValueAsVector(AOSReaperBB::InvestigateLocation);
		return true;
	}

	const TArray<TObjectPtr<AActor>>& Nodes = R->PatrolNodes;
	if (Nodes.Num() > 0)
	{
		int32 Index = BB->GetValueAsInt(AOSReaperBB::PatrolNodeIndex);
		for (int32 Attempt = 0; Attempt < Nodes.Num(); ++Attempt)
		{
			Index = (Index + 1) % Nodes.Num();
			if (const AActor* Node = Nodes[Index])
			{
				OutDestination = AIC->ProjectToNavBelow(Node->GetActorLocation());
				BB->SetValueAsInt(AOSReaperBB::PatrolNodeIndex, Index);
				BB->SetValueAsVector(AOSReaperBB::PatrolLocation, OutDestination);
				UE_LOG(LogAOSAI, Verbose, TEXT("oom_reaper[%d]: patrol -> node %s (#%d)"), R->GetPID(), *Node->GetName(), Index);
				return true;
			}
		}
	}

	// No nodes: random reachable point around the spawn (spec 4.6).
	if (UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(R->GetWorld()))
	{
		FNavLocation Random;
		if (Nav->GetRandomReachablePointInRadius(AIC->GetHomeLocation(), R->HomeRadius, Random))
		{
			OutDestination = Random.Location;
			BB->SetValueAsVector(AOSReaperBB::PatrolLocation, OutDestination);
			return true;
		}
	}
	return false;
}

void UBTTask_AOS_PatrolSurvey::BeginSurvey(AAOS_AIController* AIC, AAOS_AIEnemyCharacter* R, FAOSPatrolSurveyMemory::FState& S) const
{
	AIC->StopMovement();   // survey halt: the walker plants its feet
	R->SetPhase(EAOSReaperPhase::Survey);

	const bool bInvestigate = Mode == EAOSSurveyMode::Investigate;
	S.NumHeadings = bInvestigate ? 7 : 5;
	for (int32 i = 0; i < S.NumHeadings; ++i)
	{
		S.Headings[i] = bInvestigate ? InvestigateHeadings[i] : PatrolHeadings[i];
	}
	if (!bInvestigate)
	{
		// Seeded shuffle (spec 5.5): the order differs per Reaper and per survey, the run stays reproducible.
		FRandomStream Stream(R->GetPID() * 131 + FMath::FloorToInt(static_cast<float>(R->GetWorld()->GetTimeSeconds()) * 10.f));
		for (int32 i = S.NumHeadings - 1; i > 0; --i)
		{
			Swap(S.Headings[i], S.Headings[Stream.RandRange(0, i)]);
		}
	}
	S.HeadingIndex = 0;
	S.StageTime = 0.f;
	S.ArrivalYaw = static_cast<float>(R->GetActorRotation().Yaw);
	S.Stage = StageTurn;

	// In-place heavy turn: let the controller rotation drive the capsule at the survey turn rate.
	if (UCharacterMovementComponent* CMC = R->GetCharacterMovement())
	{
		if (!S.bMovementOverridden)
		{
			S.bSavedOrient = CMC->bOrientRotationToMovement;
			S.bSavedDesiredRotation = CMC->bUseControllerDesiredRotation;
			S.SavedRotationRate = CMC->RotationRate;
			S.bMovementOverridden = true;
		}
		CMC->bOrientRotationToMovement = false;
		CMC->bUseControllerDesiredRotation = true;
		CMC->RotationRate = FRotator(0.0, bInvestigate ? InvestigateTurnRate : PatrolTurnRate, 0.0);
	}
}

void UBTTask_AOS_PatrolSurvey::RestoreBody(AAOS_AIController* AIC, AAOS_AIEnemyCharacter* R, FAOSPatrolSurveyMemory::FState& S) const
{
	if (S.bMovementOverridden)
	{
		if (UCharacterMovementComponent* CMC = R->GetCharacterMovement())
		{
			CMC->bOrientRotationToMovement = S.bSavedOrient;
			CMC->bUseControllerDesiredRotation = S.bSavedDesiredRotation;
			CMC->RotationRate = S.SavedRotationRate;
		}
		S.bMovementOverridden = false;
		AIC->ClearFocus(EAIFocusPriority::Default);
	}
	R->SetMastSweep(0.f, 0.f);   // mast back to neutral
}

EBTNodeResult::Type UBTTask_AOS_PatrolSurvey::ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	FAOSPatrolSurveyMemory* Memory = CastInstanceNodeMemory<FAOSPatrolSurveyMemory>(NodeMemory);
	Memory->S = FAOSPatrolSurveyMemory::FState();

	AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (!AIC || !R || !BB || R->IsDead())
	{
		return EBTNodeResult::Failed;
	}

	const bool bInvestigate = Mode == EAOSSurveyMode::Investigate;
	R->SetLocomotionMode(bInvestigate ? EAOSLocomotionMode::Investigate : EAOSLocomotionMode::Walk);
	R->SetPhase(bInvestigate ? EAOSReaperPhase::Investigate : EAOSReaperPhase::Patrol);

	FVector Destination = FVector::ZeroVector;
	if (PickDestination(AIC, R, BB, Destination))
	{
		Memory->S.Destination = Destination;
		const float Acceptance = bInvestigate ? InvestigateAcceptanceRadius : PatrolAcceptanceRadius;
		const EPathFollowingRequestResult::Type Request = AIC->MoveToLocation(Destination, Acceptance, true, true, false, true, nullptr, true);
		if (Request == EPathFollowingRequestResult::RequestSuccessful)
		{
			Memory->S.Stage = StageMove;
			return EBTNodeResult::InProgress;
		}
	}
	// Already there, or no path / no destination: halt and survey where we stand.
	BeginSurvey(AIC, R, Memory->S);
	return EBTNodeResult::InProgress;
}

EBTNodeResult::Type UBTTask_AOS_PatrolSurvey::AbortTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	return EBTNodeResult::Aborted;   // OnTaskFinished restores the body and the mast
}

void UBTTask_AOS_PatrolSurvey::OnTaskFinished(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, EBTNodeResult::Type TaskResult)
{
	AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	if (!AIC || !R)
	{
		return;
	}
	FAOSPatrolSurveyMemory* Memory = CastInstanceNodeMemory<FAOSPatrolSurveyMemory>(NodeMemory);
	RestoreBody(AIC, R, Memory->S);
	if (TaskResult == EBTNodeResult::Aborted && Memory->S.Stage == StageMove)
	{
		AIC->StopMovement();
	}
}

void UBTTask_AOS_PatrolSurvey::TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds)
{
	FAOSPatrolSurveyMemory* Memory = CastInstanceNodeMemory<FAOSPatrolSurveyMemory>(NodeMemory);
	FAOSPatrolSurveyMemory::FState& S = Memory->S;
	AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (!AIC || !R || !BB || R->IsDead())
	{
		FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
		return;
	}
	if (R->IsSkittering())
	{
		return;   // evasion owns the body
	}

	const bool bInvestigate = Mode == EAOSSurveyMode::Investigate;
	S.StageTime += DeltaSeconds;
	S.TotalTime += DeltaSeconds;

	switch (S.Stage)
	{
	case StageMove:
	{
		if (bInvestigate)
		{
			// A fresh sound moved the investigation point: follow it.
			const FVector Latest = BB->GetValueAsVector(AOSReaperBB::InvestigateLocation);
			if (FVector::DistSquared(Latest, S.Destination) > FMath::Square(200.f))
			{
				S.Destination = Latest;
				AIC->MoveToLocation(Latest, InvestigateAcceptanceRadius, true, true, false, true, nullptr, true);
			}
		}
		if (AIC->GetMoveStatus() == EPathFollowingStatus::Idle || S.StageTime > MoveStuckTimeout)
		{
			BeginSurvey(AIC, R, S);
		}
		break;
	}
	case StageTurn:
	{
		const float TargetYaw = S.ArrivalYaw + S.Headings[S.HeadingIndex];
		AIC->SetFocalPoint(R->GetActorLocation() + FRotator(0.0, TargetYaw, 0.0).Vector() * 1000.0, EAIFocusPriority::Default);
		const float Delta = FMath::Abs(FMath::FindDeltaAngleDegrees(static_cast<float>(R->GetActorRotation().Yaw), TargetYaw));
		if (Delta <= TurnToleranceDeg || S.StageTime > TurnTimeout)
		{
			S.Stage = StageHold;
			S.StageTime = 0.f;
			FRandomStream Jitter(R->GetPID() * 7919 + S.HeadingIndex);
			S.HoldDuration = bInvestigate ? InvestigateHold : PatrolHold + Jitter.FRandRange(0.f, 0.2f);
		}
		break;
	}
	case StageHold:
	{
		const float Hz = bInvestigate ? InvestigateMastHz : PatrolMastHz;
		const float Amp = bInvestigate ? InvestigateMastAmp : PatrolMastAmp;
		const float SweepYaw = Amp * FMath::Sin(2.f * PI * Hz * S.TotalTime);
		// Look-up into the water column: every heading when investigating, alternate headings when patrolling.
		const bool bLookUp = bInvestigate || (S.HeadingIndex % 2 == 1);
		float Pitch = 0.f;
		if (bLookUp)
		{
			Pitch = bInvestigate ? InvestigateLookUpPitch : (S.StageTime < LookUpDuration ? PatrolLookUpPitch : 0.f);
		}
		R->SetMastSweep(SweepYaw, Pitch);

		if (S.StageTime >= S.HoldDuration)
		{
			++S.HeadingIndex;
			S.StageTime = 0.f;
			if (S.HeadingIndex >= S.NumHeadings)
			{
				UE_LOG(LogAOSAI, Verbose, TEXT("oom_reaper[%d]: survey: %d headings"), R->GetPID(), S.NumHeadings);
				if (bInvestigate && AIC->GetThreatLevel() == EAOSThreatLevel::Suspicious)
				{
					AIC->ClearThreat();   // nothing found: back to patrol
				}
				FinishLatentTask(OwnerComp, EBTNodeResult::Succeeded);
				return;
			}
			S.Stage = StageTurn;
		}
		break;
	}
	default:
		break;
	}
}
