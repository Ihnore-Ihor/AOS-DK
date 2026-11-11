#include "BTTask_AOS_Evade.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIController.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIEnemyCharacter.h"
#include "AOS_DK/Enemies/Reaper/AOS_EvasionComponent.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperTypes.h"
#include "BehaviorTree/BehaviorTreeComponent.h"

UBTTask_AOS_Evade::UBTTask_AOS_Evade()
{
	NodeName = TEXT("Evade (skitter + decoy)");
	INIT_TASK_NODE_NOTIFY_FLAGS();
}

FString UBTTask_AOS_Evade::GetStaticDescription() const
{
	return FString::Printf(TEXT("Holds while UAOS_EvasionComponent skitters 340 cm and launches the decoy\ntimeout %.1f s"), SafetyTimeout);
}

EBTNodeResult::Type UBTTask_AOS_Evade::ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	FAOSEvadeMemory* Memory = CastInstanceNodeMemory<FAOSEvadeMemory>(NodeMemory);
	Memory->Elapsed = 0.f;

	AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	const UAOS_EvasionComponent* Evasion = R ? R->GetEvasion() : nullptr;
	if (!R || !Evasion || R->IsDead())
	{
		return EBTNodeResult::Failed;
	}
	if (!Evasion->IsEvading())
	{
		return EBTNodeResult::Succeeded;   // the dodge ended before the tree reacted
	}

	AIC->StopMovement();      // the skitter is a root-motion move, the path must not fight it
	R->AbortStrike();         // no-op unless a strike is running (the component already did this on a dodge)
	R->SetPhase(EAOSReaperPhase::Evading);
	return EBTNodeResult::InProgress;
}

EBTNodeResult::Type UBTTask_AOS_Evade::AbortTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
	return EBTNodeResult::Aborted;   // the skitter itself is owned by the component and finishes on its own timer
}

void UBTTask_AOS_Evade::TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds)
{
	FAOSEvadeMemory* Memory = CastInstanceNodeMemory<FAOSEvadeMemory>(NodeMemory);
	Memory->Elapsed += DeltaSeconds;

	const AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	const AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	const UAOS_EvasionComponent* Evasion = R ? R->GetEvasion() : nullptr;
	if (!R || !Evasion || R->IsDead())
	{
		FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
		return;
	}
	if (!Evasion->IsEvading() || Memory->Elapsed >= SafetyTimeout)
	{
		FinishLatentTask(OwnerComp, EBTNodeResult::Succeeded);
	}
}
