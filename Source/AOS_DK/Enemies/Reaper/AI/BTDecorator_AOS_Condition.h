#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/Decorators/BTDecorator_BlackboardBase.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperTypes.h"
#include "BTDecorator_AOS_Condition.generated.h"

UENUM(BlueprintType)
enum class EAOSBTCondition : uint8
{
	/** The selected Bool key is true. */
	BoolTrue,
	/** The selected EAOSThreatLevel key is >= MinThreat. */
	ThreatAtLeast
};

/**
 * One decorator for every Reaper gate of BT_OOMReaper (ThreatLevel >= Hostile, bInStrikeEnvelope, bTargetAboveReach, bIsEvading).
 * Derives from UBTDecorator_BlackboardBase, so the key observer and the observer aborts (spec 5.1) come from the engine.
 */
UCLASS()
class AOS_DK_API UBTDecorator_AOS_Condition : public UBTDecorator_BlackboardBase
{
	GENERATED_BODY()

public:
	UBTDecorator_AOS_Condition();

	/** Native tree builder entry point (editor-authored trees set the same values in the details panel). */
	void Configure(FName KeyName, EAOSBTCondition InCondition, EAOSThreatLevel InMinThreat, EBTFlowAbortMode::Type InAbortMode);

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|BT")
	EAOSBTCondition Condition = EAOSBTCondition::BoolTrue;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|BT", meta = (EditCondition = "Condition == EAOSBTCondition::ThreatAtLeast"))
	EAOSThreatLevel MinThreat = EAOSThreatLevel::Hostile;

protected:
	virtual bool CalculateRawConditionValue(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) const override;
	virtual FString GetStaticDescription() const override;
};
