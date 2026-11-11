#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AOS_DK/Core/UI/HUD/AOSHudTypes.h"
#include "AOS_HazardReceiver.h"
#include "AOS_ReaperTypes.h"
#include "AOS_AIEnemyCharacter.generated.h"

class UBoxComponent;
class UNiagaraSystem;
class AAOS_AIWeapon;
class AAOS_AIController;
class AShellPawn;
class UAOS_EvasionComponent;
class UAOS_RSSPageMapComponent;

/**
 * RPR-6 "OOM Reaper": six-legged benthic walker on SK_OOMReaper (36 bones, procedurally animated by
 * UAOS_ReaperAnimInstance: tripod gait + analytic 2-bone leg IK, sensor-mast and dorsal-arm IK aimed at Shell-1).
 * 168 HP = 12 torpedo hits of 14. Hinders-only-the-NPC hazards (heap brine) reach it through IAOS_HazardReceiver.
 */
UCLASS(Blueprintable)
class AOS_DK_API AAOS_AIEnemyCharacter : public ACharacter, public IAOS_HazardReceiver
{
	GENERATED_BODY()

public:
	AAOS_AIEnemyCharacter();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void PostInitializeComponents() override;
	virtual float TakeDamage(float DamageAmount, struct FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override;
	virtual void GetActorEyesViewPoint(FVector& OutLocation, FRotator& OutRotation) const override;

	// ---- IAOS_HazardReceiver ----------------------------------------------------------------------------------------------
	virtual void EnterHazard_Implementation(AActor* Source, const FAOSHazardParams& Params) override;
	virtual void ExitHazard_Implementation(AActor* Source) override;

	// ---- state -------------------------------------------------------------------------------------------------------------
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper")
	bool IsDead() const { return bDead; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper")
	float GetHealth() const { return Health; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper")
	float GetMaxHealth() const { return MaxHealth; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper")
	int32 GetPID() const { return PID; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper")
	EAOSReaperPhase GetPhase() const { return Phase; }

	void SetPhase(EAOSReaperPhase NewPhase);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper")
	bool IsInHazard() const { return ActiveHazards.Num() > 0; }

	UBoxComponent* GetHitVolume() const { return HitVolume; }
	UAOS_EvasionComponent* GetEvasion() const { return Evasion; }
	UAOS_RSSPageMapComponent* GetPageMap() const { return PageMap; }
	AAOS_AIWeapon* GetWeapon() const { return Weapon; }
	AAOS_AIController* GetReaperController() const;

	bool HasLineOfSightToTarget() const;
	float GetSecondsSinceHeard() const;

	/** Locomotion mode -> MaxWalkSpeed (x hazard scale), gait row, rotation behaviour. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Reaper")
	void SetLocomotionMode(EAOSLocomotionMode Mode);

	EAOSLocomotionMode GetLocomotionMode() const { return LocomotionMode; }
	EAOSGaitMode GetGaitMode() const;

	void SetSkittering(bool bInSkitter) { bSkittering = bInSkitter; }
	bool IsSkittering() const { return bSkittering; }

	/** Sensor flare + jaw snap on first sighting. */
	void PlaySpotReaction();

	/** Key lines go to the cockpit terminal (AShellPawn::PushTerminalLog); everything goes to LogAOSAI. */
	void ReportToShell(const FString& Message, EAOSHudLogSeverity Severity = EAOSHudLogSeverity::Info);

	// ---- strike -------------------------------------------------------------------------------------------------------------
	bool CanStrike() const;
	bool IsStriking() const { return StrikeStage != EStrikeStage::None; }

	/** Commits a strike along arm-turret -> closest hull point. 0.45 s wind-up, 0.18 s thrust, 0.60 s recover. */
	bool RequestStrike(const AShellPawn* Shell, const FVector& ClosestHullPoint);

	/** Cancels a running strike (evasion took over). */
	void AbortStrike();

	// ---- mast / arm (read by the anim instance on the game thread) ----------------------------------------------------------
	void SetShellTarget(const AShellPawn* Shell);
	void SetMastLookPoint(const FVector& WorldPoint);
	void SetMastSweep(float YawDeg, float PitchDeg) { MastSweepYaw = YawDeg; MastSweepPitch = PitchDeg; }
	float GetMastSweepYaw() const { return MastSweepYaw; }
	float GetMastSweepPitch() const { return MastSweepPitch; }
	bool GetMastLookPoint(FVector& OutWorldPoint) const;
	FVector GetArmTurretLocation() const;
	float GetArmCommand(FVector& OutTipWorld, FVector& OutDirWorld, float& OutTipSpeed) const;
	float GetJawOpenTarget() const;
	float GetDeathAlpha() const { return DeathAlpha; }
	float GetPikeTipDistance() const { return PikeTipDistance; }
	void NotifyFootPlanted(int32 Leg, const FVector& GroundLocation);

	// ---- tuning (spec 4.6 / Appendix C) ---------------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Health", meta = (ClampMin = "1"))
	float MaxHealth = 168.f;   // 12 torpedo hits x 14

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Locomotion", meta = (Units = "cm/s"))
	float WalkSpeed = 170.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Locomotion", meta = (Units = "cm/s"))
	float InvestigateSpeed = 320.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Locomotion", meta = (Units = "cm/s"))
	float ScuttleSpeed = 620.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Locomotion", meta = (Units = "cm/s"))
	float CombatSpeed = 120.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Weapon")
	TSubclassOf<AAOS_AIWeapon> WeaponClass;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Weapon")
	FName WeaponSocketName = TEXT("SOCKET_Weapon_Dorsal");

	/** Mount -> SOCKET_Strike_Trace_End along the pike axis (authored 262 cm). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Weapon", meta = (Units = "cm"))
	float PikeTipDistance = 262.f;

	/** Arm turret (strike envelope origin) and the bones used for the eye point. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Rig")
	FName ArmTurretBone = TEXT("Arm_Yaw_Bone");

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Rig")
	FName SensorBone = TEXT("Mast_Head_Bone");

	/** Wind-up / thrust / recover / cooldown (s). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Strike", meta = (ClampMin = "0.01", Units = "s"))
	float WindupTime = 0.45f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Strike", meta = (ClampMin = "0.01", Units = "s"))
	float ThrustTime = 0.18f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Strike", meta = (ClampMin = "0.01", Units = "s"))
	float RecoverTime = 0.6f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Strike", meta = (ClampMin = "0", Units = "s"))
	float StrikeCooldown = 1.5f;

	/** Farthest pike-tip distance from the arm turret (arm reach + pike). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Strike", meta = (ClampMin = "0", Units = "cm"))
	float MaxTipReach = 432.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Patrol")
	TArray<TObjectPtr<AActor>> PatrolNodes;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Patrol", meta = (ClampMin = "0", Units = "cm"))
	float HomeRadius = 2000.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Hazard", meta = (ClampMin = "0.05", Units = "s"))
	float HazardRampIn = 0.3f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Hazard", meta = (ClampMin = "0.05", Units = "s"))
	float HazardRampOut = 1.0f;

	/** After death a fresh Reaper of this class is spawned at the original spawn transform (full HP, full decoy charges). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Respawn")
	bool bAutoRespawn = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Respawn", meta = (ClampMin = "0", Units = "s", EditCondition = "bAutoRespawn"))
	float RespawnDelay = 6.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|FX")
	TObjectPtr<UNiagaraSystem> SiltPuffFX;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|FX")
	TObjectPtr<UNiagaraSystem> BrineWadeFX;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|FX")
	TObjectPtr<UNiagaraSystem> PageReleaseFX;

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Reaper", meta = (DisplayName = "On Spotted Target"))
	void BP_OnSpotted();

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Reaper", meta = (DisplayName = "On Died"))
	void BP_OnDied();

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UBoxComponent> HitVolume;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UAOS_EvasionComponent> Evasion;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UAOS_RSSPageMapComponent> PageMap;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "AOS_DK|Reaper")
	TObjectPtr<AAOS_AIWeapon> Weapon;

private:
	enum class EStrikeStage : uint8 { None, Windup, Thrust, Recover };

	void Die();
	void Respawn();
	void ApplySpeed();
	void UpdateStrike(float Dt);
	void UpdateHazardRamp(float Dt);
	void UpdatePageMapAlert();
	void RecomputeHazards();

	FTransform SpawnTransform;
	FTimerHandle RespawnTimer;

	float Health = 168.f;
	bool bDead = false;
	int32 PID = 0;
	EAOSReaperPhase Phase = EAOSReaperPhase::Patrol;
	EAOSLocomotionMode LocomotionMode = EAOSLocomotionMode::Walk;
	bool bSkittering = false;
	float DeathAlpha = 0.f;
	float OffGroundTime = 0.f;
	float SpotFlare = 0.f;
	int32 LastReportedPages = 16;

	// strike
	EStrikeStage StrikeStage = EStrikeStage::None;
	float StageTime = 0.f;
	FVector StrikeTarget = FVector::ZeroVector;
	FVector StrikeDir = FVector::ForwardVector;
	double LastStrikeEndTime = -1000.0;
	bool bStrikeHitReported = false;

	// aim
	TWeakObjectPtr<const AShellPawn> ShellTarget;
	FVector MastLookPoint = FVector::ZeroVector;
	double MastLookExpire = -1.0;
	float MastSweepYaw = 0.f;
	float MastSweepPitch = 0.f;

	// hazards
	TMap<TWeakObjectPtr<AActor>, FAOSHazardParams> ActiveHazards;
	float HazardSpeedTarget = 1.f;
	float HazardSpeedCurrent = 1.f;
};
