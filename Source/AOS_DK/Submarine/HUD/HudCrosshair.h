#pragma once

#include "CoreMinimal.h"
#include "AOS_DK/Core/UI/HUD/AOSHudElement.h"
#include "HudCrosshair.generated.h"

/**
 * Centre reticle "[ . ]": a dot and two thin square brackets. When the view line trace hits a
 * hostile target the brackets glide apart (target lock) and turn to the lock colour.
 */
UCLASS(meta = (DisplayName = "AOS HUD Crosshair"))
class AOS_DK_API UAOSHudCrosshair : public UAOSHudElement
{
	GENERATED_BODY()

public:
	UAOSHudCrosshair(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetLock(bool bInLocked, float InDistanceMeters);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetDimmed(bool bInDimmed) { bDimmed = bInDimmed; }

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

private:
	bool bLocked = false;
	bool bDimmed = false;
	float LockAlpha = 0.f;
	float DistanceMeters = 0.f;
	float DimAlpha = 0.f;
};
