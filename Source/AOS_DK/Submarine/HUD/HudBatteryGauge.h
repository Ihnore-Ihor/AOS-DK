#pragma once

#include "CoreMinimal.h"
#include "AOS_DK/Core/UI/HUD/AOSHudElement.h"
#include "AOS_DK/Submarine/Energy/ShellEnergyComponent.h"
#include "HudBatteryGauge.generated.h"

/**
 * Top-left canopy gauge: core energy (= Shell health). The block fills the rounded top-left corner of the
 * canopy from the top rim down: its top and bottom edges are strictly HORIZONTAL (Y = const), its left and
 * right faces are ARCS with the canopy-rim radius - the left one parallel to the rim, the right one the same
 * arc shifted right by BlockWidth (a concentric smaller arc cannot reach the top rim). Every horizontal
 * stripe therefore has the same length. The element is stretched over the whole HUD exactly like the
 * frame (same design height), so the faces follow the rim at any resolution / aspect ratio.
 *  - SegmentCount HORIZONTAL stripes (10 % each), stacked bottom -> top; each one is bounded left / right
 *    by the two arcs. The active stripe THINS with the charge left in its step and then goes out.
 *  - The percentage sits in a clean rectangular aperture: the stripes are clipped around it exactly.
 *  - Balance readout under the block: neutral / "v -1.5%/s" drain / "^ +8.5%/s" dock charge.
 */
UCLASS(meta = (DisplayName = "AOS HUD Battery Gauge"))
class AOS_DK_API UAOSHudBatteryGauge : public UAOSHudElement
{
	GENERATED_BODY()

public:
	UAOSHudBatteryGauge(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetEnergyFraction(float Fraction, bool bSnap = false);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetBalance(EShellEnergyFlow InFlow, float InRatePercentPerSecond);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetStatus(bool bInCharging, bool bInHalted);

	/** Canopy corner the arc follows (synced from UAOSHudCockpitFrame by the HUD hub). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetCanopyGeometry(float InCornerRadiusFraction, float InEdgeInset);

	virtual void AdvanceHud(float DeltaSeconds) override;
	virtual void ResetHud() override;

protected:
	virtual void PaintHud(FAOSHudPainter& Painter) const override;

	/** Fill follow speed (exponential, 1/s): the level glides, it never jumps. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery", meta = (ClampMin = "0.5"))
	float FillSmoothing = 5.f;

	/** Stripes = energy steps (10 -> 10 % each). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery", meta = (ClampMin = "2", ClampMax = "20"))
	int32 SegmentCount = 10;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery", meta = (ClampMin = "0", ClampMax = "1"))
	float LowThreshold = 0.25f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery", meta = (ClampMin = "0", ClampMax = "1"))
	float CriticalThreshold = 0.12f;

	// --- Block geometry (design space = the whole canopy, 1080 units high) ------------------------
	/** Must match UAOSHudCockpitFrame (the hub copies the frame values at runtime). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery|Block", meta = (ClampMin = "0.02", ClampMax = "0.5"))
	float CornerRadiusFraction = 0.17f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery|Block", meta = (ClampMin = "0"))
	float EdgeInset = 7.f;

	/** Clear water between the canopy rim and the left arc face (also above the top edge). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery|Block", meta = (ClampMin = "0"))
	float RimClearance = 10.f;

	/** Horizontal length of every stripe (offset of the right arc face from the left one). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery|Block", meta = (ClampMin = "40"))
	float BlockWidth = 104.f;

	/** Gap between the top edge and the highest point of the left arc (the top rim level). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery|Block", meta = (ClampMin = "5"))
	float TopGap = 6.f;

	/** Bottom edge below the corner centre (the rim is straight from there on). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery|Block", meta = (ClampMin = "-60", ClampMax = "40"))
	float BottomOffset = 24.f;

	/** Clear gap between two stripes; the stripe thickness follows from the block height. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery|Block", meta = (ClampMin = "0"))
	float StripeGap = 3.f;

	// --- Readout ---------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery|Readout", meta = (ClampMin = "6"))
	float PercentFontSize = 20.f;

	/** Clear margin of the aperture around the widest readout ("100%"). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery|Readout")
	FVector2D AperturePadding = FVector2D(6.0, 3.0);

	/** Preferred height of the aperture in the block (0 = top, 1 = bottom); the free span decides first. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Battery|Readout", meta = (ClampMin = "0", ClampMax = "1"))
	float ApertureHeightRatio = 0.62f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor FillColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor LowColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor CriticalColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor ChargeColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor DrainColor;

	/** Muted light tone of a zero balance. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor NeutralColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor OutlineColor;

	/** Empty (discharged) stripes. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor GlassColor;

	/** Dark plate inside the percent aperture. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor ApertureColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor LabelColor;

private:
	struct FBlockLayout
	{
		FVector2f LeftCentre = FVector2f::ZeroVector;  // canopy corner centre (shared with the rim)
		FVector2f RightCentre = FVector2f::ZeroVector; // LeftCentre + (BlockWidth, 0)
		float LeftRadius = 0.f;                         // left face
		float RightRadius = 0.f;                        // right face
		float Top = 0.f;                                // horizontal top edge
		float Bottom = 0.f;                             // horizontal bottom edge
		FVector2f HoleMin = FVector2f::ZeroVector;
		FVector2f HoleMax = FVector2f::ZeroVector;

		float LeftX(float Y) const;
		float RightX(float Y) const;
	};
	FBlockLayout ComputeLayout(const FAOSHudPainter& P) const;
	FLinearColor GetLevelColor(float Fraction) const;

	// Preview values = the cockpit sketch (35 %, -0.2 %/s).
	float TargetFraction = 0.35f;
	float DisplayFraction = 0.35f;
	float Rate = -0.2f;
	EShellEnergyFlow Flow = EShellEnergyFlow::Drain;
	bool bCharging = false;
	bool bHalted = false;
	float ChargeAlpha = 0.f;
	float HaltAlpha = 0.f;
};
