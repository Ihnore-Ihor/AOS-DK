#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "AOS_DK/Core/UI/HUD/AOSHudTypes.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneTypes.h"
#include "PlayerSubmarineHUDWidget.generated.h"

class AShellPawn;
class UShellEnergyComponent;
class ASubDroneBase;
class USubDroneBayComponent;
class UWidgetTree;
class UAOSHudElement;
class UAOSHudCockpitFrame;
class UAOSHudBatteryGauge;
class UAOSHudNavigationTape;
class UAOSHudCrosshair;
class UAOSHudDroneHoneycomb;
class UAOSHudTerminalLog;
class UAOSHudGlitchOverlay;
class UAOSHudKernelPanicPanel;

/**
 * Cockpit HUD of the Shell (Task 4). The C++ "hub": pulls telemetry from the possessed Shell every
 * frame, reacts to energy / drone events and feeds the vector elements. WBP_SubmarineHUD (child
 * Blueprint) is only the layout: a Canvas Panel with the UAOSHud* elements bound by name
 * (BindWidgetOptional). If the widget tree is empty, the reference layout is built in C++.
 *
 * Created once (pooled) by AShellPawn on the first possession, shown/hidden afterwards.
 */
UCLASS()
class AOS_DK_API UPlayerSubmarineHUDWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void BindToShell(AShellPawn* InShell);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void UnbindFromShell();

	/** Prints "source: message" into the terminal log. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void PushLog(const FString& Source, const FString& Message, EAOSHudLogSeverity Severity = EAOSHudLogSeverity::Info);

	/** Short display glitch pulse (0..1). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void TriggerGlitch(float Strength = 1.f);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|HUD")
	AShellPawn* GetShell() const;

	/**
	 * Reference cockpit layout (Canvas + all elements, anchors for any resolution / aspect ratio).
	 * Used by the editor authoring helper to fill WBP_SubmarineHUD and as the runtime fallback.
	 */
	static void BuildDefaultLayout(UWidgetTree* Tree, TArray<UWidget*>* OutCreated = nullptr);

	virtual bool Initialize() override;

protected:
	virtual void NativeOnInitialized() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
	virtual void NativeDestruct() override;

	// --- Layout (names must match the widgets in WBP_SubmarineHUD) --------------------------------
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|HUD", meta = (BindWidgetOptional))
	TObjectPtr<UAOSHudCockpitFrame> CockpitFrame;

	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|HUD", meta = (BindWidgetOptional))
	TObjectPtr<UAOSHudBatteryGauge> BatteryGauge;

	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|HUD", meta = (BindWidgetOptional))
	TObjectPtr<UAOSHudNavigationTape> NavigationTape;

	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|HUD", meta = (BindWidgetOptional))
	TObjectPtr<UAOSHudCrosshair> Crosshair;

	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|HUD", meta = (BindWidgetOptional))
	TObjectPtr<UAOSHudDroneHoneycomb> DroneHoneycomb;

	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|HUD", meta = (BindWidgetOptional))
	TObjectPtr<UAOSHudTerminalLog> TerminalLog;

	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|HUD", meta = (BindWidgetOptional))
	TObjectPtr<UAOSHudGlitchOverlay> GlitchOverlay;

	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|HUD", meta = (BindWidgetOptional))
	TObjectPtr<UAOSHudKernelPanicPanel> KernelPanicPanel;

	// --- Tuning -------------------------------------------------------------------------------
	/**
	 * true: the tape spans exactly the degrees it covers on screen (camera FOV * tape width / screen width),
	 * so its marks line up with the world. false: arc = camera FOV * CompassArcPerFOV (more context).
	 */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD")
	bool bCompassMatchesCameraFOV = false;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD", meta = (ClampMin = "0.2", ClampMax = "4", EditCondition = "!bCompassMatchesCameraFOV"))
	float CompassArcPerFOV = 1.25f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD", meta = (ClampMin = "0.005", Units = "s"))
	float AimTraceInterval = 0.033f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD", meta = (ClampMin = "0.05", Units = "s"))
	float DamageGlitchDuration = 0.45f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD", meta = (ClampMin = "0", ClampMax = "1"))
	float LowEnergyWarning = 0.25f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD", meta = (ClampMin = "0", ClampMax = "1"))
	float CriticalEnergyWarning = 0.1f;

private:
	void ResolveElements();
	/** Clean slate for a (re)attached session: no leftover panic / glitch / log, values snapped to the Shell. */
	void ResetTransientState(AShellPawn& InShell);
	void ForEachElement(TFunctionRef<void(UAOSHudElement&)> Fn) const;
	void TickTelemetry(AShellPawn& InShell, const FGeometry& MyGeometry);
	void TickAim(AShellPawn& InShell, float Dt);
	void TickDrones(AShellPawn& InShell);

	UFUNCTION()
	void HandleEnergyDamaged(float EnergyLostPercent, float NewFraction, FVector HitLocation, AActor* DamageCauser);

	UFUNCTION()
	void HandleEnergyDepleted();

	UFUNCTION()
	void HandleChargingChanged(bool bCharging, float ChargeRatePercentPerSecond);

	UFUNCTION()
	void HandleChargeComplete();

	UFUNCTION()
	void HandleEnergyRestored(float NewFraction);

	/** RMB reload result -> terminal log. */
	UFUNCTION()
	void HandleDroneReload(ASubDroneBase* Drone, ESubDroneReloadResult Result, float EnergyCostPercent);

	/** A drone projectile ended (hit / surface / expired) -> crosshair hit marker. */
	UFUNCTION()
	void HandleProjectileImpact(ASubDroneBase* Drone, ESubDroneImpactKind Kind, FVector Location, float Damage);

	TWeakObjectPtr<AShellPawn> Shell;
	TWeakObjectPtr<UShellEnergyComponent> BoundEnergy;
	TWeakObjectPtr<USubDroneBayComponent> BoundBay;

	float DamageGlitch = 0.f;
	float PanicAlpha = 0.f;
	float AimTimer = 0.f;
	bool bAimLocked = false;
	float AimDistanceMeters = 0.f;
	float AimHealth = -1.f;
	float AimBearing = 0.f;
	bool bWarnedLow = false;
	bool bWarnedCritical = false;

	TArray<bool> SlotWasLowAmmo;
	TArray<bool> SlotWasRingEmpty;
	TArray<bool> SlotWasDepleted;
	TArray<uint8> SlotLastMobility;
};
