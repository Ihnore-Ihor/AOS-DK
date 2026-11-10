#include "HudCrosshair.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

UAOSHudCrosshair::UAOSHudCrosshair(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	DesignSize = FVector2D(200.0, 90.0);
	IdleColor = AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.9f);
	LockColor = AOSDracula::Pink();
	PromptColor = AOSDracula::Cyan();
}

void UAOSHudCrosshair::SetLock(bool bInLocked, float InDistanceMeters, float InHealthFraction)
{
	bLocked = bInLocked;
	if (bInLocked)
	{
		DistanceMeters = InDistanceMeters;
		HealthFraction = InHealthFraction;
	}
}

void UAOSHudCrosshair::SetInteractPrompt(bool bInShow, const FText& InAction, bool bInAvailable)
{
	bPrompt = bInShow;
	if (bInShow)
	{
		bPromptAvailable = bInAvailable;
		PromptText = TEXT("[F] ") + InAction.ToString().ToUpper();
	}
}

void UAOSHudCrosshair::AdvanceHud(float DeltaSeconds)
{
	Super::AdvanceHud(DeltaSeconds);
	LockAlpha = AOSHudMath::Approach(LockAlpha, bLocked ? 1.f : 0.f, LockSpeed, DeltaSeconds);
	DimAlpha = AOSHudMath::Approach(DimAlpha, bDimmed ? 1.f : 0.f, 8.f, DeltaSeconds);
	PromptAlpha = AOSHudMath::Approach(PromptAlpha, (bPrompt && !bLocked) ? 1.f : 0.f, 12.f, DeltaSeconds);
}

void UAOSHudCrosshair::ResetHud()
{
	bLocked = false;
	LockAlpha = 0.f;
	bDimmed = false;
	DimAlpha = 0.f;
	HealthFraction = -1.f;
	bPrompt = false;
	PromptAlpha = 0.f;
	PromptText.Reset();
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
	// Interactable focus tints the idle brackets Cyan (no glide: the gap stays the "not hostile" read).
	const float F = PromptAlpha * (1.f - L) * (bPromptAvailable ? 1.f : 0.f);
	const FLinearColor Idle = AOSDracula::Mix(IdleColor, PromptColor, 0.75f * F);
	const FLinearColor Color = AOSDracula::WithAlpha(AOSDracula::Mix(Idle, LockColor, L), FMath::Lerp(IdleColor.A, 1.f, FMath::Max(L, F)) * Alpha);

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
		if (HealthFraction >= 0.f)
		{
			// Target health: 56 x 3 bar under the range readout.
			const FVector2f Min = C + FVector2f(-28.f, HalfH + 22.f);
			const FVector2f Max = Min + FVector2f(56.f, 3.f);
			P.FillRect(Min, Max, AOSDracula::WithAlpha(AOSDracula::CurrentLine(), 0.8f * L * Alpha));
			P.FillRect(Min, FVector2f(FMath::Lerp(Min.X, Max.X, FMath::Clamp(HealthFraction, 0.f, 1.f)), Max.Y), AOSDracula::WithAlpha(LockColor, L * Alpha));
		}
	}

	// [F] prompt under the reticle (only without a lock - combat telemetry has priority).
	const float PA = PromptAlpha * (1.f - L) * Alpha;
	if (PA > 0.01f && !PromptText.IsEmpty())
	{
		const FLinearColor TextColor = bPromptAvailable
			? AOSDracula::WithAlpha(PromptColor, PA)
			: AOSDracula::WithAlpha(AOSDracula::Foreground(), PromptUnavailableAlpha * PA);
		P.TextOutlined(PromptText, BoldFont, PromptSize, C + FVector2f(0.f, HalfH + 18.f), FVector2f(0.5f, 0.5f), TextColor,
			AOSDracula::WithAlpha(AOSDracula::Background(), 0.85f * PA), 1.2f);
	}
}
