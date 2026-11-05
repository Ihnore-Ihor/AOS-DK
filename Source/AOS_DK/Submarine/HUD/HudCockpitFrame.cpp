#include "HudCockpitFrame.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

namespace
{
	struct FRimPoint
	{
		FVector2f Pos;
		FVector2f Normal;   // inward
		float Corner = 0.f; // 1 = in a corner, 0 = middle of an edge
	};

	/** Clockwise rounded-rect rim (y down), arcs + subdivided edges. */
	void BuildRim(const FVector2f& Extent, float Inset, float Radius, int32 CornerSegments, int32 EdgeSegments, TArray<FRimPoint>& Out)
	{
		Out.Reset();
		const FVector2f Centres[4] =
		{
			FVector2f(Inset + Radius, Inset + Radius),
			FVector2f(Extent.X - Inset - Radius, Inset + Radius),
			FVector2f(Extent.X - Inset - Radius, Extent.Y - Inset - Radius),
			FVector2f(Inset + Radius, Extent.Y - Inset - Radius)
		};
		const float StartAngles[4] = { 180.f, 270.f, 0.f, 90.f };
		const FVector2f EdgeNormals[4] = { FVector2f(0.f, 1.f), FVector2f(-1.f, 0.f), FVector2f(0.f, -1.f), FVector2f(1.f, 0.f) };

		for (int32 Corner = 0; Corner < 4; ++Corner)
		{
			for (int32 i = 0; i <= CornerSegments; ++i)
			{
				const float A = FMath::DegreesToRadians(StartAngles[Corner] + 90.f * float(i) / float(CornerSegments));
				const FVector2f Dir(FMath::Cos(A), FMath::Sin(A));
				FRimPoint P;
				P.Pos = Centres[Corner] + Dir * Radius;
				P.Normal = -Dir;
				P.Corner = 1.f;
				Out.Add(P);
			}
			// Edge towards the next corner (interior points only).
			const FVector2f From = Out.Last().Pos;
			const int32 Next = (Corner + 1) % 4;
			const float NextA = FMath::DegreesToRadians(StartAngles[Next]);
			const FVector2f To = Centres[Next] + FVector2f(FMath::Cos(NextA), FMath::Sin(NextA)) * Radius;
			for (int32 i = 1; i < EdgeSegments; ++i)
			{
				const float T = float(i) / float(EdgeSegments);
				FRimPoint P;
				P.Pos = FMath::Lerp(From, To, T);
				P.Normal = EdgeNormals[Corner];
				P.Corner = FMath::Square(1.f - FMath::Sin(PI * T));
				Out.Add(P);
			}
		}
	}

	/** Ray (inside the rect) to the screen border. */
	FVector2f ProjectToBorder(const FVector2f& From, const FVector2f& Dir, const FVector2f& Extent)
	{
		float T = TNumericLimits<float>::Max();
		if (Dir.X > KINDA_SMALL_NUMBER)  { T = FMath::Min(T, (Extent.X - From.X) / Dir.X); }
		if (Dir.X < -KINDA_SMALL_NUMBER) { T = FMath::Min(T, -From.X / Dir.X); }
		if (Dir.Y > KINDA_SMALL_NUMBER)  { T = FMath::Min(T, (Extent.Y - From.Y) / Dir.Y); }
		if (Dir.Y < -KINDA_SMALL_NUMBER) { T = FMath::Min(T, -From.Y / Dir.Y); }
		return T < TNumericLimits<float>::Max() ? From + Dir * T : From;
	}
}

UAOSHudCockpitFrame::UAOSHudCockpitFrame(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	DesignSize = FVector2D(1920.0, 1080.0);
	bStretchToFill = true;
	FrameColor   = AOSDracula::WithAlpha(AOSDracula::Mix(AOSDracula::Background(), FLinearColor::Black, 0.62f), 0.97f);
	RimColor     = AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.10f);
	FringeColorA = AOSDracula::WithAlpha(AOSDracula::Cyan(), 0.26f);
	FringeColorB = AOSDracula::WithAlpha(AOSDracula::Pink(), 0.20f);
}

