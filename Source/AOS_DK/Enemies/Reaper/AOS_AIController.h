#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "Perception/AIPerceptionTypes.h"
#include "AOS_ReaperTypes.h"
#include "AOS_AIController.generated.h"

class UAIPerceptionComponent;
class UAISenseConfig_Sight;
class UAISenseConfig_Hearing;
class UAISenseConfig_Damage;
class UBehaviorTree;
class AShellPawn;
class AAOS_AIEnemyCharacter;

/**
 * Brain of the OOM Reaper. Team 9 ("oom"): hostile only to Shell-1; Lab 3 Daemons, drones, torpedoes and other Reapers are
 * ignored. Perception: sight 26 m (lose 30 m) in a 150 deg cone that follows the sensor mast, hearing 40 m, damage.
 * OnPossess wires the Blackboard and runs the Behavior Tree (spec 4.1): BehaviorTreeAsset if assigned, otherwise the native
 * BT_OOMReaper built by AOSReaperBT::BuildBehaviorTree (spec 5.1: Evade / Engage / Investigate / Patrol with
 * UBTService_AOS_ReaperSense, UBTTask_AOS_PatrolSurvey / MeleeStrike / Evade / Pursue). The controller owns perception and the
 * threat state; the sense service validates and decays it and mirrors it into the Blackboard.
 */
UCLASS()
class AOS_DK_API AAOS_AIController : public AAIController
{
	GENERATED_BODY()

public:
	AAOS_AIController();

	virtual void OnPossess(APawn* InPawn) override;
	virtual void OnUnPossess() override;
	virtual ETeamAttitude::Type GetTeamAttitudeTowards(const AActor& Other) const override;

	/** Only a piloted, powered Shell-1 outside the LARS cradle. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper|AI")
	bool IsHostileActor(const AActor* Actor) const;

	/** Perception reduction inside a hazard (heap brine): sight radius scale and half-angle (degrees). */
	void SetSightDegradation(float RadiusScale, float HalfAngleDegrees);
	void ResetSightDegradation();

	/** Death: stop the brain and every sense. */
	void ShutDown();

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper|AI")
	EAOSThreatLevel GetThreatLevel() const { return ThreatLevel; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper|AI")
	AShellPawn* GetTargetShell() const;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper|AI")
	bool HasLineOfSight() const { return bHasLineOfSight; }

	/** Seconds since the last hearing / damage stimulus (large when never). */
	float GetSecondsSinceHeard() const;

	UAIPerceptionComponent* GetReaperPerception() const { return PerceptionComp; }

	// ---- Behavior Tree layer (spec 4.3 / 5.3) ------------------------------------------------------------------------------
	bool IsBehaviorTreeRunning() const { return bRunningBT; }
	AAOS_AIEnemyCharacter* GetReaper() const;
	FVector GetHomeLocation() const { return HomeLocation; }
	double GetLostSightTime() const { return LostSightTime; }
	double GetSuspiciousSince() const { return SuspiciousSince; }
	const FVector& GetLastKnownLocation() const { return LastKnownLocation; }
	const FVector& GetLastSeenVelocity() const { return LastSeenVelocity; }

	/** Closest hull point of the Shell to the arm turret, strike envelope and above-reach flags (spec 5.3 steps 2-4). */
	bool ComputeEnvelope(const AShellPawn* Shell, FVector& OutClosest, bool& bOutInEnvelope, bool& bOutAboveReach) const;

	/** Point on the NavMesh below / near a world location (extent 300 x 300 x 3000). */
	FVector ProjectToNavBelow(const FVector& Location) const;

	/** Hostile -> Suspicious: drops the target and the focus, investigates InvestigateAt. */
	void LoseTarget(const FVector& InvestigateAt);

	/** Any level -> None (nothing found / suspicion decayed): back to the Walk gait. */
	void ClearThreat();

	/** Writes the perception state into the Blackboard (TargetActor, ThreatLevel, bHasLineOfSight, LastKnown/InvestigateLocation). */
	void MirrorToBlackboard();

	// ---- tuning (spec 4.1) -------------------------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|AI")
	TObjectPtr<UBehaviorTree> BehaviorTreeAsset;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|AI", meta = (ClampMin = "0", Units = "s"))
	float LoseTargetGrace = 2.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|AI", meta = (ClampMin = "0", Units = "s"))
	float InvestigateTimeout = 25.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Reaper|AI")
	int32 ReaperTeamId = 9;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|AI|Sight", meta = (Units = "cm"))
	float SightRadius = 2600.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|AI|Sight", meta = (Units = "cm"))
	float LoseSightRadius = 3000.f;

	/** Half angle; 75 = 150 deg cone. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|AI|Sight", meta = (Units = "deg"))
	float SightHalfAngle = 75.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|AI|Hearing", meta = (Units = "cm"))
	float HearingRange = 4000.f;

	/** Strike envelope (spec 5.3): reach from the arm turret and the horizontal radius of the "above reach" shadow zone. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|AI|Combat", meta = (Units = "cm"))
	float StrikeReach = 430.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|AI|Combat", meta = (Units = "cm"))
	float ShadowRadius = 700.f;

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UAIPerceptionComponent> PerceptionComp;

	UPROPERTY()
	TObjectPtr<UAISenseConfig_Sight> SightConfig;

	UPROPERTY()
	TObjectPtr<UAISenseConfig_Hearing> HearingConfig;

	UPROPERTY()
	TObjectPtr<UAISenseConfig_Damage> DamageConfig;

private:
	UFUNCTION()
	void HandleTargetPerceptionUpdated(AActor* Actor, FAIStimulus Stimulus);

	void SetThreatLevel(EAOSThreatLevel NewLevel);

	/** Blackboard + Behavior Tree lifecycle (called from OnPossess). */
	void StartBehaviorTree();

	/** The native tree when no asset is assigned (kept alive here; transient). */
	UPROPERTY(Transient)
	TObjectPtr<UBehaviorTree> RuntimeTree;

	TWeakObjectPtr<AAOS_AIEnemyCharacter> Reaper;
	TWeakObjectPtr<AShellPawn> TargetShell;
	EAOSThreatLevel ThreatLevel = EAOSThreatLevel::None;
	bool bHasLineOfSight = false;
	double LostSightTime = -1000.0;
	double SuspiciousSince = 0.0;
	double LastHeardTime = -1000.0;
	FVector LastKnownLocation = FVector::ZeroVector;
	FVector LastSeenVelocity = FVector::ZeroVector;
	FVector InvestigateLocation = FVector::ZeroVector;
	FVector HomeLocation = FVector::ZeroVector;
	bool bRunningBT = false;
	bool bShutDown = false;
};
