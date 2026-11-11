#include "BTTask_AOS_Pursue.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIController.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIEnemyCharacter.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperTypes.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "Navigation/PathFollowingComponent.h"
#include "AOS_DK/Enemies/Reaper/Hazard/AOS_NavFilter_ReaperChase.h"

UBTTask_AOS_Pursue::UBTTask_AOS_Pursue()
{
	NodeName = TEXT("Pursue");
	INIT_TASK_NODE_NOTIFY_FLAGS();
}

FString UBTTask_AOS_Pursue::GetStaticDescription() const
{
	return FString::Printf(TEXT("%s TargetGroundPoint (accept %.0f cm)"), bShadow ? TEXT("Shadow (Combat gait)") : TEXT("Chase (Scuttle gait)"), AcceptanceRadius);
}

bool UBTTask_AOS_Pursue::IssueMove(UBehaviorTreeComponent& OwnerComp, FAOSPursueMemory& Memory, const FVector& Ground) const
{
	AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	if (!AIC)
	{
		return false;
	}
	Memory.Destination = Ground;
	Memory.RepathTimer = 0.f;
	const EPathFollowingRequestResult::Type Result = // Hostile pursuit: brine costs 1.0 (tunnel vision); patrol / investigate keep the default filter (brine x3 -> detour).
	AIC->MoveToLocation(Ground, AcceptanceRadius, true, true, false, true, UAOS_NavFilter_ReaperChase::StaticClass(), true);
	return Result != EPathFollowingRequestResult::Failed;
}

EBTNodeResult::Type UBTTask_AOS_Pursue::ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	FAOSPursueMemory* Memory = CastInstanceNodeMemory<FAOSPursueMemory>(NodeMemory);
	Memory->PathFailTime = 0.f;

	const AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	const UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (!R || !BB || R->IsDead())
	{
		return EBTNodeResult::Failed;
	}
	const FVector Ground = BB->GetValueAsVector(AOSReaperBB::TargetGroundPoint);
	if (Ground.IsNearlyZero())
	{
		return EBTNodeResult::Failed;
	}
	R->SetLocomotionMode(bShadow ? EAOSLocomotionMode::Combat : EAOSLocomotionMode::Scuttle);
	R->SetPhase(bShadow ? EAOSReaperPhase::Shadow : EAOSReaperPhase::Chase);
	if (!IssueMove(OwnerComp, *Memory, Ground) && !bShadow)
	{
		Memory->PathFailTime = 0.01f;
	}
	return EBTNodeResult::InProgress;
}

EBTNodeResult::Type UBTTask_AOS_Pursue::AbortTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	if (AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner()))
	{
		AIC->StopMovement();
	}
	return EBTNodeResult::Aborted;
}

void UBTTask_AOS_Pursue::TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds)
{
	FAOSPursueMemory* Memory = CastInstanceNodeMemory<FAOSPursueMemory>(NodeMemory);
	const AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	const AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	const UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (!R || !BB || R->IsDead())
	{
		FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
		return;
	}
	if (R->IsStriking() || R->IsSkittering())
	{
		return;   // the strike / skitter owns the body
	}

	Memory->RepathTimer += DeltaSeconds;
	if (Memory->RepathTimer < RepathInterval)
	{
		return;
	}
	Memory->RepathTimer = 0.f;

	const FVector Ground = BB->GetValueAsVector(AOSReaperBB::TargetGroundPoint);
	const bool bIdle = AIC->GetMoveStatus() == EPathFollowingStatus::Idle;
	const bool bMoved = FVector::DistSquared(Ground, Memory->Destination) > FMath::Square(RepathDistance);
	const bool bFar = FVector::DistSquared(Ground, R->GetActorLocation()) > FMath::Square(AcceptanceRadius + 150.f);
	if (bMoved || (bIdle && bFar))
	{
		if (IssueMove(OwnerComp, *Memory, Ground))
		{
			Memory->PathFailTime = 0.f;
		}
		else
		{
			Memory->PathFailTime += RepathInterval;
		}
	}
	if (!bShadow && Memory->PathFailTime > PathFailGrace)
	{
		FinishLatentTask(OwnerComp, EBTNodeResult::Failed);   // Shell over open water beyond the NavMesh
	}
}