void UAOSHudCockpitFrame::PaintHud(FAOSHudPainter& P) const
{
	const FVector2f Extent = P.Extent();
	const float Radius = FMath::Min(Extent.Y * CornerRadiusFraction, Extent.X * 0.45f);

	TArray<FRimPoint> Rim;
	BuildRim(Extent, EdgeInset, Radius, 24, 10, Rim);
	const int32 N = Rim.Num();

	const FLinearColor Frame = AOSDracula::Mix(FrameColor, AOSDracula::WithAlpha(AOSDracula::Mix(AOSDracula::Background(), AOSDracula::Red(), 0.35f), FrameColor.A), Panic * 0.6f);

	TArray<FVector2f> RimPos, Border, VignetteInner;
	TArray<FLinearColor> FrameColors, VignetteOuterColors, VignetteInnerColors;
	RimPos.Reserve(N); Border.Reserve(N); VignetteInner.Reserve(N);
	for (const FRimPoint& R : Rim)
	{
		RimPos.Add(R.Pos);
		Border.Add(ProjectToBorder(R.Pos, -R.Normal, Extent));
		const float Width = FMath::Lerp(VignetteEdgeWidth, VignetteCornerWidth, R.Corner);
		VignetteInner.Add(R.Pos + R.Normal * Width);
		FrameColors.Add(Frame);
		const float A = FMath::Lerp(VignetteEdgeAlpha, VignetteCornerAlpha, R.Corner) * Frame.A;
		VignetteOuterColors.Add(AOSDracula::WithAlpha(Frame, A));
		VignetteInnerColors.Add(AOSDracula::WithAlpha(Frame, 0.f));
	}

	// 1) Opaque canopy frame (screen border -> rim) + soft vignette (rim -> inside), one mesh.
	FAOSHudMesh Mesh;
	Mesh.AddBand(Border, RimPos, FrameColors, FrameColors, true);
	Mesh.AddBand(RimPos, VignetteInner, VignetteOuterColors, VignetteInnerColors, true);
	P.DrawMesh(Mesh);
	P.NextLayer();

	// 2) Glass rim + chromatic fringe (spreads and flickers with the damage glitch).
	const float Jitter = Glitch > 0.01f ? (AOSHudMath::Hash01(uint32(HudTime * 30.f)) - 0.5f) * 6.f * Glitch : 0.f;
	const float Spread = FringeOffset * (1.f + 5.f * Glitch) + Jitter;
	TArray<FVector2f> FringeA, FringeB;
	FringeA.Reserve(N); FringeB.Reserve(N);
	for (const FRimPoint& R : Rim)
	{
		FringeA.Add(R.Pos + R.Normal * Spread);
		FringeB.Add(R.Pos - R.Normal * Spread * 0.6f + FVector2f(Spread * 0.4f, 0.f));
	}
	const float GlitchBoost = 1.f + 1.5f * Glitch;
	const FLinearColor FringeB2 = AOSDracula::Mix(FringeColorB, AOSDracula::WithAlpha(AOSDracula::Red(), FringeColorB.A), Panic);
	P.Polyline(FringeA, AOSDracula::WithAlpha(FringeColorA, FMath::Min(1.f, FringeColorA.A * GlitchBoost)), 1.2f, true);
	P.Polyline(FringeB, AOSDracula::WithAlpha(FringeB2, FMath::Min(1.f, FringeB2.A * GlitchBoost)), 1.2f, true);
	P.Polyline(RimPos, AOSDracula::Mix(RimColor, AOSDracula::WithAlpha(AOSDracula::Red(), 0.5f), Panic), 1.f, true);

	// 3) Registration ticks at the arc ends of every corner.
	const FLinearColor TickColor = AOSDracula::WithAlpha(AOSDracula::Comment(), 0.55f);
	constexpr int32 CornerPoints = 25; // CornerSegments + 1
	constexpr int32 PerCorner = CornerPoints + 9; // + EdgeSegments - 1
	for (int32 Corner = 0; Corner < 4; ++Corner)
	{
		const int32 Mid = Corner * PerCorner + CornerPoints / 2;
		if (Rim.IsValidIndex(Mid))
		{
			const FRimPoint& R = Rim[Mid];
			P.Line(R.Pos + R.Normal * 10.f, R.Pos + R.Normal * 22.f, TickColor, 1.f);
		}
	}
}
