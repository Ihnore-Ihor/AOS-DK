#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "AOS_DK/Core/Interfaces/Interactions/Interactable.h"
#include "AOS_DK/Core/UI/HUD/AOSHudTypes.h"
#include "ShellPawn.generated.h"

class UBoxComponent;
class UStaticMeshComponent;
class UCameraComponent;
class USubDroneBayComponent;
class UShellEnergyComponent;
class UAOSFluidPhysicsComponent;
class UPlayerSubmarineHUDWidget;
class ULightComponent;
class UPointLightComponent;
class USpotLightComponent;
class UNiagaraSystem;
class AShellDock;
class APlayerController;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

UCLASS()
class AOS_DK_API AShellPawn : public APawn, public IInteractable
{
	GENERATED_BODY()

public:
	AShellPawn();

	virtual void Tick(float DeltaTime) override;
	virtual void BeginPlay() override;
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;
	virtual void NotifyControllerChanged() override;
	virtual void Interact_Implementation(AActor* InstigatorActor) override;

	virtual float TakeDamage(float DamageAmount, struct FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override;

	/** Mean sea level, owned by the fluid physics component. */
	float GetOceanSurfaceZ() const;
	USubDroneBayComponent* GetDroneBay() const { return DroneBay; }

	// --- Energy / HUD telemetry -------------------------------------------------------------------
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell")
	UShellEnergyComponent* GetEnergy() const { return Energy; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell")
	UPlayerSubmarineHUDWidget* GetCockpitHUD() const { return CockpitHUD; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell")
	UAOSFluidPhysicsComponent* GetFluidPhysics() const { return FluidPhysics; }

	/** Depth below the mean sea level (OceanSurfaceZ), metres, >= 0. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell")
	float GetDepthMeters() const;

	/** Compass heading of the nose: 0 = N (+X), 90 = E (+Y). */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell")
	float GetHeadingDegrees() const;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell")
	float GetPitchDegrees() const;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell")
	float GetCameraFieldOfView() const;

	/** Energy depleted: engines, lights and drones are down until the recovery completes. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell")
	bool IsSystemsHalted() const { return bSystemsHalted; }

	/** 0..1 progress of the Kernel Panic -> surface recovery sequence. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell")
	float GetRecoveryProgress() const;

	/** G: engages the gyro-stabilizer (aligns the hull to the horizon). Its state lines go to the cockpit terminal log. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Shell")
	void TriggerStabilization();

	/** Prints a line into the cockpit terminal log (no-op while nobody is aboard). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Shell")
	void PushTerminalLog(const FString& Source, const FString& Message, EAOSHudLogSeverity Severity = EAOSHudLogSeverity::Info);

	/**
	 * Locks / unlocks the pilot's 6DOF control (thrust, ballast, steering, gyro, boost, drone bay, interact) for
	 * scripted sequences such as the transit shafts. Locking zeroes every pending input and recalls the drones.
	 */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Shell")
	void SetBlockControls(bool bBlock);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell")
	bool AreControlsBlocked() const { return bControlsBlocked; }

	// --- [F] interaction focus ----------------------------------------------------------------------
	/** Interactable under the reticle (pickup, terminal, dock), refreshed at InteractQueryRate; [F] acts on it. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell|Interaction")
	AActor* GetInteractFocus() const { return InteractFocus.Get(); }

	/** Reticle prompt of the focus ("SALVAGE ENERGY (+25%)" / "FULL"); false = nothing in focus. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell|Interaction")
	bool GetFocusPrompt(FText& OutAction, bool& bOutAvailable) const;

	/** Called by the dock at the end of the recovery: berth transform + restored base charge. */
	void FinishRecovery(const FTransform& ParkingTransform);

	// --- LARS cradle (dock arm) ---------------------------------------------------------------------
	/** The Shell is carried by the LARS arm: kinematic (no fluid forces), pilot controls locked, cockpit HUD deferred. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Shell|LARS")
	void EnterLARSCradle();

	/** The jaws let go: physics + fluid forces back on (controls stay locked until GrantPilotControl). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Shell|LARS")
	void LeaveLARSCradle();

	/** End of the LARS launch: 6DOF control and the cockpit HUD come online. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Shell|LARS")
	void GrantPilotControl();

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Shell|LARS")
	bool IsInLARSCradle() const { return bInLARSCradle; }

	/** Shows (binds, telemetry live this frame) / hides the cockpit HUD, e.g. while an external camera is in use. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Shell|HUD")
	void SetCockpitHUDVisible(bool bVisible);

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UBoxComponent> BoxRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UStaticMeshComponent> ShellMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UCameraComponent> FPCamera;

	/** Dual-Core drone bay: spawns module drones, routes IA_Sub_DroneToggle / IA_Sub_DroneAttack. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<USubDroneBayComponent> DroneBay;

	/** Water interaction engine: Gerstner sea state, drag, flotation (vehicle response model, stepped from Tick). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UAOSFluidPhysicsComponent> FluidPhysics;

	/** Core energy = hull integrity + power budget. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UShellEnergyComponent> Energy;

	/** Cabin light (dims / turns into a red emergency strobe on Kernel Panic). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UPointLightComponent> CabinLight;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<USpotLightComponent> HeadlightLeft;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<USpotLightComponent> HeadlightRight;

	//~ Inputs
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputMappingContext> SubMappingContext;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> MoveAction; // W/S, A/D

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> RotateAction; // Mouse X/Y, Q/E

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> BallastAction; // Shift/Space

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> StabilizeAction; // G

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> InteractAction;

	//~ [F] interaction focus
	/** Reach of the reticle interaction query from the camera. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Interaction", meta = (ClampMin = "100", Units = "cm"))
	float InteractRange = 800.f;

	/** Sweep radius for query-only focus volumes (pickups): aim forgiveness on top of the volume itself. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Interaction", meta = (ClampMin = "0", Units = "cm"))
	float InteractAimRadius = 25.f;

	/** Query rate of the interaction focus (matches the HUD aim trace). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Interaction", meta = (ClampMin = "1", ClampMax = "120", Units = "Hz"))
	float InteractQueryRate = 30.f;

	/** IA_Sub_Boost (hold): thrust multiplier - the only movement mode that costs energy. */
	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> BoostAction;

	//~ Boost
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Thrust", meta = (ClampMin = "1"))
	float BoostThrustMultiplier = 1.8f;

	//~ Energy budget (% of core per second at full load).
	//~ Cruising - main/lateral thrust, ballast, steering, gyro - is FREE. Power goes only to:
	/** Boost (Left Ctrl) at full forward thrust. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy", meta = (ClampMin = "0"))
	float BoostDrainPerSec = 1.5f;

	/** Per drone held in its working (Deployed) position: link + stabilisation (minimal background load). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy", meta = (ClampMin = "0"))
	float DroneDeployedDrainPerSec = 0.05f;

	/** Attacker pulse systems at full spin (spin-up / firing). One-shot costs (manual reload) live on the drone. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy", meta = (ClampMin = "0"))
	float DroneCombatDrainPerSec = 0.8f;

	//~ Kernel Panic -> recovery
	/** Panic shown before the screen fades out. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Recovery", meta = (ClampMin = "0", Units = "s"))
	float PanicHoldTime = 2.5f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Recovery", meta = (ClampMin = "0.05", Units = "s"))
	float RecoveryFadeOutTime = 0.9f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Recovery", meta = (ClampMin = "0.05", Units = "s"))
	float RecoveryFadeInTime = 1.1f;

	/** Base charge of the Shell when it is returned to its berth. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Recovery", meta = (ClampMin = "0.01", ClampMax = "1"))
	float RecoveryEnergyFraction = 0.4f;

	/** Dead weight while halted (the hull slowly sinks), cm/s^2. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Recovery", meta = (ClampMin = "0"))
	float HaltedSinkAcceleration = 45.f;

	//~ Headlight anti-glare: proximity auto-dimming (the lamp "auto-iris" of a work-class ROV)
	/**
	 * Beyond this range ahead of the lamps the headlights run at full power. Closer to a surface the power follows
	 * (d / BeamFullPowerDistance)^2, i.e. the illuminance on the surface the beams hit stays capped at the value it has at
	 * this range, instead of growing with 1/d^2 into a 7-stop hot spot the auto-exposure cannot hold. 0 = off.
	 */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Lights|AntiGlare", meta = (ClampMin = "0", Units = "cm"))
	float BeamFullPowerDistance = 1200.f;

	/** Floor of the auto-dimming (fraction of the full power) right against a wall. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Lights|AntiGlare", meta = (ClampMin = "0.01", ClampMax = "1"))
	float MinBeamDimming = 0.05f;

	/** Log-space slew of the dimming, 1/s (no visible pumping between the 30 Hz probes). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Lights|AntiGlare", meta = (ClampMin = "0.1"))
	float BeamDimmingSpeed = 5.f;

	/** Radius of the probe swept along each beam axis (a thin pillar does not dim the lamps). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Lights|AntiGlare", meta = (ClampMin = "0", Units = "cm"))
	float BeamProbeRadius = 30.f;

	/** Main lights die out within this time, then only the red emergency strobe remains. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Recovery", meta = (ClampMin = "0.1", Units = "s"))
	float EmergencyLightDecayTime = 1.8f;

	//~ Damage feedback
	/** NS_ShellHitDischarge: energy dissipation on the hull at the impact point. */
	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Damage")
	TObjectPtr<UNiagaraSystem> HullHitFX;

	/** Optional second burst at the impact (e.g. NS_TorpedoHit bubbles). */
	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Damage")
	TObjectPtr<UNiagaraSystem> HullHitSecondaryFX;

	/** Camera chromatic aberration at the peak of a damage glitch. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Damage", meta = (ClampMin = "0"))
	float DamageFringeIntensity = 4.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Damage", meta = (ClampMin = "0"))
	float PanicFringeIntensity = 2.5f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Damage", meta = (ClampMin = "0.05", Units = "s"))
	float DamageGlitchTime = 0.45f;

	//~ HUD
	/** WBP_SubmarineHUD (falls back to the native layout). */
	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|HUD")
	TSubclassOf<UPlayerSubmarineHUDWidget> HUDWidgetClass;

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|HUD")
	int32 HUDZOrder = -10;

	//~ Propulsion Configuration
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Thrust")
	float ForwardThrust = 1500.f; // Acceleration in cm/s^2 (approx 1.5G)

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Thrust")
	float LateralThrust = 500.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Thrust")
	float ThrustRampSpeed = 3.5f;

	//~ Steering Settings
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Control")
	bool bSwapYawAndRoll = false;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Control")
	float PitchSensitivity = 2.2f; // Angular acceleration in rad/s^2

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Control")
	float YawSensitivity = 2.0f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Control")
	float RollSensitivity = 1.5f;

	//~ Ballast System
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Ballast")
	float BallastForce = 600.f; // Ascend/Descend acceleration

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Ballast")
	float BallastChangeSpeed = 3.5f;

private:
	void ApplyThrust(const FInputActionValue& Value);
	void ResetThrust(const FInputActionValue& Value);
	void ApplyRotation(const FInputActionValue& Value);
	void ApplyBallast(const FInputActionValue& Value);
	void ResetBallast(const FInputActionValue& Value);
	void HandleInteract();
	void StartBoost(const FInputActionValue& Value);
	void StopBoost(const FInputActionValue& Value);

	UFUNCTION()
	void HandleEnergyDepleted();

	void BeginRecoveryFade();
	void ExecuteRecovery();
	AShellDock* ResolveHomeDock();
	void ShowCockpitHUD(APlayerController* PC);
	/** Creates + adds the HUD widget collapsed (no first-show hitch when the camera enters the cockpit). */
	UPlayerSubmarineHUDWidget* EnsureCockpitHUD(APlayerController* PC);
	void HideCockpitHUD();
	void CacheLights();
	void SetLightsLevel(float Level, bool bEmergencyRed);
	void UpdateLights(float DeltaTime);
	/** 30 Hz beam-axis probes -> smoothed HeadlightDim -> lamp intensities. */
	void UpdateHeadlightDimming(float DeltaTime);
	bool IsHeadlight(const ULightComponent* Light) const;
	void UpdateEnergyLoads();
	void UpdateCameraGlitch(float DeltaTime);
	/** Hands the lens back to the level post-process (no leftover fringe / grain). */
	void ResetCameraPostProcess();
	void SpawnHullHitFX(const FVector& Location, const FVector& Normal);

	void UpdateHydrodynamics(float DeltaTime);

	void UpdateInteractFocus(float DeltaTime);
	/** Visibility trace (occluders, blocking interactables) + object sweep for query-only focus volumes; nearest wins. */
	AActor* QueryInteractFocus() const;
	void RefreshFocusPrompt();

	UPROPERTY()
	TObjectPtr<AController> CachedController;

	float TargetBallastForce = 0.f;
	float CurrentBallastForce = 0.f;
	float TargetThrustScalar = 0.f;
	float CurrentThrustScalar = 0.f;

	FVector CurrentMoveInput = FVector::ZeroVector;
	FVector CurrentRotationInput = FVector::ZeroVector;
	bool bIsStabilizing = false;

	FVector2D MoveAxisRaw = FVector2D::ZeroVector;
	bool bBoostHeld = false;

	// --- Halt / recovery ---------------------------------------------------------------------------
	bool bSystemsHalted = false;
	bool bRecoveryFading = false;
	bool bControlsBlocked = false;
	bool bInLARSCradle = false;
	float HaltElapsed = 0.f;
	float CameraGlitch = 0.f;
	float LightsLevel = 0.f;
	float HeadlightDim = 1.f;
	float HeadlightDimTarget = 1.f;
	float BeamProbeTimer = 0.f;
	FTimerHandle RecoveryTimer;
	TWeakObjectPtr<APlayerController> RecoveryController;
	TWeakObjectPtr<AShellDock> HomeDock;

	UPROPERTY(Transient)
	TObjectPtr<UPlayerSubmarineHUDWidget> CockpitHUD;

	TWeakObjectPtr<AActor> InteractFocus;
	float InteractQueryTimer = 0.f;
	FText FocusAction;
	bool bFocusAvailable = false;

	struct FCachedLight
	{
		TWeakObjectPtr<ULightComponent> Light;
		float BaseIntensity = 0.f;
		FLinearColor BaseColor = FLinearColor::White;
	};
	TArray<FCachedLight> CachedLights;
};