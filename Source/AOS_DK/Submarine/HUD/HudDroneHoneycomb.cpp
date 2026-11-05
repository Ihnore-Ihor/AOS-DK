#include "HudDroneHoneycomb.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

namespace
{
	constexpr float Sqrt3 = 1.7320508f;

	/** Point on the hexagon perimeter, S in [0, 6): integer part = edge, fraction = position on it. */
	FVector2f HexPerimeterPoint(const TArray<FVector2f>& Hex, float S)
	{
		const float Wrapped = FMath::Fmod(S, 6.f);
		const int32 Edge = FMath::Clamp(FMath::FloorToInt(Wrapped), 0, 5);
		return FMath::Lerp(Hex[Edge], Hex[(Edge + 1) % 6], Wrapped - float(Edge));
	}
}

UAOSHudDroneHoneycomb::UAOSHudDroneHoneycomb(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	DesignSize = FVector2D(270.0, 180.0);
	FormationColor = AOSDracula::Purple();
	DeployedColor  = AOSDracula::Green();
	AttackColor    = AOSDracula::Pink();
	LowAmmoColor   = AOSDracula::Orange();
	DepletedColor  = AOSDracula::Red();
	ServiceColor   = AOSDracula::Cyan();
	EmptyColor     = AOSDracula::CurrentLine();
	MagazineColor  = AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.92f);
	LabelPlateColor = AOSDracula::WithAlpha(AOSDracula::Background(), 0.82f);

	// Designer preview: Attacker deployed, 20/32 in the ring, 6 of 7 reserve magazines; second core idle.
	FAOSHudDroneSlotView Attacker;
	Attacker.Status = EAOSHudDroneStatus::Deployed;
	Attacker.Tag = TEXT("ATK");
	Attacker.bHasAmmo = true;
	Attacker.RingAmmo = 20;
	Attacker.RingCapacity = 32;
	Attacker.ReserveAmmo = 192;
	Attacker.ReserveCapacity = 224;
	Views.Add(Attacker);
	Views.Add(FAOSHudDroneSlotView());
	Bars.SetNum(Views.Num());
	GetBarTargets(Views[0], Bars[0].Fill);
}

void UAOSHudDroneHoneycomb::SetSlotCount(int32 Count)
{
	Count = FMath::Clamp(Count, 0, 4);
	if (Views.Num() != Count)
	{
		Views.SetNum(Count);
		Bars.SetNum(Count);
	}
}

void UAOSHudDroneHoneycomb::GetBarTargets(const FAOSHudDroneSlotView& View, TArray<float>& OutTargets)
{
	OutTargets.Reset();
	if (!View.bHasAmmo || View.RingCapacity <= 0)
	{
		return;
	}
	const float Capacity = float(View.RingCapacity);
	OutTargets.Add(FMath::Clamp(float(View.RingAmmo) / Capacity, 0.f, 1.f));

	// Reserve, top -> bottom: full magazines first, the partly used one last (the next reload drains it).
	float Left = float(FMath::Max(View.ReserveAmmo, 0));
	for (int32 i = 0; i < View.GetReserveSlots(); ++i)
	{
		OutTargets.Add(FMath::Clamp(Left / Capacity, 0.f, 1.f));
		Left -= Capacity;
	}
}

void UAOSHudDroneHoneycomb::SetSlotView(int32 SlotIndex, const FAOSHudDroneSlotView& View)
{
	if (!Views.IsValidIndex(SlotIndex))
	{
		return;
	}
	Views[SlotIndex] = View;
	TArray<float>& Fill = Bars[SlotIndex].Fill;
	TArray<float> Targets;
	GetBarTargets(View, Targets);
	if (Fill.Num() != Targets.Num())
	{
		const int32 Old = Fill.Num();
		Fill.SetNum(Targets.Num());
		for (int32 i = Old; i < Targets.Num(); ++i)
		{
			Fill[i] = Targets[i]; // new slots appear in place
		}
	}
}

