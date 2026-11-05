#include "HudBatteryGauge.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

namespace
{
	/** Clear gap between the clipped stripe ends and the aperture plate. */
	constexpr float ApertureGap = 2.5f;

	/** Vertical slicing step of a stripe (each slice is a convex trapezoid between the two arcs). */
	constexpr float SliceStep = 2.5f;
}

float UAOSHudBatteryGauge::FBlockLayout::LeftX(float Y) const
{
	return AOSHudMath::CircleLeftX(LeftCentre, LeftRadius, Y);
}

float UAOSHudBatteryGauge::FBlockLayout::RightX(float Y) const
{
	return AOSHudMath::CircleLeftX(RightCentre, RightRadius, Y);
}

namespace
{
	/**
	 * Horizontal stripe [Y0, Y1] bounded by the two arc faces, minus the aperture rectangle. The stripe is
	 * sliced into thin horizontal trapezoids (convex even where the inner arc bulges in), each one clipped
	 * exactly against the aperture. Vertex colours are evaluated per position -> seamless clipped edges.
	 */
	template <typename LayoutT>
	void AddBlockStripe(FAOSHudMesh& Mesh, const LayoutT& L, float Y0, float Y1, const FVector2f& HoleMin, const FVector2f& HoleMax,
		TFunctionRef<FLinearColor(const FVector2f&)> ColorAt)
	{
		if (Y1 - Y0 < 0.05f)
		{
			return;
		}
		const int32 Slices = FMath::Clamp(FMath::CeilToInt((Y1 - Y0) / SliceStep), 1, 64);
		TArray<TArray<FVector2f>> Pieces;
		TArray<FLinearColor> Colors;
		for (int32 s = 0; s < Slices; ++s)
		{
			const float YA = FMath::Lerp(Y0, Y1, float(s) / float(Slices));
			const float YB = FMath::Lerp(Y0, Y1, float(s + 1) / float(Slices));
			const FVector2f Quad[4] =
			{
				FVector2f(L.LeftX(YA), YA), FVector2f(L.RightX(YA), YA), FVector2f(L.RightX(YB), YB), FVector2f(L.LeftX(YB), YB)
			};
			Pieces.Reset();
			AOSHudMath::SubtractRect(MakeArrayView(Quad, 4), HoleMin, HoleMax, Pieces);
			for (const TArray<FVector2f>& Piece : Pieces)
			{
				Colors.Reset();
				for (const FVector2f& V : Piece)
				{
					Colors.Add(ColorAt(V));
				}
				Mesh.AddConvex(Piece, Colors);
			}
		}
	}
}

UAOSHudBatteryGauge::UAOSHudBatteryGauge(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	// Same design space as the canopy frame: stretched over the whole HUD, 1080 units high.
	DesignSize = FVector2D(1920.0, 1080.0);
	bStretchToFill = true;
	FillColor     = AOSDracula::Yellow();
	LowColor      = AOSDracula::Orange();
	CriticalColor = AOSDracula::Red();
	ChargeColor   = AOSDracula::Green();
	DrainColor    = AOSDracula::Orange();
	NeutralColor  = AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.55f);
	OutlineColor  = AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.6f);
	GlassColor    = AOSDracula::WithAlpha(AOSDracula::Mix(AOSDracula::Background(), FLinearColor::Black, 0.3f), 0.55f);
	ApertureColor = AOSDracula::WithAlpha(AOSDracula::Mix(AOSDracula::Background(), FLinearColor::Black, 0.55f), 0.7f);
	LabelColor    = AOSDracula::Comment();
}

void UAOSHudBatteryGauge::SetEnergyFraction(float Fraction, bool bSnap)
{
	TargetFraction = FMath::Clamp(Fraction, 0.f, 1.f);
	if (bSnap)
	{
		DisplayFraction = TargetFraction;
	}
}

void UAOSHudBatteryGauge::SetBalance(EShellEnergyFlow InFlow, float InRatePercentPerSecond)
{
	Flow = InFlow;
	Rate = InRatePercentPerSecond;
}

