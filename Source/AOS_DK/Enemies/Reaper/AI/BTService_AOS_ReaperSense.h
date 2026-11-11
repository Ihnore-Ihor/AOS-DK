#pragma once

#include "CoreMinimal.h"
#include "BehaviorTree/BTService.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperTypes.h"
#include "BTService_AOS_ReaperSense.generated.h"

/**
 * Perception / target-tracking service of BT_OOMReaper (spec 5.3), 10 Hz.
 *
 *  - validates the target (Kernel Panic, LARS cradle, despawn), downgrades Hostile -> Suspicious after LoseTargetGrace without
 *    line of sight, and decays Suspicious -> None after InvestigateTimeout;
 *  - drives the speed ladder Walk (170) -> Investigate (320) -> Scuttle (620 cm/s) on every threat-level transition (the first
 *    sight is already handled in the same frame by the controller's perception callback);
 *  - writes TargetActor, ThreatLevel, bHasLineOfSight, TargetDistance, TargetGroundPoint, bInStrikeEnvelope, bTargetAboveReach,
 *    LastKnownLocation, InvestigateLocation, bIsEvading, bInHazard.
 */
UCLASS()
class AOS_DK_API UBTService_AOS_ReaperSense : public UBTService
{
	GENERATED_BODY()

public:
	UBTService_AOS_ReaperSense();

protected:
	virtual void TickNode(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds) override;
	virtual FString GetStaticDescription() const override;

private:
	/** Per-instance (bCreateNodeInstance): the level the speed ladder was last applied for. */
	EAOSThreatLevel LastAppliedLevel = EAOSThreatLevel::None;
};
