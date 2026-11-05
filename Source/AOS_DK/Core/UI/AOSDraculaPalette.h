#pragma once

#include "CoreMinimal.h"

/**
 * Dracula Theme palette (draculatheme.com) - the single colour source of the AOS_DK UI.
 * Authored as sRGB hex, returned as linear colours (what Slate / UMG / materials expect).
 *
 * HUD role mapping (chosen for legibility against blue-green underwater fog):
 *  Yellow  - core energy fill (highest luminance contrast vs. water)
 *  Green   - energy recovery / dock charge, healthy enemy
 *  Orange  - system load (drain), warnings, low ammo
 *  Red     - damage, critical, kernel panic
 *  Pink    - target lock, telegraphed enemy attack
 *  Purple  - Attacker drone module (accent of its honeycomb cell)
 *  Cyan    - navigation (compass, cardinal marks), terminal sources, glass fringe
 *  Foreground / Comment / CurrentLine / Background - text, muted labels, idle frames, plates
 */
namespace AOSDracula
{
	inline FLinearColor FromHex(uint8 R, uint8 G, uint8 B, float Alpha = 1.f)
	{
		FLinearColor Color = FLinearColor::FromSRGBColor(FColor(R, G, B, 255));
		Color.A = Alpha;
		return Color;
	}

	inline FLinearColor Background()  { return FromHex(0x28, 0x2A, 0x36); }
	inline FLinearColor CurrentLine() { return FromHex(0x44, 0x47, 0x5A); }
	inline FLinearColor Foreground()  { return FromHex(0xF8, 0xF8, 0xF2); }
	inline FLinearColor Comment()     { return FromHex(0x62, 0x72, 0xA4); }
	inline FLinearColor Cyan()        { return FromHex(0x8B, 0xE9, 0xFD); }
	inline FLinearColor Green()       { return FromHex(0x50, 0xFA, 0x7B); }
	inline FLinearColor Orange()      { return FromHex(0xFF, 0xB8, 0x6C); }
	inline FLinearColor Pink()        { return FromHex(0xFF, 0x79, 0xC6); }
	inline FLinearColor Purple()      { return FromHex(0xBD, 0x93, 0xF9); }
	inline FLinearColor Red()         { return FromHex(0xFF, 0x55, 0x55); }
	inline FLinearColor Yellow()      { return FromHex(0xF1, 0xFA, 0x8C); }

	inline FLinearColor WithAlpha(FLinearColor Color, float Alpha)
	{
		Color.A = Alpha;
		return Color;
	}

	/** Linear blend that also blends alpha. */
	inline FLinearColor Mix(const FLinearColor& A, const FLinearColor& B, float T)
	{
		return A + (B - A) * FMath::Clamp(T, 0.f, 1.f);
	}
}