void UAOSHudBatteryGauge::SetStatus(bool bInCharging, bool bInHalted)
{
	bCharging = bInCharging;
	bHalted = bInHalted;
}

void UAOSHudBatteryGauge::SetCanopyGeometry(float InCornerRadiusFraction, float InEdgeInset)
{
	CornerRadiusFraction = FMath::Clamp(InCornerRadiusFraction, 0.02f, 0.5f);
	EdgeInset = FMath::Max(0.f, InEdgeInset);
}

void UAOSHudBatteryGauge::AdvanceHud(float DeltaSeconds)
{
	Super::AdvanceHud(DeltaSeconds);
	DisplayFraction = AOSHudMath::Approach(DisplayFraction, TargetFraction, FillSmoothing, DeltaSeconds);
	ChargeAlpha = AOSHudMath::Approach(ChargeAlpha, bCharging ? 1.f : 0.f, 6.f, DeltaSeconds);
	HaltAlpha = AOSHudMath::Approach(HaltAlpha, bHalted ? 1.f : 0.f, 8.f, DeltaSeconds);
}

void UAOSHudBatteryGauge::ResetHud()
{
	DisplayFraction = TargetFraction;
	ChargeAlpha = bCharging ? 1.f : 0.f;
	HaltAlpha = bHalted ? 1.f : 0.f;
}

FLinearColor UAOSHudBatteryGauge::GetLevelColor(float Fraction) const
{
	FLinearColor Color;
	if (Fraction >= 0.5f)
	{
		Color = FillColor;
	}
	else if (Fraction >= LowThreshold)
	{
		Color = AOSDracula::Mix(LowColor, FillColor, (Fraction - LowThreshold) / FMath::Max(0.5f - LowThreshold, 0.01f));
	}
	else
	{
		Color = AOSDracula::Mix(CriticalColor, LowColor, Fraction / FMath::Max(LowThreshold, 0.01f));
	}
	return AOSDracula::Mix(Color, ChargeColor, 0.45f * ChargeAlpha);
}

UAOSHudBatteryGauge::FBlockLayout UAOSHudBatteryGauge::ComputeLayout(const FAOSHudPainter& P) const
{
	FBlockLayout L;
	const FVector2f Extent = P.Extent();
	// Identical to UAOSHudCockpitFrame::PaintHud: the left face runs parallel to the canopy rim, the right
	// face is the same arc shifted by BlockWidth, so both exist up to the top rim and every stripe is equally long.
	const float RimRadius = FMath::Min(Extent.Y * CornerRadiusFraction, Extent.X * 0.45f);
	const FVector2f Centre(EdgeInset + RimRadius, EdgeInset + RimRadius);
	L.LeftCentre = Centre;
	L.RightCentre = Centre + FVector2f(BlockWidth, 0.f);
	L.LeftRadius = FMath::Max(RimRadius - RimClearance, 20.f);
	L.RightRadius = L.LeftRadius;
	// Top edge right under the top rim: the highest point of the left arc is at EdgeInset + RimClearance.
	L.Top = Centre.Y - L.LeftRadius + TopGap;
	L.Bottom = FMath::Max(Centre.Y + BottomOffset, L.Top + 40.f);

	// Aperture: sized for the widest readout ("100%") so it never changes size; the height follows the glyphs
	// (digit height ~ 1.3 x point size in design units), not the taller line box. The faces are steep near the
	// bottom and flat near the top rim, so the aperture goes to the row band with the widest free span
	// between the faces (ties -> closest to ApertureHeightRatio) and is centred in that span.
	const float TextWidth = P.MeasureText(TEXT("100%"), BoldFont, PercentFontSize).X;
	const FVector2f Half = FVector2f(0.5f * TextWidth, 0.66f * PercentFontSize) + FVector2f(AperturePadding) + FVector2f(ApertureGap);
	const float MinCentre = L.Top + Half.Y + 3.f;
	const float MaxCentre = FMath::Max(L.Bottom - Half.Y - 3.f, MinCentre);
	const float Preferred = FMath::Lerp(L.Top, L.Bottom, ApertureHeightRatio);
	float BestScore = -TNumericLimits<float>::Max();
	FVector2f Best = FVector2f(0.5f * (L.LeftX(Preferred) + L.RightX(Preferred)), Preferred);
	for (int32 c = 0; c <= 24; ++c)
	{
		const float CentreY = FMath::Lerp(MinCentre, MaxCentre, float(c) / 24.f);
		float MinRight = TNumericLimits<float>::Max();
		float MaxLeft = -TNumericLimits<float>::Max();
		for (int32 i = 0; i <= 6; ++i)
		{
			const float Y = CentreY - Half.Y + 2.f * Half.Y * float(i) / 6.f;
			MaxLeft = FMath::Max(MaxLeft, L.LeftX(Y));
			MinRight = FMath::Min(MinRight, L.RightX(Y));
		}
		// A fitting band wins; among fitting bands the one nearest to the preferred height.
		const float Spare = (MinRight - MaxLeft) - 2.f * Half.X;
		const float Score = FMath::Min(Spare, 6.f) - 0.02f * FMath::Abs(CentreY - Preferred);
		if (Score > BestScore)
		{
			BestScore = Score;
			Best = FVector2f(0.5f * (MaxLeft + MinRight), CentreY);
		}
	}
	L.HoleMin = Best - Half;
	L.HoleMax = Best + Half;
	return L;
}

