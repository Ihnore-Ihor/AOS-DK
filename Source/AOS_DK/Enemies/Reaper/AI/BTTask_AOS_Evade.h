#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/BTTaskNode.h"
#include "BTTask_AOS_Evade.generated.h"

struct FAOSEvadeMemory : public FBTTaskMemory
{
	float Elapsed = 0.f;
};

/**
 * Behavior Tree side of the distance-proportional evasion (spec 5.1 branch [1], 5.7, section 6).
 *
 * UAOS_EvasionComponent owns the roll (P_dodge from the salvo launch distance, one seeded roll per salvo) and the execution:
 * the 340 cm lateral skitter (0.45 s root-motion move), the AAOS_CavitationDecoy launch from the tube on the threat side and the
 * AMicroTorpedo::Retarget of the in-flight salvo. When a dodge starts it raises bIsEvading; this task is the branch that
 * takes over the Reaper for that window: it cancels the path, hands the arm and phase to the evasion, and holds the branch
 * until the component clears bIsEvading (1.0 s safety timeout).
 */
UCLASS()
class AOS_DK_API UBTTask_AOS_Evade : public UBTTaskNode
{
	GENERATED_BODY()

public:
	UBTTask_AOS_Evade();

	/** Safety timeout in case the evasion component never clears the flag (spec 5.7: 1.0 s). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0.1", Units = "s"))
	float SafetyTimeout = 1.f;

protected:
	virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual EBTNodeResult::Type AbortTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual void TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds) override;
	virtual uint16 GetInstanceMemorySize() const override { return sizeof(FAOSEvadeMemory); }
	virtual FString GetStaticDescription() const override;
};
