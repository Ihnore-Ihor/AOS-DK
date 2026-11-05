#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Fonts/SlateFontInfo.h"
#include "EnemyHealthBarWidget.generated.h"

/**
 * 3D health bar of an enemy (Task 5), shown by a UWidgetComponent above the daemon
 * (screen-space overlay or world-space billboard turned to the camera).
 * Thin minimal bar + percentage; the fill colour follows a Dracula gradient
 * Green (full) -> Yellow -> Orange -> Red (critical). A pale "ghost" segment trails the damage.
 * Painted in C++ (NativePaint) - works directly as a native class, a WBP child can restyle it.
 */
UCLASS()
class AOS_DK_API UEnemyHealthBarWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	UEnemyHealthBarWidget(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|EnemyHealth")
	void SetHealthFraction(float Fraction, bool bSnap = false);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|EnemyHealth")
	void SetLabel(const FString& InLabel) { Label = InLabel; }

	/** Engaged = label turns to the threat colour; Charge (0..1) = telegraphed attack. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|EnemyHealth")
	void SetThreat(bool bInEngaged, float InCharge);

	/** Driven by the owning actor (deterministic, independent of widget ticking). */
	void AdvanceDisplay(float DeltaSeconds);

	/** Gradient used by the fill (exposed for reuse). */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|EnemyHealth")
	FLinearColor EvaluateHealthColor(float Fraction) const;

protected:
	virtual int32 NativePaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
		FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|EnemyHealth")
	FVector2D DesignSize = FVector2D(180.0, 46.0);

	UPROPERTY(EditAnywhere, Category = "AOS_DK|EnemyHealth|Colors")
	FLinearColor FullColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|EnemyHealth|Colors")
	FLinearColor MidColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|EnemyHealth|Colors")
	FLinearColor LowColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|EnemyHealth|Colors")
	FLinearColor CriticalColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|EnemyHealth|Colors")
	FLinearColor FrameColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|EnemyHealth|Colors")
	FLinearColor ThreatColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|EnemyHealth", meta = (ClampMin = "0", ClampMax = "1"))
	float CriticalThreshold = 0.2f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|EnemyHealth|Style")
	FSlateFontInfo Font;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|EnemyHealth|Style")
	FSlateFontInfo BoldFont;

private:
	float TargetFraction = 0.85f;
	float DisplayFraction = 0.85f;
	float GhostFraction = 0.85f;
	float GhostHold = 0.f;
	float Time = 0.f;
	float Charge = 0.f;
	bool bEngaged = false;
	FString Label = TEXT("daemon[4127]");
};
