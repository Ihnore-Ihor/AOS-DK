#include "AOSHudElement.h"
#include "AOSHudPainter.h"

#include "Widgets/SLeafWidget.h"
#include "Engine/Font.h"
#include "Styling/CoreStyle.h"
#include "UObject/ConstructorHelpers.h"

#define LOCTEXT_NAMESPACE "AOSHud"

/** Slate leaf that forwards painting to its owning UAOSHudElement. Volatile: repainted every frame. */
class SAOSHudSurface : public SLeafWidget
{
public:
	SLATE_BEGIN_ARGS(SAOSHudSurface) {}
	SLATE_END_ARGS()

	void Construct(const FArguments& InArgs, UAOSHudElement* InOwner)
	{
		Owner = InOwner;
		SetCanTick(false);
		ForceVolatile(true);
	}

	virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
		FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override
	{
		if (const UAOSHudElement* Element = Owner.Get())
		{
			return Element->PaintFromSlate(AllottedGeometry, OutDrawElements, LayerId, InWidgetStyle);
		}
		return LayerId;
	}

	virtual FVector2D ComputeDesiredSize(float LayoutScaleMultiplier) const override
	{
		const UAOSHudElement* Element = Owner.Get();
		return Element ? Element->GetDesignSize() : FVector2D(16.0, 16.0);
	}

private:
	TWeakObjectPtr<UAOSHudElement> Owner;
};

UAOSHudElement::UAOSHudElement(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	struct FFontAssets
	{
		ConstructorHelpers::FObjectFinder<UFont> Regular;
		ConstructorHelpers::FObjectFinder<UFont> Bold;
		FFontAssets()
			: Regular(TEXT("/Game/AOS_DK_Game/Core/UI/Fonts/SpaceMono-Regular_Font.SpaceMono-Regular_Font"))
			, Bold(TEXT("/Game/AOS_DK_Game/Core/UI/Fonts/SpaceMono-Bold_Font.SpaceMono-Bold_Font"))
		{
		}
	};
	static FFontAssets Fonts;

	Font = Fonts.Regular.Succeeded() ? FSlateFontInfo(Fonts.Regular.Object, 12.f) : FCoreStyle::GetDefaultFontStyle("Regular", 12.f);
	BoldFont = Fonts.Bold.Succeeded() ? FSlateFontInfo(Fonts.Bold.Object, 12.f) : FCoreStyle::GetDefaultFontStyle("Bold", 12.f);

	// The HUD never takes the mouse.
	SetVisibilityInternal(ESlateVisibility::HitTestInvisible);
}

TSharedRef<SWidget> UAOSHudElement::RebuildWidget()
{
	Surface = SNew(SAOSHudSurface, this);
	return Surface.ToSharedRef();
}

void UAOSHudElement::ReleaseSlateResources(bool bReleaseChildren)
{
	Super::ReleaseSlateResources(bReleaseChildren);
	Surface.Reset();
}

int32 UAOSHudElement::PaintFromSlate(const FGeometry& AllottedGeometry, FSlateWindowElementList& OutDrawElements,
	int32 LayerId, const FWidgetStyle& InWidgetStyle) const
{
	FAOSHudPainter Painter(AllottedGeometry, OutDrawElements, LayerId, InWidgetStyle,
		FVector2f(float(DesignSize.X), float(DesignSize.Y)), bStretchToFill);
	if (!Painter.IsValid())
	{
		return LayerId;
	}
	PaintHud(Painter);
	return Painter.Layer;
}

#if WITH_EDITOR
const FText UAOSHudElement::GetPaletteCategory()
{
	return LOCTEXT("AOSHudPaletteCategory", "AOS_DK HUD");
}
#endif

#undef LOCTEXT_NAMESPACE
