#include "EnemyHealthBarWidget.h"

#include "AOS_DK/Core/UI/AOSDraculaPalette.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "Engine/Font.h"
#include "Styling/CoreStyle.h"
#include "UObject/ConstructorHelpers.h"

UEnemyHealthBarWidget::UEnemyHealthBarWidget(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	FullColor     = AOSDracula::Green();
	MidColor      = AOSDracula::Yellow();
	LowColor      = AOSDracula::Orange();
	CriticalColor = AOSDracula::Red();
	FrameColor    = AOSDracula::Comment();
	ThreatColor   = AOSDracula::Pink();

	static ConstructorHelpers::FObjectFinder<UFont> Regular(TEXT("/Game/AOS_DK_Game/Core/UI/Fonts/SpaceMono-Regular_Font.SpaceMono-Regular_Font"));
	static ConstructorHelpers::FObjectFinder<UFont> Bold(TEXT("/Game/AOS_DK_Game/Core/UI/Fonts/SpaceMono-Bold_Font.SpaceMono-Bold_Font"));
	Font = Regular.Succeeded() ? FSlateFontInfo(Regular.Object, 9.f) : FCoreStyle::GetDefaultFontStyle("Regular", 9.f);
	BoldFont = Bold.Succeeded() ? FSlateFontInfo(Bold.Object, 9.f) : FCoreStyle::GetDefaultFontStyle("Bold", 9.f);
}

void UEnemyHealthBarWidget::SetHealthFraction(float Fraction, bool bSnap)
{
	const float Clamped = FMath::Clamp(Fraction, 0.f, 1.f);
	if (Clamped < TargetFraction)
	{
		GhostHold = 0.45f; // the ghost waits, then drains to the new value
	}
	TargetFraction = Clamped;
	if (bSnap)
	{
		DisplayFraction = GhostFraction = Clamped;
	}
}

void UEnemyHealthBarWidget::SetThreat(bool bInEngaged, float InCharge)
{
	bEngaged = bInEngaged;
	Charge = FMath::Clamp(InCharge, 0.f, 1.f);
}

void UEnemyHealthBarWidget::AdvanceDisplay(float DeltaSeconds)
{
	Time += DeltaSeconds;
	DisplayFraction = AOSHudMath::Approach(DisplayFraction, TargetFraction, 14.f, DeltaSeconds);
	GhostHold -= DeltaSeconds;
	if (GhostHold <= 0.f)
	{
		GhostFraction = AOSHudMath::Approach(GhostFraction, DisplayFraction, 4.f, DeltaSeconds);
	}
	GhostFraction = FMath::Max(GhostFraction, DisplayFraction);
}

FLinearColor UEnemyHealthBarWidget::EvaluateHealthColor(float Fraction) const
{
	// Full -> mid -> low -> critical (piecewise linear in linear space).
	if (Fraction >= 0.6f)
	{
		return AOSDracula::Mix(MidColor, FullColor, (Fraction - 0.6f) / 0.4f);
	}
	if (Fraction >= 0.35f)
	{
		return AOSDracula::Mix(LowColor, MidColor, (Fraction - 0.35f) / 0.25f);
	}
	return AOSDracula::Mix(CriticalColor, LowColor, FMath::Max(0.f, Fraction - CriticalThreshold * 0.5f) / FMath::Max(0.35f - CriticalThreshold * 0.5f, 0.01f));
}

int32 UEnemyHealthBarWidget::NativePaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
	FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
	const int32 BaseLayer = Super::NativePaint(Args, AllottedGeometry, MyCullingRect, OutDrawElements, LayerId, InWidgetStyle, bParentEnabled);

	FAOSHudPainter P(AllottedGeometry, OutDrawElements, BaseLayer + 1, InWidgetStyle, FVector2f(float(DesignSize.X), float(DesignSize.Y)), false);
	if (!P.IsValid())
	{
		return BaseLayer;
	}

	const float F = FMath::Clamp(DisplayFraction, 0.f, 1.f);
	const bool bCritical = F < CriticalThreshold;
	const float Pulse = bCritical ? 0.5f + 0.5f * FMath::Sin(Time * 2.f * PI * 2.5f) : 0.f;
	const FLinearColor Fill = AOSDracula::Mix(EvaluateHealthColor(F), AOSDracula::Foreground(), 0.35f * Pulse);

	// Label + percentage above the bar.
	const FLinearColor LabelColor = bEngaged ? AOSDracula::Mix(ThreatColor, AOSDracula::Red(), Charge) : FrameColor;
	P.Text(Label, Font, 8.5f, FVector2f(10.f, 13.f), FVector2f(0.f, 0.5f), LabelColor);
	P.Text(FString::Printf(TEXT("%d%%"), FMath::CeilToInt(F * 100.f)), BoldFont, 10.f, FVector2f(170.f, 13.f), FVector2f(1.f, 0.5f), Fill);

	// Bar: back plate, trailing ghost, gradient-coloured fill, 10 % notches, thin frame.
	const FVector2f Min(10.f, 25.f), Max(170.f, 33.f);
	const float Width = Max.X - Min.X;
	P.FillRect(Min, Max, AOSDracula::WithAlpha(AOSDracula::Background(), 0.78f));
	if (GhostFraction > F + 0.002f)
	{
		P.FillRect(FVector2f(Min.X + Width * F, Min.Y + 1.f), FVector2f(Min.X + Width * GhostFraction, Max.Y - 1.f), AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.38f));
	}
	if (F > 0.001f)
	{
		FAOSHudMesh Mesh;
		Mesh.AddQuadGradientV(FVector2f(Min.X + 1.f, Min.Y + 1.f), FVector2f(Min.X + Width * F, Max.Y - 1.f),
			AOSDracula::WithAlpha(Fill, 1.f), AOSDracula::WithAlpha(Fill, 0.7f));
		P.DrawMesh(Mesh);
	}
	for (int32 i = 1; i < 10; ++i)
	{
		const float X = Min.X + Width * float(i) / 10.f;
		P.Line(FVector2f(X, Min.Y + 1.f), FVector2f(X, Max.Y - 1.f), AOSDracula::WithAlpha(AOSDracula::Background(), 0.6f), 1.f);
	}
	P.StrokeRect(Min, Max, AOSDracula::WithAlpha(bEngaged ? LabelColor : FrameColor, 0.9f), 1.f);

	// Telegraph warning chevrons.
	if (Charge > 0.01f)
	{
		const float A = Charge * (0.6f + 0.4f * FMath::Sin(Time * 2.f * PI * 6.f));
		P.Line(FVector2f(Min.X - 7.f, Min.Y), FVector2f(Min.X - 3.f, (Min.Y + Max.Y) * 0.5f), AOSDracula::WithAlpha(AOSDracula::Red(), A), 1.4f);
		P.Line(FVector2f(Min.X - 3.f, (Min.Y + Max.Y) * 0.5f), FVector2f(Min.X - 7.f, Max.Y), AOSDracula::WithAlpha(AOSDracula::Red(), A), 1.4f);
		P.Line(FVector2f(Max.X + 7.f, Min.Y), FVector2f(Max.X + 3.f, (Min.Y + Max.Y) * 0.5f), AOSDracula::WithAlpha(AOSDracula::Red(), A), 1.4f);
		P.Line(FVector2f(Max.X + 3.f, (Min.Y + Max.Y) * 0.5f), FVector2f(Max.X + 7.f, Max.Y), AOSDracula::WithAlpha(AOSDracula::Red(), A), 1.4f);
	}
	return P.Layer;
}
