#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AOS_ReaperTypes.h"
#include "AOS_EvasionComponent.generated.h"

class AAOS_CavitationDecoy;
class AAOS_AIEnemyCharacter;
class UAOS_RSSPageMapComponent;

/**
 * Distance-proportional evasion against guided micro-torpedoes (spec section 6).
 *
 *   P_base(D) = clamp(0.05 + 3.571e-4 * (D - 400), 0.05, 0.80)    for D in [4 m, 25 m]   (0 below the reaction gate)
 *   P_dodge   = clamp(P_base * M_aware * M_state * M_fatigue * M_hazard, 0, P_max)   while Charges > 0 and the cooldown elapsed
 *
 * One seeded roll per salvo (Seed = PID * 7919 + SalvoId). On success: lateral skitter + cavitation decoy, and every
 * in-flight torpedo of the salvo is diverted with AMicroTorpedo::Retarget.
 */
UCLASS(ClassGroup = (AOS_DK), meta = (BlueprintSpawnableComponent))
class AOS_DK_API UAOS_EvasionComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UAOS_EvasionComponent();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** Analytic base law (cm in, probability out). Static so the Monte-Carlo test and the unit tests share it. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper|Evasion")
	static float ComputeBaseProbability(float DistanceCm);

	/** Full model for the current state of the owner. */
	float ComputeDodgeProbability(float DistanceCm) const;

	/**
	 * Rolls once for the salvo. On DODGE launches the decoy + skitter and returns the decoy.
	 * Returns null when the Reaper holds (no dodge); InOutSalvo is only read.
	 */
	AAOS_CavitationDecoy* EvaluateSalvo(const FAOSTorpedoSalvo& Salvo);

	/** Whether this Reaper is the subject of the salvo (aimed at, or the aim point is within ThreatAimRadius of its hit volume). */
	bool IsThreatenedBy(const FAOSTorpedoSalvo& Salvo) const;

	void SetHazardScale(float Scale) { HazardScale = FMath::Clamp(Scale, 0.f, 1.f); }
	void SetChargeRegenPaused(bool bPaused) { bRegenPaused = bPaused; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper|Evasion")
	int32 GetCharges() const { return Charges; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper|Evasion")
	bool IsEvading() const { return bEvading; }

	/** 0..1 evasion readiness (border of the page map). */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper|Evasion")
	float GetReadiness() const;

	// ---- tuning (spec Appendix C) --------------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0", Units = "cm"))
	float PointBlankDistance = 400.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0", Units = "cm"))
	float FarDistance = 2500.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0", ClampMax = "1"))
	float MinProbability = 0.05f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0", ClampMax = "1"))
	float MaxProbability = 0.80f;

	/** Below this launch distance the Reaper has no time to react (t_gate 0.15 s at 40 m/s mean flight speed ~ 240 cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0", Units = "cm"))
	float ReactionGateDistance = 240.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0", Units = "cm"))
	float ThreatAimRadius = 250.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0"))
	int32 MaxCharges = 3;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0.1", Units = "s"))
	float ChargeRegenInterval = 6.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0", Units = "s"))
	float DodgeCooldown = 1.5f;

	/** Fatigue base: M_fatigue = FatigueBase^n, n = dodges in the last FatigueWindow seconds. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0", ClampMax = "1"))
	float FatigueBase = 0.6f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion", meta = (ClampMin = "0.1", Units = "s"))
	float FatigueWindow = 5.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion|Skitter", meta = (ClampMin = "0", Units = "cm"))
	float SkitterDistance = 340.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion|Skitter", meta = (ClampMin = "0.05", Units = "s"))
	float SkitterDuration = 0.45f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion|Decoy", meta = (ClampMin = "0", Units = "cm"))
	float DecoyOffset = 80.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Evasion|Decoy", meta = (ClampMin = "0.1", Units = "s"))
	float DecoyLifetime = 1.2f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Evasion|Decoy")
	TSubclassOf<AAOS_CavitationDecoy> DecoyClass;

	// ---- statistics (aos.ai.DodgeStats) -----------------------------------------------------------------------------------
	int32 StatSalvos = 0;
	int32 StatDodges = 0;
	int32 StatBlocked = 0;
	double StatDodgedDistanceSum = 0.0;
	double StatLandedDistanceSum = 0.0;
	int32 StatLanded = 0;

protected:
	virtual void BeginPlay() override;

private:
	AAOS_AIEnemyCharacter* GetReaper() const;
	float ComputeAwareness() const;
	float ComputeStateFactor() const;
	float ComputeFatigue() const;
	bool TrySkitter(const FVector& AttackOrigin, const FVector& AimPoint);
	void EndSkitter();
	void PushPageMap();

	int32 Charges = 3;
	float RegenTimer = 0.f;
	float HazardScale = 1.f;
	bool bRegenPaused = false;
	bool bEvading = false;
	double LastDodgeTime = -1000.0;
	TArray<double> RecentDodges;
	FTimerHandle SkitterTimer;
	float SavedGroundFriction = 0.f;
	float SavedBraking = 0.f;
};
