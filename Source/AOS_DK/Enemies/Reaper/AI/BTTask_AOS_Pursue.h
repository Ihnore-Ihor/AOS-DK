#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/BTTaskNode.h"
#include "BTTask_AOS_Pursue.generated.h"

struct FAOSPursueMemory : public FBTTaskMemory
{
	FVector Destination = FVector::ZeroVector;
	float RepathTimer = 0.f;
	float PathFailTime = 0.f;
};

/**
 * Engage movement (spec 5.7 ChaseTarget / ShadowTarget). Follows TargetGroundPoint (the Shell projected onto the NavMesh).
 * Chase: Scuttle gait, fails if no path for PathFailGrace seconds. Shadow (bShadow): Combat gait, keeps the Reaper under the
 * Shell, never fails and never damages by itself (area denial).
 */
UCLASS()
class AOS_DK_API UBTTask_AOS_Pursue : public UBTTaskNode
{
	GENERATED_BODY()

public:
	UBTTask_AOS_Pursue();

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Pursue")
	bool bShadow = false;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Pursue", meta = (ClampMin = "1", Units = "cm"))
	float AcceptanceRadius = 120.f;

	/** Re-issue the move when the ground point has moved farther than this. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Pursue", meta = (ClampMin = "1", Units = "cm"))
	float RepathDistance = 200.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Pursue", meta = (ClampMin = "0.05", Units = "s"))
	float RepathInterval = 0.25f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Pursue", meta = (ClampMin = "0", Units = "s"))
	float PathFailGrace = 1.5f;

protected:
	virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual EBTNodeResult::Type AbortTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual void TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds) override;
	virtual uint16 GetInstanceMemorySize() const override { return sizeof(FAOSPursueMemory); }
	virtual FString GetStaticDescription() const override;

private:
	bool IssueMove(UBehaviorTreeComponent& OwnerComp, FAOSPursueMemory& Memory, const FVector& Ground) const;
};
