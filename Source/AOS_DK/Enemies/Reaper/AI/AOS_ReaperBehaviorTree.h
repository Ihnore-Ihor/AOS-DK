#pragma once

#include "CoreMinimal.h"

class UBehaviorTree;
class UBlackboardData;

/**
 * Native construction of BB_OOMReaper / BT_OOMReaper (spec 4.3 and 5.1). The editor's Python API cannot author Behavior Tree
 * graphs, so the default tree is assembled from the C++ nodes at possession time. A designer-authored UBehaviorTree assigned to
 * AAOS_AIController::BehaviorTreeAsset takes precedence (it must use the AOSReaperBB key names).
 *
 *   Selector "RPR_Root"                                  Service: BTService_AOS_ReaperSense (0.10 s)
 *   |- [bIsEvading]            (Both)        BTTask_AOS_Evade
 *   |- [ThreatLevel >= Hostile](Both)        Selector "Engage"
 *   |     |- [bInStrikeEnvelope](LowerPrio)  BTTask_AOS_MeleeStrike
 *   |     |- [bTargetAboveReach](Both)       BTTask_AOS_Pursue (Shadow)
 *   |     `-                                 BTTask_AOS_Pursue (Chase)
 *   |- [ThreatLevel >= Suspicious](Both)     BTTask_AOS_PatrolSurvey (Investigate)
 *   `-                                       BTTask_AOS_PatrolSurvey (Patrol)
 */
namespace AOSReaperBT
{
	AOS_DK_API UBlackboardData* BuildBlackboard(UObject* Outer);
	AOS_DK_API UBehaviorTree* BuildBehaviorTree(UObject* Outer);
}