void UAOSHudDroneHoneycomb::AdvanceHud(float DeltaSeconds)
{
	Super::AdvanceHud(DeltaSeconds);
	TArray<float> Targets;
	for (int32 s = 0; s < Views.Num(); ++s)
	{
		GetBarTargets(Views[s], Targets);
		TArray<float>& Fill = Bars[s].Fill;
		for (int32 i = 0; i < Fill.Num() && i < Targets.Num(); ++i)
		{
			// A leaving torpedo thins the bar a bit faster than a loaded one thickens it.
			const float Speed = Targets[i] < Fill[i] ? BarFollowSpeed : BarFollowSpeed * 0.7f;
			Fill[i] = AOSHudMath::Approach(Fill[i], Targets[i], Speed, DeltaSeconds);
		}
	}
}

void UAOSHudDroneHoneycomb::ResetHud()
{
	for (int32 s = 0; s < Views.Num() && s < Bars.Num(); ++s)
	{
		GetBarTargets(Views[s], Bars[s].Fill);
	}
}

FVector2f UAOSHudDroneHoneycomb::GetCellCentre(int32 Index) const
{
	// Honeycomb (flat-top) packing growing from the top-right corner towards the screen centre.
	const float R = CellRadius;
	const FVector2f Anchor(270.f - R - 9.f, R * Sqrt3 * 0.5f + 12.f);
	switch (Index)
	{
	case 0:  return Anchor;
	case 1:  return Anchor + FVector2f(-1.5f * R, R * Sqrt3 * 0.5f);
	case 2:  return Anchor + FVector2f(0.f, R * Sqrt3);
	default: return Anchor + FVector2f(-1.5f * R, R * Sqrt3 * 1.5f);
	}
}

FLinearColor UAOSHudDroneHoneycomb::GetStatusColor(EAOSHudDroneStatus Status) const
{
	switch (Status)
	{
	case EAOSHudDroneStatus::Formation: return FormationColor;
	case EAOSHudDroneStatus::Deployed:  return DeployedColor;
	case EAOSHudDroneStatus::Attack:    return AttackColor;
	case EAOSHudDroneStatus::LowAmmo:   return LowAmmoColor;
	case EAOSHudDroneStatus::Depleted:  return DepletedColor;
	case EAOSHudDroneStatus::Service:   return ServiceColor;
	default:                            return EmptyColor;
	}
}

void UAOSHudDroneHoneycomb::PaintHud(FAOSHudPainter& P) const
{
	for (int32 i = 0; i < Views.Num(); ++i)
	{
		PaintCell(P, i);
	}
}

