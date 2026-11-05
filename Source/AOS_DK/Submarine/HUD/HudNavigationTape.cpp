#include "HudNavigationTape.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

namespace
{
	constexpr float TapeLeft = 22.f;
	constexpr float TapeRight = 458.f;
	constexpr float TapeBaseY = 76.f;
	constexpr float CentreX = 240.f;

	const TCHAR* CardinalLabel(int32 Degrees)
	{
		switch (((Degrees % 360) + 360) % 360)
		{
		case 0:   return TEXT("N");
		case 45:  return TEXT("NE");
		case 90:  return TEXT("E");
		case 135: return TEXT("SE");
		case 180: return TEXT("S");
		case 225: return TEXT("SW");
		case 270: return TEXT("W");
		case 315: return TEXT("NW");
		default:  return nullptr;
		}
	}
}

UAOSHudNavigationTape::UAOSHudNavigationTape(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	DesignSize = FVector2D(480.0, 104.0);
	TextColor     = AOSDracula::Foreground();
	CardinalColor = AOSDracula::Cyan();
	TickColor     = AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.8f);
	LabelColor    = AOSDracula::Comment();
	PitchColor    = AOSDracula::Purple();
	TargetColor   = AOSDracula::Pink();
	VisibleArc    = DefaultVisibleArc;
}

void UAOSHudNavigationTape::SetTelemetry(float InDepthMeters, float InHeadingDegrees, float InPitchDegrees)
{
	DepthMeters = FMath::Max(0.f, InDepthMeters);
	Heading = AOSHudMath::ClampDegrees(InHeadingDegrees);
	Pitch = InPitchDegrees;
}

void UAOSHudNavigationTape::SetVisibleArc(float Degrees)
{
	VisibleArc = FMath::Clamp(Degrees, 20.f, 360.f);
}

void UAOSHudNavigationTape::SetTargetBearing(bool bHasTarget, float BearingDegrees)
{
	bHasTargetBearing = bHasTarget;
	if (bHasTarget)
	{
		TargetBearing = AOSHudMath::ClampDegrees(BearingDegrees);
	}
}

void UAOSHudNavigationTape::AdvanceHud(float DeltaSeconds)
{
	Super::AdvanceHud(DeltaSeconds);
	// Shortest-arc smoothing (no 359 -> 0 spin).
	const float Delta = FMath::UnwindDegrees(Heading - DisplayHeading);
	DisplayHeading = AOSHudMath::ClampDegrees(DisplayHeading + Delta * (1.f - FMath::Exp(-HeadingSmoothing * DeltaSeconds)));
	DisplayDepth = AOSHudMath::Approach(DisplayDepth, DepthMeters, 8.f, DeltaSeconds);
	TargetAlpha = AOSHudMath::Approach(TargetAlpha, bHasTargetBearing ? 1.f : 0.f, 10.f, DeltaSeconds);
}

void UAOSHudNavigationTape::ResetHud()
{
	DisplayHeading = Heading;
	DisplayDepth = DepthMeters;
	bHasTargetBearing = false;
	TargetAlpha = 0.f;
	bDegraded = false;
}

