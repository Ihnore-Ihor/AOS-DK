#pragma once

#include "CoreMinimal.h"
#include "AOS_DK/Core/UI/HUD/AOSHudElement.h"
#include "HudKernelPanicPanel.generated.h"

/**
 * Centre system message shown when the core is depleted:
 *   [FATAL] KERNEL PANIC: CORE DEPLETED
 *   System halted. Emergency surface recovery initiated...
 * with a typed second line, blinking cursor, horizontal glitch jitter and a recovery progress bar.
 */
UCLASS(meta = (DisplayName = "AOS HUD Kernel Panic Panel"))
class AOS_DK_API UAOSHudKernelPanicPanel : public UAOSHudElement
{
	GENERATED_BODY()

public:
	UAOSHudKernelPanicPanel(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetPanicActive(bool bInActive);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetRecoveryProgress(float InProgress) { Progress = FMath::Clamp(InProgress, 0.f, 1.f); }

	virtual void AdvanceHud(float DeltaSeconds) override;
	virtual void ResetHud() override;

protected:
	virtual void PaintHud(FAOSHudPainter& Painter) const override;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Panic")
	FString HeadlineText = TEXT("[FATAL] KERNEL PANIC: CORE DEPLETED");

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Panic")
	FString DetailText = TEXT("System halted. Emergency surface recovery initiated...");

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Panic", meta = (ClampMin = "5"))
	float CharsPerSecond = 48.f;

	/** Show the panel in the Designer (layout preview). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Panic")
	bool bPreviewInDesigner = false;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor AlertColor;

private:
	bool bActive = false;
	float ActiveTime = 0.f;
	float Alpha = 0.f;
	float Progress = 0.f;
};
