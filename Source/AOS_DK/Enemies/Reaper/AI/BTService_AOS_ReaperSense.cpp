#include "BTService_AOS_ReaperSense.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIController.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIEnemyCharacter.h"
#include "AOS_DK/Enemies/Reaper/AOS_EvasionComponent.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "Engine/World.h"
#include "CollisionQueryParams.h"

UBTService_AOS_ReaperSense::UBTService_AOS_ReaperSense()
{
	NodeName = TEXT("Reaper Sense");
	Interval = 0.10f;
	RandomDeviation = 0.02f;
	bCallTickOnSearchStart = true;   // decorators below read the flags before the first interval elapses
	bCreateNodeInstance = true;      // LastAppliedLevel is per owner (UBTService already notifies tick + search start)
}

FString UBTService_AOS_ReaperSense::GetStaticDescription() const
{
	return FString::Printf(TEXT("Target tracking + speed ladder (Walk 170 / Investigate 320 / Scuttle 620)\n%s"), *GetStaticTickIntervalDescription());
}

void UBTService_AOS_ReaperSense::TickNode(UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory, float DeltaSeconds)
{
	Super::TickNode(OwnerComp, NodeMemory, DeltaSeconds);

	AAOS_AIController* AIC = Cast<AAOS_AIController>(OwnerComp.GetAIOwner());
	AAOS_AIEnemyCharacter* R = AIC ? AIC->GetReaper() : nullptr;
	UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
	UWorld* World = OwnerComp.GetWorld();
	if (!AIC || !R || !BB || !World || R->IsDead())
	{
		return;
	}
	const double Now = World->GetTimeSeconds();

	// ---- 1. target validity and threat decay (spec 5.3 steps 6-7) --------------------------------------------------------------
	AShellPawn* Shell = AIC->GetTargetShell();
	EAOSThreatLevel Level = AIC->GetThreatLevel();
	if (Level == EAOSThreatLevel::Hostile && (!Shell || !AIC->IsHostileActor(Shell)))
	{
		// Kernel Panic / LARS cradle / gone: back to Investigate -> Patrol.
		AIC->LoseTarget(AIC->ProjectToNavBelow(AIC->GetLastKnownLocation()));
	}
	else if (Level == EAOSThreatLevel::Hostile && !AIC->HasLineOfSight() && Now - AIC->GetLostSightTime() > AIC->LoseTargetGrace)
	{
		AIC->LoseTarget(AIC->ProjectToNavBelow(AIC->GetLastKnownLocation() + AIC->GetLastSeenVelocity() * 1.f));
	}
	else if (Level == EAOSThreatLevel::Suspicious && Shell && !AIC->IsHostileActor(Shell))
	{
		AIC->ClearThreat();
	}
	else if (Level == EAOSThreatLevel::Suspicious && Now - AIC->GetSuspiciousSince() > AIC->InvestigateTimeout)
	{
		AIC->ClearThreat();
	}
	Shell = AIC->GetTargetShell();
	Level = AIC->GetThreatLevel();

	// ---- 2. speed ladder on transitions ---------------------------------------------------------------------------------------
	if (Level != LastAppliedLevel)
	{
		LastAppliedLevel = Level;
		switch (Level)
		{
		case EAOSThreatLevel::Hostile:    R->SetLocomotionMode(EAOSLocomotionMode::Scuttle); break;
		case EAOSThreatLevel::Suspicious: R->SetLocomotionMode(EAOSLocomotionMode::Investigate); break;
		default:                          R->SetLocomotionMode(EAOSLocomotionMode::Walk); break;
		}
	}

	// ---- 3. geometry: closest hull point, strike envelope, above-reach flag, ground point (steps 2-5) ---------------------------
	bool bInEnvelope = false;
	bool bAboveReach = false;
	float Distance = 0.f;
	FVector Closest = FVector::ZeroVector;
	if (Level == EAOSThreatLevel::Hostile && Shell && AIC->ComputeEnvelope(Shell, Closest, bInEnvelope, bAboveReach))
	{
		Distance = static_cast<float>(FVector::Dist(Closest, R->GetArmTurretLocation()));
		R->SetShellTarget(Shell);

		FVector Ground = Shell->GetActorLocation();
		FCollisionQueryParams Params(SCENE_QUERY_STAT(ReaperSenseGround), false, Shell);
		Params.AddIgnoredActor(R);
		FHitResult Hit;
		if (World->LineTraceSingleByChannel(Hit, Ground, Ground - FVector(0.0, 0.0, 3000.0), ECC_WorldStatic, Params))
		{
			Ground = Hit.ImpactPoint;
		}
		BB->SetValueAsVector(AOSReaperBB::TargetGroundPoint, AIC->ProjectToNavBelow(Ground));
	}
	else
	{
		R->SetShellTarget(nullptr);
	}

	// ---- 4. Blackboard -----------------------------------------------------------------------------------------------------------
	AIC->MirrorToBlackboard();   // TargetActor, ThreatLevel, bHasLineOfSight, LastKnownLocation, InvestigateLocation
	BB->SetValueAsBool(AOSReaperBB::bInStrikeEnvelope, bInEnvelope);
	BB->SetValueAsBool(AOSReaperBB::bTargetAboveReach, bAboveReach);
	BB->SetValueAsFloat(AOSReaperBB::TargetDistance, Distance);
	const UAOS_EvasionComponent* Evasion = R->GetEvasion();
	BB->SetValueAsBool(AOSReaperBB::bIsEvading, Evasion && Evasion->IsEvading());
	BB->SetValueAsBool(AOSReaperBB::bInHazard, R->IsInHazard());
}
