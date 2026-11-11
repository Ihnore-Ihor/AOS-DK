#include "BTTask_AOS_MeleeStrike.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIController.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIEnemyCharacter.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperTypes.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "BehaviorTree/BlackboardComponent.h"

UBTTask_AOS_MeleeStrike::UBTTask_AOS_MeleeStrike()
{
	NodeName = TEXT("Arc Pike Strike");
	INIT_TASK_NODE_NOTIFY_FLAGS();
}

FString UBTTask_AOS_MeleeStrike::GetStaticDescription() const
{
	return TEXT("0.45 s telegraph -> 0.18 s swept strike -> 0.60 s recovery\n5 % core energy per hit");
}

bool UBTTask_AOS_MeleeStrike::TryBeginStrike(UBehaviorTreeComponent& OwnerComp) const
{
	AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	const UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (!R || !BB || !R->CanStrike())
	{
		return false;
	}
	const AShellPawn* Shell = Cast<AShellPawn>(BB->GetValueAsObject(AOSReaperBB::TargetActor));
	FVector Closest = FVector::ZeroVector;
	bool bInEnvelope = false;
	bool bAboveReach = false;
	if (!Shell || !AIC->ComputeEnvelope(Shell, Closest, bInEnvelope, bAboveReach) || !bInEnvelope)
	{
		return false;
	}
	R->SetLocomotionMode(EAOSLocomotionMode::Combat);
	return R->RequestStrike(Shell, Closest);   // commits the line arm turret -> closest hull point
}

EBTNodeResult::Type UBTTask_AOS_MeleeStrike::ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	FAOSMeleeStrikeMemory* Memory = CastInstanceNodeMemory<FAOSMeleeStrikeMemory>(NodeMemory);
	Memory->WaitedForCooldown = 0.f;
	Memory->bStrikeStarted = false;

	const AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	const AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	if (!R || R->IsDead() || !OwnerComp.GetBlackboardComponent())
	{
		return EBTNodeResult::Failed;
	}
	Memory->bStrikeStarted = TryBeginStrike(OwnerComp);
	return EBTNodeResult::InProgress;
}

EBTNodeResult::Type UBTTask_AOS_MeleeStrike::AbortTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	// A strike that has started is committed (spec 5.6); the Reaper's own timeline finishes it, and the evasion
	// component aborts it explicitly when a dodge starts.
	return EBTNodeResult::Aborted;
}

void UBTTask_AOS_MeleeStrike::TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds)
{
	FAOSMeleeStrikeMemory* Memory = CastInstanceNodeMemory<FAOSMeleeStrikeMemory>(NodeMemory);
	const AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	const AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	if (!R || R->IsDead())
	{
		FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
		return;
	}

	if (Memory->bStrikeStarted)
	{
		if (!R->IsStriking())   // recovery finished (or the evasion component aborted the strike)
		{
			FinishLatentTask(OwnerComp, EBTNodeResult::Succeeded);
		}
		return;
	}

	if (R->IsStriking())   // somebody else started it; just wait for it to end
	{
		return;
	}
	if (TryBeginStrike(OwnerComp))
	{
		Memory->bStrikeStarted = true;
		return;
	}
	Memory->WaitedForCooldown += DeltaSeconds;
	if (Memory->WaitedForCooldown > MaxCooldownWait)
	{
		FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
	}
}
