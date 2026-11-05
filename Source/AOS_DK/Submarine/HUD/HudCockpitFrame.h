#pragma once

#include "CoreMinimal.h"
#include "AOS_DK/Core/UI/HUD/AOSHudElement.h"
#include "HudCockpitFrame.generated.h"

/**
 * Full-screen cockpit canopy: dark rounded corners (the viewport of the Shell), a soft vignette
 * that is deeper in the corners, a thin glass rim and a chromatic-aberration fringe (cyan/pink
 * offset lines) along the perimeter. Stretched: adapts to any aspect ratio and resolution.
 */
UCLASS(meta = (DisplayName = "AOS HUD Cockpit Frame"))
class AOS_DK_API UAOSHudCockpitFrame : public UAOSHudElement
{
	GENERATED_BODY()

public:
	UAOSHudCockpitFrame(const FObjectInitializer& ObjectInitializer);

	/** 0..1 damage glitch (fringe spreads, rim flickers). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetGlitch(float InGlitch) { Glitch = FMath::Clamp(InGlitch, 0.f, 1.f); }

	/** 0..1 Kernel Panic tint. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetPanic(float InPanic) { Panic = FMath::Clamp(InPanic, 0.f, 1.f); }

	virtual void ResetHud() override { Glitch = 0.f; Panic = 0.f; }

	/** Canopy corner geometry (instruments that follow the rim, e.g. the arc battery, copy it). */
	float GetCornerRadiusFraction() const { return CornerRadiusFraction; }
	float GetEdgeInset() const { return EdgeInset; }

protected:
	virtual void PaintHud(FAOSHudPainter& Painter) const override;

	/** Corner radius as a fraction of the screen height. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Canopy", meta = (ClampMin = "0.02", ClampMax = "0.5"))
	float CornerRadiusFraction = 0.17f;

	/** Dark frame along the straight edges (design px @1080). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Canopy", meta = (ClampMin = "0"))
	float EdgeInset = 7.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Canopy", meta = (ClampMin = "0"))
	float VignetteEdgeWidth = 55.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Canopy", meta = (ClampMin = "0"))
	float VignetteCornerWidth = 170.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Canopy", meta = (ClampMin = "0", ClampMax = "1"))
	float VignetteEdgeAlpha = 0.32f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Canopy", meta = (ClampMin = "0", ClampMax = "1"))
	float VignetteCornerAlpha = 0.85f;

	/** Offset of the cyan / pink fringe lines from the rim (design px). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Canopy", meta = (ClampMin = "0"))
	float FringeOffset = 2.2f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor FrameColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor RimColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor FringeColorA;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor FringeColorB;

private:
	float Glitch = 0.f;
	float Panic = 0.f;
};
