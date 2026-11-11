#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/BTTaskNode.h"
#include "BTTask_AOS_MeleeStrike.generated.h"

struct FAOSMeleeStrikeMemory : public FBTTaskMemory
{
	float WaitedForCooldown = 0.f;
	bool bStrikeStarted = false;
};

/**
 * SIGKILL arc-pike strike (spec 5.6). Commits the strike on the Reaper (AAOS_AIEnemyCharacter owns the timeline and the arm
 * pose):  0.45 s telegraph (sensor flare, pike Pink -> Red)  ->  0.18 s thrust (AAOS_AIWeapon swept sphere, one hit per swing,
 * AShellPawn::TakeDamage = 5 % of core energy)  ->  0.60 s recovery.  Waits out the 1.5 s cooldown in place; succeeds when the
 * recovery ends. A strike that is already in its wind-up is committed: an observer abort lets it finish (the thrust then misses
 * if the Shell has left the envelope, spec 5.6).
 */
UCLASS()
class AOS_DK_API UBTTask_AOS_MeleeStrike : public UBTTaskNode
{
	GENERATED_BODY()

public:
	UBTTask_AOS_MeleeStrike();

	/** Longest wait for the strike cooldown before the task gives the branch back to the tree. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Strike", meta = (ClampMin = "0", Units = "s"))
	float MaxCooldownWait = 3.f;

protected:
	virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual EBTNodeResult::Type AbortTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual void TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds) override;
	virtual uint16 GetInstanceMemorySize() const override { return sizeof(FAOSMeleeStrikeMemory); }
	virtual FString GetStaticDescription() const override;

private:
	/** Starts the strike if the Reaper may strike right now. Returns true when a strike was committed. */
	bool TryBeginStrike(UBehaviorTreeComponent& OwnerComp) const;
};
