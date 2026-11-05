#include "HudCrosshair.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

UAOSHudCrosshair::UAOSHudCrosshair(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	DesignSize = FVector2D(200.0, 90.0);
	IdleColor = AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.9f);
	LockColor = AOSDracula::Pink();
}

void UAOSHudCrosshair::SetLock(bool bInLocked, float InDistanceMeters)
{
	bLocked = bInLocked;
	if (bInLocked)
	{
		DistanceMeters = InDistanceMeters;
	}
}

void UAOSHudCrosshair::AdvanceHud(float DeltaSeconds)
{
	Super::AdvanceHud(DeltaSeconds);
	LockAlpha = AOSHudMath::Approach(LockAlpha, bLocked ? 1.f : 0.f, LockSpeed, DeltaSeconds);
	DimAlpha = AOSHudMath::Approach(DimAlpha, bDimmed ? 1.f : 0.f, 8.f, DeltaSeconds);
}

void UAOSHudCrosshair::ResetHud()
{
	bLocked = false;
	LockAlpha = 0.f;
	bDimmed = false;
	DimAlpha = 0.f;
}

void UAOSHudCrosshair::PaintHud(FAOSHudPainter& P) const
{
	const FVector2f C(100.f, 40.f);
	const float L = LockAlpha;
	const float Breath = L * 1.5f * FMath::Sin(HudTime * 2.f * PI * 1.4f);
	const float Gap = FMath::Lerp(IdleGap, LockedGap, L) + Breath;
	const float HalfH = FMath::Lerp(11.f, 14.f, L);
	const float Serif = FMath::Lerp(6.f, 8.f, L);
	const float Alpha = FMath::Lerp(1.f, 0.35f, DimAlpha);
	const FLinearColor Color = AOSDracula::WithAlpha(AOSDracula::Mix(IdleColor, LockColor, L), FMath::Lerp(IdleColor.A, 1.f, L) * Alpha);

	// Brackets.
	const FVector2f Left[] = { C + FVector2f(-Gap + Serif, -HalfH), C + FVector2f(-Gap, -HalfH), C + FVector2f(-Gap, HalfH), C + FVector2f(-Gap + Serif, HalfH) };
	const FVector2f Right[] = { C + FVector2f(Gap - Serif, -HalfH), C + FVector2f(Gap, -HalfH), C + FVector2f(Gap, HalfH), C + FVector2f(Gap - Serif, HalfH) };
	P.Polyline(MakeArrayView(Left), Color, 1.6f);
	P.Polyline(MakeArrayView(Right), Color, 1.6f);

	// Dot (+ faint halo when locked).
	P.FillCircle(C, FMath::Lerp(2.2f, 2.6f, L), Color, 16);
	if (L > 0.01f)
	{
		P.StrokeCircle(C, 7.f + 2.f * L, AOSDracula::WithAlpha(LockColor, 0.35f * L * Alpha), 1.f, 24);
		// Lock ticks on the bracket axis.
		P.Line(C + FVector2f(-Gap - 7.f, 0.f), C + FVector2f(-Gap - 2.f, 0.f), AOSDracula::WithAlpha(LockColor, L * Alpha), 1.2f);
		P.Line(C + FVector2f(Gap + 2.f, 0.f), C + FVector2f(Gap + 7.f, 0.f), AOSDracula::WithAlpha(LockColor, L * Alpha), 1.2f);
		const FString Range = FString::Printf(TEXT("LOCK %d M"), FMath::RoundToInt(DistanceMeters));
		P.Text(Range, Font, 8.5f, C + FVector2f(0.f, HalfH + 14.f), FVector2f(0.5f, 0.5f), AOSDracula::WithAlpha(LockColor, L * Alpha));
	}
}
