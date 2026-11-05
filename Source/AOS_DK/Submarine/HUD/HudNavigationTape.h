#pragma once

#include "CoreMinimal.h"
#include "AOS_DK/Core/UI/HUD/AOSHudElement.h"
#include "HudNavigationTape.generated.h"

/**
 * Top-centre navigation block: digital depth below the sea surface ("102 M"), pitch readout and a
 * horizontal heading tape directly under the depth. The tape can match the camera FOV so its
 * marks line up with the world at any field of view / aspect ratio.
 */
UCLASS(meta = (DisplayName = "AOS HUD Navigation Tape"))
class AOS_DK_API UAOSHudNavigationTape : public UAOSHudElement
{
	GENERATED_BODY()

public:
	UAOSHudNavigationTape(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetTelemetry(float InDepthMeters, float InHeadingDegrees, float InPitchDegrees);

	/** Degrees covered by the tape width (computed from the camera FOV by the HUD hub). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetVisibleArc(float Degrees);

	/** Bearing marker of the locked target on the tape. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetTargetBearing(bool bHasTarget, float BearingDegrees);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetDegraded(bool bInDegraded) { bDegraded = bInDegraded; }

	virtual void AdvanceHud(float DeltaSeconds) override;
	virtual void ResetHud() override;

protected:
	virtual void PaintHud(FAOSHudPainter& Painter) const override;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Compass", meta = (ClampMin = "20", ClampMax = "360"))
	float DefaultVisibleArc = 110.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Compass", meta = (ClampMin = "1"))
	float HeadingSmoothing = 14.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor TextColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor CardinalColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor TickColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor LabelColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor PitchColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor TargetColor;

private:
	// Preview = sketch: 102 M, heading between E and S.
	float DepthMeters = 102.f;
	float DisplayDepth = 102.f;
	float Heading = 118.f;
	float DisplayHeading = 118.f;
	float Pitch = 0.f;
	float VisibleArc = 110.f;
	bool bHasTargetBearing = false;
	float TargetBearing = 0.f;
	float TargetAlpha = 0.f;
	bool bDegraded = false;
};