void UAOSHudDroneHoneycomb::PaintCell(FAOSHudPainter& P, int32 Index) const
{
	const FAOSHudDroneSlotView& View = Views[Index];
	const FVector2f C = GetCellCentre(Index);
	const float R = CellRadius;

	TArray<FVector2f> Hex;
	AOSHudMath::Hexagon(C, R, Hex);

	if (View.Status == EAOSHudDroneStatus::Empty)
	{
		P.FillConvex(Hex, AOSDracula::WithAlpha(AOSDracula::Background(), 0.25f));
		P.Polyline(Hex, AOSDracula::WithAlpha(EmptyColor, 0.9f), 1.2f, true);
		P.Text(FString::Printf(TEXT("CORE %d"), Index), Font, 8.f, C + FVector2f(0.f, -8.f), FVector2f(0.5f, 0.5f), AOSDracula::Comment());
		P.Text(TEXT("IDLE"), BoldFont, 8.f, C + FVector2f(0.f, 8.f), FVector2f(0.5f, 0.5f), AOSDracula::Comment());
		return;
	}

	// --- State: colour + its own motion --------------------------------------------------------
	const FLinearColor StateColor = GetStatusColor(View.Status);
	const float Pulse = 0.5f + 0.5f * FMath::Sin(HudTime * 2.f * PI * WarningPulseHz);
	float OutlineAlpha = 1.f;
	float OutlineWidth = 1.8f;
	float TintAlpha = 0.f;
	switch (View.Status)
	{
	case EAOSHudDroneStatus::Formation:
		OutlineAlpha = 0.8f;
		OutlineWidth = 1.3f;
		break;
	case EAOSHudDroneStatus::Attack:
		OutlineWidth = 2.2f;
		OutlineAlpha = 0.75f + 0.25f * AOSHudMath::Hash01(uint32(HudTime * 24.f) + uint32(Index) * 7919u);
		TintAlpha = 0.07f;
		break;
	case EAOSHudDroneStatus::LowAmmo:
		OutlineAlpha = 0.45f + 0.55f * Pulse;
		TintAlpha = 0.09f * Pulse;
		break;
	case EAOSHudDroneStatus::Depleted:
	{
		const bool bOn = FMath::Frac(HudTime * 2.5f) < 0.6f;
		OutlineAlpha = bOn ? 1.f : 0.3f;
		OutlineWidth = 2.f;
		TintAlpha = bOn ? 0.13f : 0.04f;
		break;
	}
	case EAOSHudDroneStatus::Service:
		OutlineAlpha = 0.65f;
		OutlineWidth = 1.5f;
		TintAlpha = 0.05f;
		break;
	default:
		break;
	}
	const FLinearColor Outline = AOSDracula::WithAlpha(StateColor, OutlineAlpha);

	P.FillConvex(Hex, AOSDracula::WithAlpha(AOSDracula::Background(), 0.5f));
	if (TintAlpha > 0.f)
	{
		P.FillConvex(Hex, AOSDracula::WithAlpha(StateColor, TintAlpha));
	}

	// --- Magazine bars: horizontal slices of the inset hexagon, evenly over the whole cell height -----
	// The inset hexagon has walls parallel to the border at BarPadding: every bar end is cut along the wall.
	TArray<FVector2f> InnerHex;
	const float InnerRadius = AOSHudMath::InsetHexagonRadius(R, BarPadding);
	AOSHudMath::Hexagon(C, InnerRadius, InnerHex);
	const float InnerApothem = InnerRadius * Sqrt3 * 0.5f;

	const TArray<float>& Fill = Bars[Index].Fill;
	const int32 BarCount = View.bHasAmmo ? Fill.Num() : 0;
	const float BandTop = C.Y - InnerApothem;
	const float Pitch = BarCount > 0 ? (2.f * InnerApothem) / float(BarCount) : 0.f;
	const float BarMaxT = FMath::Max(1.f, Pitch * BarFillRatio);
	auto BarY = [BandTop, Pitch](int32 K) { return BandTop + (float(K) + 0.5f) * Pitch; };

	TArray<FVector2f> Poly;
	if (BarCount > 0)
	{
		const FLinearColor Ghost = AOSDracula::WithAlpha(AOSDracula::Comment(), 0.35f);
		const FLinearColor Reserve = AOSDracula::Mix(MagazineColor, AOSDracula::WithAlpha(StateColor, MagazineColor.A), MagazineTint);
		FAOSHudMesh Mesh;

		// Active magazine (the ring), k = 0: neon halo behind its full slot.
		const float RingY = BarY(0);
		const float RingFill = FMath::Clamp(Fill[0], 0.f, 1.f);
		const float RingT = BarMaxT * RingFill;
		if (RingT > 0.15f)
		{
			const float Glow = View.Status == EAOSHudDroneStatus::Attack ? 0.75f + 0.25f * Pulse : 0.6f;
			for (int32 Layer = 2; Layer >= 1; --Layer)
			{
				TArray<FVector2f> HaloHex;
				AOSHudMath::Hexagon(C, AOSHudMath::InsetHexagonRadius(R, BarPadding - 1.4f * float(Layer)), HaloHex);
				const float Spread = 1.6f * float(Layer);
				AOSHudMath::HorizontalSlice(HaloHex, RingY - 0.5f * RingT - Spread, RingY + 0.5f * RingT + Spread, Poly);
				Mesh.AddConvex(Poly, AOSDracula::WithAlpha(StateColor, (Layer == 2 ? 0.12f : 0.26f) * Glow));
			}
		}

		for (int32 k = 0; k < BarCount; ++k)
		{
			const float Y = BarY(k);
			const float T = BarMaxT * FMath::Clamp(Fill[k], 0.f, 1.f);
			if (T > 0.15f)
			{
				FLinearColor Color = Reserve;
				if (k == 0)
				{
					// Accent: clearly the state colour, heats towards orange / red with the generator.
					Color = AOSDracula::Mix(AOSDracula::WithAlpha(StateColor, 1.f), AOSDracula::Foreground(), 0.35f);
					const float HeatT = FMath::Clamp((View.Heat - 0.3f) / 0.7f, 0.f, 1.f);
					Color = AOSDracula::Mix(Color, AOSDracula::Mix(AOSDracula::Orange(), AOSDracula::Red(), View.Heat), 0.6f * HeatT);
				}
				AOSHudMath::HorizontalSlice(InnerHex, Y - 0.5f * T, Y + 0.5f * T, Poly);
				Mesh.AddConvex(Poly, Color);
			}
			else if (k > 0)
			{
				// Spent reserve magazine: a hairline slot, still cut along the walls.
				AOSHudMath::HorizontalSlice(InnerHex, Y - 0.6f, Y + 0.6f, Poly);
				Mesh.AddConvex(Poly, Ghost);
			}
		}

		// Firing spark / magnetic-feed sheen running along the ring bar (kept inside its trapezoid).
		if ((View.bPriming || View.bReloading) && RingT > 0.15f)
		{
			float MinX, MaxX, MinX2, MaxX2;
			if (AOSHudMath::ConvexSpanAtY(InnerHex, RingY - 0.5f * RingT, MinX, MaxX) && AOSHudMath::ConvexSpanAtY(InnerHex, RingY + 0.5f * RingT, MinX2, MaxX2))
			{
				const float Left = FMath::Max(MinX, MinX2) + 1.f;
				const float Right = FMath::Min(MaxX, MaxX2) - 1.f;
				const float Speed = View.bReloading ? 1.6f : 3.2f;
				const float X = FMath::Lerp(Left, FMath::Max(Left, Right - 9.f), FMath::Frac(HudTime * Speed));
				const FLinearColor Spark = View.bReloading ? ServiceColor : AOSDracula::Foreground();
				Mesh.AddQuad(FVector2f(X, RingY - 0.5f * RingT), FVector2f(X + 9.f, RingY + 0.5f * RingT), Spark);
			}
		}
		P.DrawMesh(Mesh);

		// Activity frame around the FULL ring slot: shows which magazine is being spent, and stays when it is dry.
		AOSHudMath::HorizontalSlice(InnerHex, RingY - 0.5f * BarMaxT - 1.2f, RingY + 0.5f * BarMaxT + 1.2f, Poly);
		const FLinearColor FrameColor = View.NeedsReload()
			? AOSDracula::WithAlpha(LowAmmoColor, 0.55f + 0.45f * Pulse)
			: AOSDracula::WithAlpha(AOSDracula::Mix(StateColor, AOSDracula::Foreground(), 0.2f), 0.95f);
		P.Polyline(Poly, FrameColor, 1.f, true);
	}

	// --- Cell border (+ service scanner) ------------------------------------------------------
	P.Polyline(Hex, Outline, OutlineWidth, true);
	if (View.Status == EAOSHudDroneStatus::Service)
	{
		TArray<FVector2f> Scan;
		const float Start = FMath::Frac(HudTime * 0.6f) * 6.f;
		for (int32 k = 0; k <= 12; ++k)
		{
			Scan.Add(HexPerimeterPoint(Hex, Start + 1.1f * float(k) / 12.f));
		}
		P.Polyline(Scan, AOSDracula::Mix(ServiceColor, AOSDracula::Foreground(), 0.35f), 2.6f);
	}

	// --- Label block on a compact dark pill (bars stay visible around it) -----------------------
	constexpr float HeaderPt = 9.f;
	constexpr float RingPt = 14.f;
	constexpr float ReservePt = 9.f;
	constexpr float LineGap = 1.5f;
	const float HeaderH = 1.32f * HeaderPt;
	const float RingH = 1.32f * RingPt;
	const float ReserveH = 1.32f * ReservePt;
	const bool bAmmoLines = View.bHasAmmo;
	const float BlockH = bAmmoLines ? HeaderH + LineGap + RingH + LineGap + ReserveH : HeaderH;
	// Fixed width (widest possible strings) -> the pill never jitters while the counters change.
	const float HeaderW = P.MeasureText(View.Tag, BoldFont, HeaderPt).X + 12.f;
	float BlockW = HeaderW;
	if (bAmmoLines)
	{
		const float RingW = P.MeasureText(FString::Printf(TEXT("%d/%d"), View.RingCapacity, View.RingCapacity), BoldFont, RingPt).X;
		const float ReserveW = P.MeasureText(TEXT("[00]"), BoldFont, ReservePt).X + 5.f + P.MeasureText(TEXT("LOAD"), BoldFont, 7.f).X;
		BlockW = FMath::Max3(HeaderW, RingW, ReserveW);
	}
	const FVector2f PillHalf(0.5f * BlockW + 6.f, 0.5f * BlockH + 3.f);
	const FVector2f PillCentre(C.X, C.Y + (bAmmoLines ? 1.f : 0.f));
	TArray<FVector2f> Pill;
	AOSHudMath::RoundedRect(PillCentre - PillHalf, PillCentre + PillHalf, 5.f, 3, Pill);
	P.FillConvex(Pill, LabelPlateColor);
	P.Polyline(Pill, AOSDracula::WithAlpha(StateColor, 0.35f), 1.f, true);

	float LineY = PillCentre.Y - 0.5f * BlockH;
	const float HeaderY = LineY + 0.5f * HeaderH;
	const float HeaderLeft = C.X - 0.5f * HeaderW;
	const FVector2f TagSize = P.Text(View.Tag, BoldFont, HeaderPt, FVector2f(HeaderLeft, HeaderY), FVector2f(0.f, 0.5f),
		AOSDracula::Mix(StateColor, AOSDracula::Foreground(), 0.2f));
	const float LedAlpha = (View.Status == EAOSHudDroneStatus::Attack || View.Status == EAOSHudDroneStatus::Depleted) ? OutlineAlpha : 1.f;
	P.FillCircle(FVector2f(HeaderLeft + TagSize.X + 7.f, HeaderY), 3.f, AOSDracula::WithAlpha(StateColor, LedAlpha), 12);

	if (!bAmmoLines)
	{
		return;
	}
	LineY += HeaderH + LineGap;
	const float RingTextY = LineY + 0.5f * RingH;
	LineY += RingH + LineGap;
	const float ReserveTextY = LineY + 0.5f * ReserveH;

	FLinearColor RingText = AOSDracula::Foreground();
	if (View.IsDepleted())
	{
		RingText = DepletedColor;
	}
	else if (View.NeedsReload())
	{
		RingText = AOSDracula::Mix(LowAmmoColor, DepletedColor, 0.3f * Pulse);
	}
	P.Text(FString::Printf(TEXT("%d/%d"), View.RingAmmo, View.RingCapacity), BoldFont, RingPt, FVector2f(C.X, RingTextY), FVector2f(0.5f, 0.5f), RingText);

	FLinearColor ReserveText = AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.85f);
	if (View.IsDepleted())
	{
		ReserveText = DepletedColor;
	}
	else if (View.IsLowAmmo())
	{
		ReserveText = AOSDracula::Mix(LowAmmoColor, DepletedColor, 0.3f * Pulse);
	}
	const FString ReserveStr = FString::Printf(TEXT("[%02d]"), View.GetReserveMagazines());
	const bool bHint = View.bReloading || View.NeedsReload();
	const float ReserveStrW = P.MeasureText(ReserveStr, BoldFont, ReservePt).X;
	const float HintW = bHint ? 5.f + P.MeasureText(View.bReloading ? TEXT("LOAD") : TEXT("RMB"), BoldFont, 7.f).X : 0.f;
	const float ReserveLeft = C.X - 0.5f * (ReserveStrW + HintW);
	P.Text(ReserveStr, BoldFont, ReservePt, FVector2f(ReserveLeft, ReserveTextY), FVector2f(0.f, 0.5f), ReserveText);

	// Action hint: RMB when the ring is dry, LOAD while the feed runs.
	if (View.bReloading)
	{
		P.Text(TEXT("LOAD"), BoldFont, 7.f, FVector2f(ReserveLeft + ReserveStrW + 5.f, ReserveTextY), FVector2f(0.f, 0.5f), ServiceColor);
	}
	else if (View.NeedsReload())
	{
		P.Text(TEXT("RMB"), BoldFont, 7.f, FVector2f(ReserveLeft + ReserveStrW + 5.f, ReserveTextY), FVector2f(0.f, 0.5f),
			AOSDracula::WithAlpha(LowAmmoColor, 0.6f + 0.4f * Pulse));
	}
}