void UAOSHudNavigationTape::PaintHud(FAOSHudPainter& P) const
{
	const float Flicker = bDegraded ? (AOSHudMath::Hash01(uint32(HudTime * 18.f) + 7u) > 0.4f ? 1.f : 0.25f) : 1.f;
	auto Fade = [&](float X) -> float
	{
		const float T = FMath::Clamp(FMath::Abs(X - CentreX) / ((TapeRight - TapeLeft) * 0.5f), 0.f, 1.f);
		return (1.f - T * T * T) * Flicker;
	};

	// --- Depth readout ---------------------------------------------------------------------------
	const FString Depth = FString::Printf(TEXT("%d M"), FMath::RoundToInt(DisplayDepth));
	P.Text(Depth, BoldFont, 24.f, FVector2f(CentreX, 22.f), FVector2f(0.5f, 0.5f), AOSDracula::WithAlpha(TextColor, Flicker));
	P.Text(TEXT("DEPTH"), Font, 8.5f, FVector2f(CentreX - 62.f, 24.f), FVector2f(1.f, 0.5f), AOSDracula::WithAlpha(LabelColor, Flicker));
	const FString PitchText = FString::Printf(TEXT("PITCH %+03d°"), FMath::RoundToInt(Pitch));
	P.Text(PitchText, Font, 8.5f, FVector2f(CentreX + 62.f, 24.f), FVector2f(0.f, 0.5f), AOSDracula::WithAlpha(PitchColor, Flicker));

	// --- Heading tape ----------------------------------------------------------------------------
	const float PxPerDeg = (TapeRight - TapeLeft) / FMath::Max(VisibleArc, 1.f);
	const float HalfArc = VisibleArc * 0.5f;

	// Baseline with faded ends (per-point alpha).
	{
		TArray<FVector2f> Points;
		TArray<FLinearColor> Colors;
		constexpr int32 Steps = 24;
		for (int32 i = 0; i <= Steps; ++i)
		{
			const float X = FMath::Lerp(TapeLeft, TapeRight, float(i) / Steps);
			Points.Add(FVector2f(X, TapeBaseY));
			Colors.Add(AOSDracula::WithAlpha(TickColor, TickColor.A * Fade(X)));
		}
		P.Polyline(Points, Colors, 1.2f);
	}

	const int32 FirstTick = FMath::FloorToInt((DisplayHeading - HalfArc) / 5.f) * 5;
	const int32 LastTick = FMath::CeilToInt((DisplayHeading + HalfArc) / 5.f) * 5;
	for (int32 Deg = FirstTick; Deg <= LastTick; Deg += 5)
	{
		const float X = CentreX + FMath::UnwindDegrees(float(Deg) - DisplayHeading) * PxPerDeg;
		if (X < TapeLeft || X > TapeRight)
		{
			continue;
		}
		const float A = Fade(X);
		const int32 Wrapped = ((Deg % 360) + 360) % 360;
		const TCHAR* Cardinal = CardinalLabel(Wrapped);
		const bool bMajor = (Wrapped % 15) == 0;
		const float Height = Cardinal ? 12.f : (bMajor ? 8.f : 4.5f);
		P.Line(FVector2f(X, TapeBaseY), FVector2f(X, TapeBaseY - Height), AOSDracula::WithAlpha(TickColor, TickColor.A * A), Cardinal ? 1.6f : 1.f);

		if (Cardinal)
		{
			const bool bPrimary = (Wrapped % 90) == 0;
			const FLinearColor C = bPrimary ? CardinalColor : AOSDracula::WithAlpha(TextColor, 0.85f);
			P.Text(Cardinal, bPrimary ? BoldFont : Font, bPrimary ? 12.f : 10.f, FVector2f(X, TapeBaseY - 22.f), FVector2f(0.5f, 0.5f), AOSDracula::WithAlpha(C, C.A * A));
		}
		else if (bMajor)
		{
			P.Text(FString::Printf(TEXT("%03d"), Wrapped), Font, 7.5f, FVector2f(X, TapeBaseY - 19.f), FVector2f(0.5f, 0.5f), AOSDracula::WithAlpha(LabelColor, A));
		}
	}

	// Target bearing diamond.
	if (TargetAlpha > 0.01f)
	{
		const float Offset = FMath::Clamp(FMath::UnwindDegrees(TargetBearing - DisplayHeading), -HalfArc, HalfArc);
		const float X = CentreX + Offset * PxPerDeg;
		const FVector2f C(X, TapeBaseY + 4.f);
		const FVector2f Diamond[] = { C + FVector2f(0.f, -4.f), C + FVector2f(4.f, 0.f), C + FVector2f(0.f, 4.f), C + FVector2f(-4.f, 0.f) };
		P.FillConvex(MakeArrayView(Diamond), AOSDracula::WithAlpha(TargetColor, TargetAlpha * Flicker));
	}

	// Lubber mark + numeric heading.
	const FVector2f Mark[] = { FVector2f(CentreX, TapeBaseY + 2.f), FVector2f(CentreX + 6.f, TapeBaseY + 11.f), FVector2f(CentreX - 6.f, TapeBaseY + 11.f) };
	P.FillConvex(MakeArrayView(Mark), AOSDracula::WithAlpha(CardinalColor, Flicker));
	const FString HeadingText = FString::Printf(TEXT("%03d"), FMath::RoundToInt(DisplayHeading) % 360);
	P.Text(HeadingText, BoldFont, 9.f, FVector2f(CentreX, TapeBaseY + 21.f), FVector2f(0.5f, 0.5f), AOSDracula::WithAlpha(CardinalColor, Flicker));
}
