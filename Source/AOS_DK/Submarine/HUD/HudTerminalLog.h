#pragma once

#include "CoreMinimal.h"
#include "AOS_DK/Core/UI/HUD/AOSHudElement.h"
#include "AOS_DK/Core/UI/HUD/AOSHudTypes.h"
#include "HudTerminalLog.generated.h"

/**
 * Bottom-left system terminal log (Linux-terminal style): every event is printed as a short
 * "source: message" line on its own black translucent plate, typed in, held for a few seconds and
 * faded out. Repeated lines collapse into "x N". The newest line is at the bottom.
 */
UCLASS(meta = (DisplayName = "AOS HUD Terminal Log"))
class AOS_DK_API UAOSHudTerminalLog : public UAOSHudElement
{
	GENERATED_BODY()

public:
	UAOSHudTerminalLog(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void AddLine(const FString& Source, const FString& Message, EAOSHudLogSeverity Severity);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void ClearLog();

	virtual void AdvanceHud(float DeltaSeconds) override;

protected:
	virtual void PaintHud(FAOSHudPainter& Painter) const override;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Log", meta = (ClampMin = "1", ClampMax = "12"))
	int32 MaxLines = 6;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Log", meta = (ClampMin = "0.5", Units = "s"))
	float HoldTime = 4.5f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Log", meta = (ClampMin = "0.05", Units = "s"))
	float FadeTime = 0.8f;

	/** Typing speed of a new line. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Log", meta = (ClampMin = "10"))
	float CharsPerSecond = 95.f;

	/** Identical line within this window -> "x N" instead of a new line. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Log", meta = (ClampMin = "0", Units = "s"))
	float MergeWindow = 1.5f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Log")
	float FontSize = 11.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Log")
	float RowHeight = 28.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor PlateColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor MessageColor;

private:
	struct FLogLine
	{
		FString Source;
		FString Message;
		EAOSHudLogSeverity Severity = EAOSHudLogSeverity::Info;
		float Age = 0.f;
		float Row = 0.f;
		int32 Count = 1;
	};

	FLinearColor GetSeverityColor(EAOSHudLogSeverity Severity) const;

	/** Oldest first. */
	TArray<FLogLine> Lines;
};
