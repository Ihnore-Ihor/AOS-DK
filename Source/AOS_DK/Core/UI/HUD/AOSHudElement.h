#pragma once

#include "CoreMinimal.h"
#include "Components/Widget.h"
#include "Fonts/SlateFontInfo.h"
#include "AOSHudElement.generated.h"

struct FAOSHudPainter;
class SAOSHudSurface;

/**
 * Base of every vector-drawn AOS_DK HUD element.
 * A UMG widget backed by a tiny Slate leaf (SAOSHudSurface) whose OnPaint is routed to PaintHud():
 * all geometry (lines, gauges, hexagons, text) is generated in C++ at paint time - no textures,
 * resolution independent, crisp at any DPI. The UMG Designer is used only to place/anchor the
 * element in a Canvas Panel and to tweak its exposed style values.
 *
 * Default values of every element are "preview" values (the cockpit sketch), so the layout is
 * readable in the Designer without play-in-editor.
 */
UCLASS(Abstract)
class AOS_DK_API UAOSHudElement : public UWidget
{
	GENERATED_BODY()

public:
	UAOSHudElement(const FObjectInitializer& ObjectInitializer);

	/** Advances animations; called every frame by the owning HUD (UPlayerSubmarineHUDWidget). */
	virtual void AdvanceHud(float DeltaSeconds) { HudTime += DeltaSeconds; }

	/**
	 * Drops every transient animation (glitches, fades, panic, locks) and snaps smoothed values to
	 * their current targets. Called by the HUD hub when it is (re)attached to a Shell, so a pooled
	 * HUD never replays the last frames of its previous session.
	 */
	virtual void ResetHud() {}

	/** Paint entry used by the Slate surface. */
	int32 PaintFromSlate(const FGeometry& AllottedGeometry, FSlateWindowElementList& OutDrawElements,
		int32 LayerId, const FWidgetStyle& InWidgetStyle) const;

	FVector2D GetDesignSize() const { return DesignSize; }

	virtual void ReleaseSlateResources(bool bReleaseChildren) override;

#if WITH_EDITOR
	virtual const FText GetPaletteCategory() override;
#endif

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

	/** Override: draw the element (design space, see FAOSHudPainter). */
	virtual void PaintHud(FAOSHudPainter& Painter) const {}

	/** Authoring space; the paint is uniformly fitted (or stretched) into the allotted rect. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|HUD")
	FVector2D DesignSize = FVector2D(200.0, 100.0);

	/** true = fill the whole slot (frames / overlays); false = uniform fit, centred. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|HUD")
	bool bStretchToFill = false;

	/** Regular face (default: SpaceMono Regular from Core/UI/Fonts). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|HUD|Style")
	FSlateFontInfo Font;

	/** Bold face (default: SpaceMono Bold). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|HUD|Style")
	FSlateFontInfo BoldFont;

	float HudTime = 0.f;

	TSharedPtr<SAOSHudSurface> Surface;
};
