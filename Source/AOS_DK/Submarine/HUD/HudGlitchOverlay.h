#pragma once

#include "CoreMinimal.h"
#include "AOS_DK/Core/UI/HUD/AOSHudElement.h"
#include "HudGlitchOverlay.generated.h"

/**
 * Full-screen "system glitch" of the cockpit display (vector, deterministic - hash driven, no
 * textures): torn scan bands with a cyan/pink RGB split, dead-pixel blocks and scanlines.
 *  - Damage pulse: short cyan/pink tear (driven by SetIntensity, decays in the HUD hub).
 *  - Kernel Panic: sustained red tear + red wash + rolling bar.
 * The camera post-process fringe (AShellPawn) is the matching world-space half of the effect.
 */
UCLASS(meta = (DisplayName = "AOS HUD Glitch Overlay"))
class AOS_DK_API UAOSHudGlitchOverlay : public UAOSHudElement
{
	GENERATED_BODY()

public:
	UAOSHudGlitchOverlay(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetIntensity(float InIntensity) { Intensity = FMath::Clamp(InIntensity, 0.f, 1.f); }

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetPanic(float InPanic) { Panic = FMath::Clamp(InPanic, 0.f, 1.f); }

	virtual void ResetHud() override { Intensity = 0.f; Panic = 0.f; }

protected:
	virtual void PaintHud(FAOSHudPainter& Painter) const override;

	/** Tear refresh rate (stutter frequency). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Glitch", meta = (ClampMin = "1"))
	float StepsPerSecond = 24.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Glitch", meta = (ClampMin = "0", ClampMax = "64"))
	int32 MaxBands = 14;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Glitch", meta = (ClampMin = "0", ClampMax = "64"))
	int32 MaxBlocks = 18;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Glitch", meta = (ClampMin = "2"))
	float ScanlineSpacing = 4.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor SplitColorA;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor SplitColorB;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor PanicColor;

private:
	float Intensity = 0.f;
	float Panic = 0.f;
};
