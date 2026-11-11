#pragma once

#include "CoreMinimal.h"
#include "AOS_DK/Core/UI/HUD/AOSHudElement.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneTypes.h"
#include "HudCrosshair.generated.h"

/**
 * Centre reticle "[ . ]": a dot and two thin square brackets. When the view line trace hits a
 * hostile target the brackets glide apart (target lock), turn to the lock colour (Pink) and show the
 * range + the target's health bar. An interactable in focus (<= 8 m) instead keeps the brackets idle,
 * tints them Cyan and shows the "[F] <ACTION>" prompt under the reticle (bold, Cyan; "[F] FULL" dimmed).
 * Lock and prompt are exclusive: combat telemetry always wins.
 */
UCLASS(meta = (DisplayName = "AOS HUD Crosshair"))
class AOS_DK_API UAOSHudCrosshair : public UAOSHudElement
{
	GENERATED_BODY()

public:
	UAOSHudCrosshair(const FObjectInitializer& ObjectInitializer);

	/** InHealthFraction < 0: no health bar. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetLock(bool bInLocked, float InDistanceMeters, float InHealthFraction = -1.f);

	/** bInAvailable = false -> "[F] <action>" drawn in dimmed Foreground (e.g. FULL). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetInteractPrompt(bool bInShow, const FText& InAction, bool bInAvailable);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetDimmed(bool bInDimmed) { bDimmed = bInDimmed; }

	/**
	 * Hit confirmation: four diagonal ticks burst away from the centre (X marker). Target = large, white to
	 * pink; Surface = small cyan; Expired (nothing hit) = no marker.
	 */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void PulseHit(ESubDroneImpactKind Kind);

	virtual void AdvanceHud(float DeltaSeconds) override;
	virtual void ResetHud() override;

protected:
	virtual void PaintHud(FAOSHudPainter& Painter) const override;

	/** Half gap between the brackets: idle / locked (design px). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Crosshair")
	float IdleGap = 17.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Crosshair")
	float LockedGap = 40.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Crosshair", meta = (ClampMin = "1"))
	float LockSpeed = 11.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor IdleColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor LockColor;

	/** "[F] SALVAGE ..." colour (Dracula Cyan 8BE9FD). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor PromptColor;

	/** "[F] FULL" / refused: Foreground at this alpha. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style", meta = (ClampMin = "0", ClampMax = "1"))
	float PromptUnavailableAlpha = 0.4f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Crosshair", meta = (ClampMin = "4"))
	float PromptSize = 12.f;

	/** Lifetime of the hit marker (s). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Crosshair", meta = (ClampMin = "0.05", Units = "s"))
	float HitMarkerDuration = 0.34f;

private:
	bool bLocked = false;
	bool bDimmed = false;
	float LockAlpha = 0.f;
	float DistanceMeters = 0.f;
	float HealthFraction = -1.f;
	float DimAlpha = 0.f;

	float HitAlpha = 0.f;
	ESubDroneImpactKind HitKind = ESubDroneImpactKind::Expired;

	bool bPrompt = false;
	bool bPromptAvailable = true;
	float PromptAlpha = 0.f;
	FString PromptText;
};
