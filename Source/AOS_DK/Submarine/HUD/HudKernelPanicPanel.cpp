#include "HudKernelPanicPanel.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

UAOSHudKernelPanicPanel::UAOSHudKernelPanicPanel(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	DesignSize = FVector2D(1000.0, 240.0);
	AlertColor = AOSDracula::Red();
}

void UAOSHudKernelPanicPanel::SetPanicActive(bool bInActive)
{
	if (bInActive && !bActive)
	{
		ActiveTime = 0.f;
		Progress = 0.f;
	}
	bActive = bInActive;
}

void UAOSHudKernelPanicPanel::AdvanceHud(float DeltaSeconds)
{
	Super::AdvanceHud(DeltaSeconds);
	if (bActive)
	{
		ActiveTime += DeltaSeconds;
	}
	Alpha = AOSHudMath::Approach(Alpha, bActive ? 1.f : 0.f, bActive ? 14.f : 6.f, DeltaSeconds);
}

void UAOSHudKernelPanicPanel::ResetHud()
{
	bActive = false;
	ActiveTime = 0.f;
	Alpha = 0.f;
	Progress = 0.f;
}

void UAOSHudKernelPanicPanel::PaintHud(FAOSHudPainter& P) const
{
	const bool bPreview = IsDesignTime() && bPreviewInDesigner;
	const float A = bPreview ? 1.f : Alpha;
	if (A <= 0.01f)
	{
		return;
	}
	const float T = bPreview ? 10.f : ActiveTime;
	const uint32 Step = uint32(HudTime * 20.f);
	const float Jitter = (AOSHudMath::Hash01(Step * 31u + 3u) > 0.82f) ? (AOSHudMath::Hash01(Step) - 0.5f) * 18.f : 0.f;

	const FVector2f Min(40.f, 26.f), Max(960.f, 214.f);
	P.FillRect(Min, Max, AOSDracula::WithAlpha(AOSDracula::Background(), 0.9f * A));
	P.FillRect(Min, FVector2f(Min.X + 6.f, Max.Y), AOSDracula::WithAlpha(AlertColor, A));
	P.StrokeRect(Min, Max, AOSDracula::WithAlpha(AlertColor, 0.85f * A), 1.6f);
	P.NextLayer();

	P.Text(TEXT("core dump -> /dev/shell0"), Font, 8.5f, FVector2f(940.f, 44.f), FVector2f(1.f, 0.5f), AOSDracula::WithAlpha(AOSDracula::Comment(), A));

	// Headline (with a red/cyan split ghost on glitch frames).
	const FVector2f HeadPos(76.f + Jitter, 84.f);
	if (FMath::Abs(Jitter) > 0.f)
	{
		P.Text(HeadlineText, BoldFont, 26.f, HeadPos + FVector2f(-3.f, 0.f), FVector2f(0.f, 0.5f), AOSDracula::WithAlpha(AOSDracula::Cyan(), 0.45f * A));
	}
	P.Text(HeadlineText, BoldFont, 26.f, HeadPos, FVector2f(0.f, 0.5f), AOSDracula::WithAlpha(AlertColor, A));

	// Typed detail line + cursor.
	const int32 Chars = FMath::Clamp(FMath::FloorToInt(FMath::Max(0.f, T - 0.25f) * CharsPerSecond), 0, DetailText.Len());
	const FString Typed = DetailText.Left(Chars);
	const FVector2f DetailPos(78.f, 132.f);
	const FVector2f Size = P.Text(Typed, Font, 15.f, DetailPos, FVector2f(0.f, 0.5f), AOSDracula::WithAlpha(AOSDracula::Foreground(), A));
	if (Chars < DetailText.Len() || FMath::Frac(HudTime * 1.8f) < 0.55f)
	{
		P.FillRect(FVector2f(DetailPos.X + Size.X + 3.f, DetailPos.Y - 9.f), FVector2f(DetailPos.X + Size.X + 12.f, DetailPos.Y + 9.f),
			AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.8f * A));
	}

	// Recovery progress.
	const float Pr = bPreview ? 0.64f : Progress;
	const FVector2f BarMin(78.f, 172.f), BarMax(922.f, 180.f);
	P.StrokeRect(BarMin, BarMax, AOSDracula::WithAlpha(AOSDracula::Comment(), A), 1.f);
	P.FillRect(BarMin + FVector2f(1.5f, 1.5f), FVector2f(FMath::Lerp(BarMin.X + 1.5f, BarMax.X - 1.5f, Pr), BarMax.Y - 1.5f),
		AOSDracula::WithAlpha(AOSDracula::Mix(AlertColor, AOSDracula::Orange(), Pr), A));
	P.Text(FString::Printf(TEXT("surface recovery %d%%"), FMath::RoundToInt(Pr * 100.f)), Font, 8.5f, FVector2f(922.f, 196.f), FVector2f(1.f, 0.5f),
		AOSDracula::WithAlpha(AOSDracula::Comment(), A));
}
