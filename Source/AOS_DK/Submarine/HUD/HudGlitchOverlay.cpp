#include "HudGlitchOverlay.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

UAOSHudGlitchOverlay::UAOSHudGlitchOverlay(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	DesignSize = FVector2D(1920.0, 1080.0);
	bStretchToFill = true;
	SplitColorA = AOSDracula::Cyan();
	SplitColorB = AOSDracula::Pink();
	PanicColor  = AOSDracula::Red();
}

void UAOSHudGlitchOverlay::PaintHud(FAOSHudPainter& P) const
{
	const float Panicked = Panic;
	const float I = FMath::Clamp(FMath::Max(Intensity, Panicked * 0.55f), 0.f, 1.f);
	if (I <= 0.005f && Panicked <= 0.005f)
	{
		return;
	}
	const FVector2f E = P.Extent();
	const uint32 Step = uint32(FMath::Max(0.f, HudTime) * StepsPerSecond);
	const FLinearColor ColorA = AOSDracula::Mix(SplitColorA, PanicColor, Panicked);
	const FLinearColor ColorB = AOSDracula::Mix(SplitColorB, PanicColor, Panicked);
	const FLinearColor Dark = AOSDracula::Background();

	FAOSHudMesh Mesh;

	// Kernel Panic wash + rolling bar.
	if (Panicked > 0.f)
	{
		const float Wash = (0.08f + 0.05f * FMath::Sin(HudTime * 2.f * PI * 1.3f)) * Panicked;
		Mesh.AddQuad(FVector2f::ZeroVector, E, AOSDracula::WithAlpha(PanicColor, Wash));
		const float RollY = FMath::Frac(HudTime * 0.45f) * (E.Y + 120.f) - 60.f;
		Mesh.AddQuadGradientV(FVector2f(0.f, RollY - 60.f), FVector2f(E.X, RollY), AOSDracula::WithAlpha(PanicColor, 0.f), AOSDracula::WithAlpha(PanicColor, 0.10f * Panicked));
	}

	// Torn scan bands with RGB split.
	const int32 Bands = FMath::Clamp(FMath::RoundToInt(3.f + float(MaxBands - 3) * I), 0, MaxBands);
	for (int32 b = 0; b < Bands; ++b)
	{
		const uint32 Seed = Step * 7919u + uint32(b) * 104729u;
		const float Y = AOSHudMath::Hash01(Seed) * E.Y;
		const float H = FMath::Lerp(2.f, 34.f, AOSHudMath::Hash01(Seed + 1u)) * (0.4f + 0.6f * I);
		const float X0 = AOSHudMath::Hash01(Seed + 2u) * E.X * 0.55f;
		const float W = E.X * FMath::Lerp(0.25f, 0.9f, AOSHudMath::Hash01(Seed + 3u));
		const float Shift = (AOSHudMath::Hash01(Seed + 4u) - 0.5f) * 90.f * I;
		const float A = I * FMath::Lerp(0.18f, 0.42f, AOSHudMath::Hash01(Seed + 5u));

		Mesh.AddQuad(FVector2f(X0 + Shift, Y), FVector2f(X0 + Shift + W, Y + H), AOSDracula::WithAlpha(Dark, A));
		Mesh.AddQuad(FVector2f(X0 + Shift * 1.6f, Y - 1.5f), FVector2f(X0 + Shift * 1.6f + W * 0.8f, Y + 0.5f), AOSDracula::WithAlpha(ColorA, A * 1.2f));
		Mesh.AddQuad(FVector2f(X0 - Shift, Y + H - 0.5f), FVector2f(X0 - Shift + W * 0.7f, Y + H + 1.5f), AOSDracula::WithAlpha(ColorB, A * 1.1f));
	}

	// Dead-pixel blocks.
	const int32 Blocks = FMath::RoundToInt(float(MaxBlocks) * I);
	for (int32 k = 0; k < Blocks; ++k)
	{
		const uint32 Seed = Step * 15485863u + uint32(k) * 32452843u + 17u;
		const FVector2f Pos(AOSHudMath::Hash01(Seed) * E.X, AOSHudMath::Hash01(Seed + 1u) * E.Y);
		const FVector2f Size(FMath::Lerp(6.f, 46.f, AOSHudMath::Hash01(Seed + 2u)), FMath::Lerp(3.f, 14.f, AOSHudMath::Hash01(Seed + 3u)));
		const float Pick = AOSHudMath::Hash01(Seed + 4u);
		const FLinearColor C = Pick < 0.4f ? ColorA : (Pick < 0.8f ? ColorB : AOSDracula::Foreground());
		Mesh.AddQuad(Pos, Pos + Size, AOSDracula::WithAlpha(C, 0.28f * I));
	}

	// Scanlines.
	const float ScanAlpha = 0.045f * I + 0.03f * Panicked;
	if (ScanAlpha > 0.004f)
	{
		const float Spacing = FMath::Max(ScanlineSpacing, 2.f);
		const float Offset = FMath::Frac(HudTime * 3.f) * Spacing;
		for (float Y = Offset; Y < E.Y; Y += Spacing)
		{
			Mesh.AddQuad(FVector2f(0.f, Y), FVector2f(E.X, Y + 1.f), AOSDracula::WithAlpha(Dark, ScanAlpha));
		}
	}

	P.DrawMesh(Mesh);
}
