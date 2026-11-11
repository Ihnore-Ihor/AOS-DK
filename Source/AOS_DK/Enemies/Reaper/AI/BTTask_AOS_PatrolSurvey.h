#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/BTTaskNode.h"
#include "BTTask_AOS_PatrolSurvey.generated.h"

UENUM(BlueprintType)
enum class EAOSSurveyMode : uint8
{
	/** Walk to the next patrol node, then survey 5 headings (look up on alternate headings). */
	Patrol,
	/** Walk to InvestigateLocation, then survey 7 headings (look up on every heading) and clear the suspicion. */
	Investigate
};

struct FAOSPatrolSurveyMemory : public FBTTaskMemory
{
	/** Plain data, reset as a unit in ExecuteTask (node memory is raw bytes, no constructor runs). */
	struct FState
	{
		uint8 Stage = 0;              // 0 = move, 1 = turn, 2 = hold
		int32 HeadingIndex = 0;
		int32 NumHeadings = 0;
		float StageTime = 0.f;
		float TotalTime = 0.f;
		float HoldDuration = 0.f;
		float ArrivalYaw = 0.f;
		float Headings[7] = { 0.f, 0.f, 0.f, 0.f, 0.f, 0.f, 0.f };
		FVector Destination = FVector::ZeroVector;
		bool bMovementOverridden = false;
		bool bSavedOrient = false;
		bool bSavedDesiredRotation = false;
		FRotator SavedRotationRate = FRotator::ZeroRotator;
	};
	FState S;
};

/**
 * Patrol routing with survey halts (spec 5.4 / 5.5).
 * Moves between the character's PatrolNodes (round robin; random reachable points around the home location when no nodes are
 * assigned), then halts: stops, turns in place at 60 deg/s (90 deg/s investigating) through the heading list, sweeps the sensor
 * mast in yaw and pitches it up to scan the water column above (+45 deg on alternate headings when patrolling, +55 deg on every
 * heading when investigating). Writes PatrolLocation / PatrolNodeIndex. Observer aborts (a sighting) cancel it at any point.
 */
UCLASS()
class AOS_DK_API UBTTask_AOS_PatrolSurvey : public UBTTaskNode
{
	GENERATED_BODY()

public:
	UBTTask_AOS_PatrolSurvey();

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Survey")
	EAOSSurveyMode Mode = EAOSSurveyMode::Patrol;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Survey", meta = (ClampMin = "1", Units = "cm"))
	float PatrolAcceptanceRadius = 100.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Survey", meta = (ClampMin = "1", Units = "cm"))
	float InvestigateAcceptanceRadius = 150.f;

protected:
	virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual EBTNodeResult::Type AbortTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
	virtual void TickTask(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds) override;
	virtual void OnTaskFinished(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, EBTNodeResult::Type TaskResult) override;
	virtual uint16 GetInstanceMemorySize() const override { return sizeof(FAOSPatrolSurveyMemory); }
	virtual FString GetStaticDescription() const override;

private:
	bool PickDestination(class AAOS_AIController* AIC, class AAOS_AIEnemyCharacter* R, class UBlackboardComponent* BB, FVector& OutDestination) const;
	void BeginSurvey(class AAOS_AIController* AIC, class AAOS_AIEnemyCharacter* R, FAOSPatrolSurveyMemory::FState& S) const;
	void RestoreBody(class AAOS_AIController* AIC, class AAOS_AIEnemyCharacter* R, FAOSPatrolSurveyMemory::FState& S) const;
};
