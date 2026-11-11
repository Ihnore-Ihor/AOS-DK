#include "AOS_ReaperBehaviorTree.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperTypes.h"
#include "BTDecorator_AOS_Condition.h"
#include "BTService_AOS_ReaperSense.h"
#include "BTTask_AOS_Evade.h"
#include "BTTask_AOS_MeleeStrike.h"
#include "BTTask_AOS_PatrolSurvey.h"
#include "BTTask_AOS_Pursue.h"
#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BlackboardData.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Bool.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Enum.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Float.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Int.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Object.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Vector.h"
#include "BehaviorTree/Composites/BTComposite_Selector.h"
#include "GameFramework/Actor.h"

namespace AOSReaperBT
{
	UBlackboardData* BuildBlackboard(UObject* Outer)
	{
		UBlackboardData* BB = NewObject<UBlackboardData>(Outer, NAME_None, RF_Transient);

		if (UBlackboardKeyType_Object* Key = BB->UpdatePersistentKey<UBlackboardKeyType_Object>(AOSReaperBB::SelfActor))
		{
			Key->BaseClass = AActor::StaticClass();
		}
		if (UBlackboardKeyType_Object* Key = BB->UpdatePersistentKey<UBlackboardKeyType_Object>(AOSReaperBB::TargetActor))
		{
			Key->BaseClass = AActor::StaticClass();
		}
		if (UBlackboardKeyType_Enum* Key = BB->UpdatePersistentKey<UBlackboardKeyType_Enum>(AOSReaperBB::ThreatLevel))
		{
			Key->EnumType = StaticEnum<EAOSThreatLevel>();
		}
		BB->UpdatePersistentKey<UBlackboardKeyType_Bool>(AOSReaperBB::bHasLineOfSight);
		BB->UpdatePersistentKey<UBlackboardKeyType_Float>(AOSReaperBB::TargetDistance);
		BB->UpdatePersistentKey<UBlackboardKeyType_Vector>(AOSReaperBB::TargetGroundPoint);
		BB->UpdatePersistentKey<UBlackboardKeyType_Bool>(AOSReaperBB::bInStrikeEnvelope);
		BB->UpdatePersistentKey<UBlackboardKeyType_Bool>(AOSReaperBB::bTargetAboveReach);
		BB->UpdatePersistentKey<UBlackboardKeyType_Vector>(AOSReaperBB::LastKnownLocation);
		BB->UpdatePersistentKey<UBlackboardKeyType_Vector>(AOSReaperBB::InvestigateLocation);
		BB->UpdatePersistentKey<UBlackboardKeyType_Vector>(AOSReaperBB::PatrolLocation);
		BB->UpdatePersistentKey<UBlackboardKeyType_Int>(AOSReaperBB::PatrolNodeIndex);
		BB->UpdatePersistentKey<UBlackboardKeyType_Bool>(AOSReaperBB::bIsEvading);
		BB->UpdatePersistentKey<UBlackboardKeyType_Bool>(AOSReaperBB::bInHazard);

		BB->UpdateParentKeys();
		BB->UpdateKeyIDs();
		return BB;
	}

	namespace
	{
		UBTDecorator_AOS_Condition* MakeCondition(UObject* Outer, FName Key, EAOSBTCondition Condition, EAOSThreatLevel MinThreat, EBTFlowAbortMode::Type Abort)
		{
			UBTDecorator_AOS_Condition* Decorator = NewObject<UBTDecorator_AOS_Condition>(Outer);
			Decorator->Configure(Key, Condition, MinThreat, Abort);
			return Decorator;
		}

		void AddTask(UBTCompositeNode* Parent, UBTTaskNode* Task, UBTDecorator* Decorator = nullptr)
		{
			FBTCompositeChild& Child = Parent->Children.AddDefaulted_GetRef();
			Child.ChildTask = Task;
			if (Decorator)
			{
				Child.Decorators.Add(Decorator);
			}
		}

		void AddComposite(UBTCompositeNode* Parent, UBTCompositeNode* Composite, UBTDecorator* Decorator = nullptr)
		{
			FBTCompositeChild& Child = Parent->Children.AddDefaulted_GetRef();
			Child.ChildComposite = Composite;
			if (Decorator)
			{
				Child.Decorators.Add(Decorator);
			}
		}
	}

	UBehaviorTree* BuildBehaviorTree(UObject* Outer)
	{
		UBehaviorTree* Tree = NewObject<UBehaviorTree>(Outer, NAME_None, RF_Transient);
		Tree->BlackboardAsset = BuildBlackboard(Tree);

		UBTComposite_Selector* Root = NewObject<UBTComposite_Selector>(Tree);
		Tree->RootNode = Root;
		Root->Services.Add(NewObject<UBTService_AOS_ReaperSense>(Root));

		namespace Abort = EBTFlowAbortMode;

		// [1] Evade
		AddTask(Root, NewObject<UBTTask_AOS_Evade>(Root),
			MakeCondition(Root, AOSReaperBB::bIsEvading, EAOSBTCondition::BoolTrue, EAOSThreatLevel::None, Abort::Both));

		// [2] Engage
		UBTComposite_Selector* Engage = NewObject<UBTComposite_Selector>(Root);
		AddComposite(Root, Engage,
			MakeCondition(Root, AOSReaperBB::ThreatLevel, EAOSBTCondition::ThreatAtLeast, EAOSThreatLevel::Hostile, Abort::Both));

		AddTask(Engage, NewObject<UBTTask_AOS_MeleeStrike>(Engage),
			MakeCondition(Engage, AOSReaperBB::bInStrikeEnvelope, EAOSBTCondition::BoolTrue, EAOSThreatLevel::None, Abort::LowerPriority));

		UBTTask_AOS_Pursue* Shadow = NewObject<UBTTask_AOS_Pursue>(Engage);
		Shadow->bShadow = true;
		AddTask(Engage, Shadow,
			MakeCondition(Engage, AOSReaperBB::bTargetAboveReach, EAOSBTCondition::BoolTrue, EAOSThreatLevel::None, Abort::Both));

		UBTTask_AOS_Pursue* Chase = NewObject<UBTTask_AOS_Pursue>(Engage);
		Chase->bShadow = false;
		AddTask(Engage, Chase);

		// [3] Investigate
		UBTTask_AOS_PatrolSurvey* Investigate = NewObject<UBTTask_AOS_PatrolSurvey>(Root);
		Investigate->Mode = EAOSSurveyMode::Investigate;
		AddTask(Root, Investigate,
			MakeCondition(Root, AOSReaperBB::ThreatLevel, EAOSBTCondition::ThreatAtLeast, EAOSThreatLevel::Suspicious, Abort::Both));

		// [4] Patrol
		UBTTask_AOS_PatrolSurvey* Patrol = NewObject<UBTTask_AOS_PatrolSurvey>(Root);
		Patrol->Mode = EAOSSurveyMode::Patrol;
		AddTask(Root, Patrol);

		return Tree;
	}
}