void UAOSHudBatteryGauge::PaintHud(FAOSHudPainter& P) const
{
	const FBlockLayout L = ComputeLayout(P);
	const int32 N = FMath::Max(SegmentCount, 2);
	const float Fraction = FMath::Clamp(DisplayFraction, 0.f, 1.f);
	const bool bCritical = Fraction < CriticalThreshold && !bHalted;
	const float Pulse = bCritical ? 0.5f + 0.5f * FMath::Sin(HudTime * 2.f * PI * 2.2f) : 0.f;
	// Halted systems flicker (deterministic stutter).
	const float Flicker = HaltAlpha > 0.01f ? (AOSHudMath::Hash01(uint32(HudTime * 20.f)) > 0.35f ? 1.f : 0.35f) : 1.f;
	const float Alpha = FMath::Lerp(1.f, 0.55f, HaltAlpha) * Flicker;
	const FLinearColor LevelColor = AOSDracula::Mix(GetLevelColor(Fraction), CriticalColor, HaltAlpha);

	const float Height = L.Bottom - L.Top;
	const float Pitch = Height / float(N);
	const float Thickness = FMath::Max(1.f, Pitch - StripeGap);

	// Soft falloff towards both arc faces (the stripes melt into the canopy vignette).
	auto FaceShade = [&L](const FVector2f& V)
	{
		const float Left = L.LeftX(V.Y);
		const float T = FMath::Clamp((V.X - Left) / FMath::Max(L.RightX(V.Y) - Left, 1.f), 0.f, 1.f);
		return 0.72f + 0.28f * FMath::Sin(PI * T);
	};

	// 1) Glass: every stripe slot stays visible, so the empty capacity is readable.
	FAOSHudMesh Glass;
	for (int32 i = 0; i < N; ++i)
	{
		const float Y1 = L.Bottom - float(i) * Pitch;
		AddBlockStripe(Glass, L, Y1 - Thickness, Y1, L.HoleMin, L.HoleMax,
			[&](const FVector2f& V) { return AOSDracula::WithAlpha(GlassColor, GlassColor.A * Alpha * FaceShade(V)); });
	}
	P.DrawMesh(Glass);

	// 2) Charge: horizontal stripes from the bottom up. The active stripe keeps its bottom edge and thins
	//    towards it with the charge left in its step; at 0 it is gone.
	const float Level = Fraction * float(N);
	const int32 Full = FMath::Clamp(FMath::FloorToInt(Level), 0, N);
	const float Partial = Level - float(Full);
	const int32 Active = Partial > 0.02f ? Full : Full - 1;
	const float Wave = FMath::Frac(HudTime * 0.8f) * (float(N) + 2.f) - 1.f; // dock-charge sheen, bottom -> top
	const float StripeAlpha = (1.f - 0.35f * Pulse) * Alpha;
	FAOSHudMesh Lit;
	for (int32 i = 0; i < N; ++i)
	{
		const float Fill = i < Full ? 1.f : (i == Full ? Partial : 0.f);
		if (Fill < 0.02f)
		{
			continue;
		}
		const float Y1 = L.Bottom - float(i) * Pitch;
		const float Y0 = Y1 - Thickness * Fill;
		const float Sheen = ChargeAlpha * FMath::Max(0.f, 1.f - FMath::Abs(float(i) - Wave) / 1.6f);
		const FLinearColor Base = AOSDracula::Mix(LevelColor, AOSDracula::Foreground(), (i == Active ? 0.25f : 0.f) + 0.45f * Sheen);
		AddBlockStripe(Lit, L, Y0, Y1, L.HoleMin, L.HoleMax,
			[&](const FVector2f& V) { return AOSDracula::WithAlpha(Base, StripeAlpha * FaceShade(V)); });
	}
	P.DrawMesh(Lit);

	// 3) Contour: horizontal top / bottom, arc faces left / right; "+" terminal on the top edge.
	const FLinearColor Outline = AOSDracula::Mix(OutlineColor, CriticalColor, FMath::Max(Pulse * 0.8f, HaltAlpha));
	const FLinearColor OutlineA = AOSDracula::WithAlpha(Outline, Outline.A * Alpha);
	constexpr float Pad = 2.5f;
	FBlockLayout Frame = L;
	Frame.LeftRadius += Pad;  // left face: the circle grows -> the face moves left
	Frame.RightRadius -= Pad; // right face: the circle shrinks -> the face moves right
	Frame.Top -= Pad;
	Frame.Bottom += Pad;
	const int32 FaceSegments = FMath::Clamp(FMath::CeilToInt((Frame.Bottom - Frame.Top) / 4.f), 4, 64);
	TArray<FVector2f> Contour;
	for (int32 i = 0; i <= FaceSegments; ++i) // right face, top -> bottom
	{
		const float Y = FMath::Lerp(Frame.Top, Frame.Bottom, float(i) / float(FaceSegments));
		Contour.Add(FVector2f(Frame.RightX(Y), Y));
	}
	for (int32 i = FaceSegments; i >= 0; --i) // left face, bottom -> top (the closing segment is the top edge)
	{
		const float Y = FMath::Lerp(Frame.Top, Frame.Bottom, float(i) / float(FaceSegments));
		Contour.Add(FVector2f(Frame.LeftX(Y), Y));
	}
	P.Polyline(Contour, OutlineA, 1.3f, true);

	const float TopLeftX = Frame.LeftX(Frame.Top);
	const float TopRightX = Frame.RightX(Frame.Top);
	const float CapCentre = 0.5f * (TopLeftX + TopRightX);
	const float CapHalf = 0.16f * (TopRightX - TopLeftX);
	P.FillRect(FVector2f(CapCentre - CapHalf, Frame.Top - 4.5f), FVector2f(CapCentre + CapHalf, Frame.Top - 1.f), OutlineA);

	// 4) Readout in its clean aperture (nothing else is drawn inside the rectangle).
	const FVector2f PlateMin = L.HoleMin + FVector2f(ApertureGap);
	const FVector2f PlateMax = L.HoleMax - FVector2f(ApertureGap);
	P.FillRect(PlateMin, PlateMax, AOSDracula::WithAlpha(ApertureColor, ApertureColor.A * Alpha));
	P.StrokeRect(PlateMin, PlateMax, AOSDracula::WithAlpha(Outline, 0.4f * Alpha), 1.f);
	const FLinearColor TextColor = AOSDracula::Mix(AOSDracula::Foreground(), CriticalColor, FMath::Max(Pulse, HaltAlpha));
	const FString Percent = FString::Printf(TEXT("%d%%"), FMath::RoundToInt(Fraction * 100.f));
	P.Text(Percent, BoldFont, PercentFontSize, (PlateMin + PlateMax) * 0.5f, FVector2f(0.5f, 0.5f), AOSDracula::WithAlpha(TextColor, Alpha));

	// 5) Captions: identity tag right of the top edge, balance + status under the bottom edge.
	P.Text(TEXT("SHELL-1"), Font, 7.5f, FVector2f(TopRightX + 10.f, Frame.Top + 5.f), FVector2f(0.f, 0.5f), AOSDracula::WithAlpha(LabelColor, 0.85f * Alpha));

	const float LabelX = Frame.LeftX(Frame.Bottom) + 2.f;
	const float RateY = Frame.Bottom + 18.f;
	const float StatusY = RateY + 20.f;

	FLinearColor RateColor = NeutralColor;
	if (Flow == EShellEnergyFlow::Drain)  { RateColor = DrainColor; }
	if (Flow == EShellEnergyFlow::Charge) { RateColor = ChargeColor; }
	RateColor = AOSDracula::WithAlpha(RateColor, RateColor.A * Alpha);

	const FVector2f Icon(LabelX + 6.f, RateY);
	if (Flow == EShellEnergyFlow::Drain)
	{
		const FVector2f Tri[] = { Icon + FVector2f(-6.f, -4.f), Icon + FVector2f(6.f, -4.f), Icon + FVector2f(0.f, 5.f) };
		P.FillConvex(MakeArrayView(Tri, 3), RateColor);
	}
	else if (Flow == EShellEnergyFlow::Charge)
	{
		const FVector2f Tri[] = { Icon + FVector2f(0.f, -5.f), Icon + FVector2f(6.f, 4.f), Icon + FVector2f(-6.f, 4.f) };
		P.FillConvex(MakeArrayView(Tri, 3), RateColor);
	}
	else
	{
		P.FillRect(Icon + FVector2f(-6.f, -1.f), Icon + FVector2f(6.f, 1.f), RateColor);
	}
	FString RateText;
	if (Flow == EShellEnergyFlow::Neutral)
	{
		RateText = TEXT("0.0%/s");
	}
	else
	{
		const float AbsRate = FMath::Abs(Rate);
		const TCHAR* Sign = Flow == EShellEnergyFlow::Charge ? TEXT("+") : TEXT("-");
		RateText = AbsRate < 0.095f ? FString::Printf(TEXT("%s%.2f%%/s"), Sign, AbsRate) : FString::Printf(TEXT("%s%.1f%%/s"), Sign, AbsRate);
	}
	P.Text(RateText, Font, 12.f, FVector2f(LabelX + 18.f, RateY), FVector2f(0.f, 0.5f), RateColor);

	FString Status = TEXT("NOMINAL");
	FLinearColor StatusColor = AOSDracula::Foreground();
	if (bHalted)                      { Status = TEXT("HALTED");   StatusColor = CriticalColor; }
	else if (bCharging)               { Status = TEXT("CHARGING"); StatusColor = ChargeColor; }
	else if (bCritical)               { Status = TEXT("CRITICAL"); StatusColor = CriticalColor; }
	else if (Fraction < LowThreshold) { Status = TEXT("LOW");      StatusColor = LowColor; }
	const FVector2f CoreSize = P.Text(TEXT("CORE"), Font, 8.5f, FVector2f(LabelX, StatusY), FVector2f(0.f, 0.5f), AOSDracula::WithAlpha(LabelColor, Alpha));
	P.Text(Status, BoldFont, 9.f, FVector2f(LabelX + CoreSize.X + 7.f, StatusY), FVector2f(0.f, 0.5f), AOSDracula::WithAlpha(StatusColor, Alpha));
}
