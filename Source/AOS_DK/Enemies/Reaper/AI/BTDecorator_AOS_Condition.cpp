#include "BTDecorator_AOS_Condition.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "BehaviorTree/BlackboardComponent.h"

UBTDecorator_AOS_Condition::UBTDecorator_AOS_Condition()
{
	NodeName = TEXT("AOS Condition");
}

void UBTDecorator_AOS_Condition::Configure(FName KeyName, EAOSBTCondition InCondition, EAOSThreatLevel InMinThreat, EBTFlowAbortMode::Type InAbortMode)
{
	BlackboardKey.SelectedKeyName = KeyName;
	Condition = InCondition;
	MinThreat = InMinThreat;
	FlowAbortMode = InAbortMode;
}

bool UBTDecorator_AOS_Condition::CalculateRawConditionValue(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) const
{
	const UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	if (!BB)
	{
		return false;
	}
	switch (Condition)
	{
	case EAOSBTCondition::BoolTrue:
		return BB->GetValueAsBool(BlackboardKey.SelectedKeyName);
	case EAOSBTCondition::ThreatAtLeast:
		return BB->GetValueAsEnum(BlackboardKey.SelectedKeyName) >= static_cast<uint8>(MinThreat);
	default:
		return false;
	}
}

FString UBTDecorator_AOS_Condition::GetStaticDescription() const
{
	const FString KeyName = BlackboardKey.SelectedKeyName.ToString();
	if (Condition == EAOSBTCondition::ThreatAtLeast)
	{
		return FString::Printf(TEXT("%s >= %s"), *KeyName, *UEnum::GetValueAsString(MinThreat));
	}
	return FString::Printf(TEXT("%s is true"), *KeyName);
}
