#include "PlayerSubmarineHUDWidget.h"

#include "HudBatteryGauge.h"
#include "HudCockpitFrame.h"
#include "HudCrosshair.h"
#include "HudDroneHoneycomb.h"
#include "HudGlitchOverlay.h"
#include "HudKernelPanicPanel.h"
#include "HudNavigationTape.h"
#include "HudTerminalLog.h"

#include "AOS_DK/Core/UI/AOSDraculaPalette.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "AOS_DK/Enemies/Daemon/AOS_EnemyDaemon.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "AOS_DK/Submarine/Energy/ShellEnergyComponent.h"
#include "AOS_DK/Submarine/Subdrones/Attacker/SubDrone_Attacker.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBase.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"

#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"

// ------------------------------------------------------------------------------------------ layout
void UPlayerSubmarineHUDWidget::BuildDefaultLayout(UWidgetTree* Tree, TArray<UWidget*>* OutCreated)
{
	if (!Tree)
	{
		return;
	}
	UCanvasPanel* Root = Tree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("CockpitCanvas"));
	Tree->RootWidget = Root;
	if (OutCreated)
	{
		OutCreated->Add(Root);
	}

	struct FPlacement
	{
		UClass* Class;
		const TCHAR* Name;
		FAnchors Anchors;
		FVector2D Alignment;
		FMargin Offsets; // point anchors: (PosX, PosY, SizeX, SizeY); stretch anchors: margins
		int32 ZOrder;
	};
	// Reference: 1920x1080 layout units (UMG DPI scaling keeps it proportional at any resolution).
	const FPlacement Placements[] =
	{
		{ UAOSHudCockpitFrame::StaticClass(),     TEXT("CockpitFrame"),     FAnchors(0.f, 0.f, 1.f, 1.f), FVector2D(0.0, 0.0), FMargin(0.f),                        0 },
		{ UAOSHudBatteryGauge::StaticClass(),     TEXT("BatteryGauge"),     FAnchors(0.f, 0.f, 1.f, 1.f), FVector2D(0.0, 0.0), FMargin(0.f),                        10 }, // arc follows the canopy rim
		{ UAOSHudNavigationTape::StaticClass(),   TEXT("NavigationTape"),   FAnchors(0.5f, 0.f),          FVector2D(0.5, 0.0), FMargin(0.f, 30.f, 480.f, 104.f),    10 },
		{ UAOSHudDroneHoneycomb::StaticClass(),   TEXT("DroneHoneycomb"),   FAnchors(1.f, 0.f),           FVector2D(1.0, 0.0), FMargin(-64.f, 48.f, 270.f, 180.f),  10 },
		{ UAOSHudCrosshair::StaticClass(),        TEXT("Crosshair"),        FAnchors(0.5f, 0.5f),         FVector2D(0.5, 0.5), FMargin(0.f, 0.f, 200.f, 90.f),      10 },
		{ UAOSHudTerminalLog::StaticClass(),      TEXT("TerminalLog"),      FAnchors(0.f, 1.f),           FVector2D(0.0, 1.0), FMargin(60.f, -56.f, 560.f, 210.f),  10 },
		{ UAOSHudGlitchOverlay::StaticClass(),    TEXT("GlitchOverlay"),    FAnchors(0.f, 0.f, 1.f, 1.f), FVector2D(0.0, 0.0), FMargin(0.f),                        40 },
		{ UAOSHudKernelPanicPanel::StaticClass(), TEXT("KernelPanicPanel"), FAnchors(0.5f, 0.5f),         FVector2D(0.5, 0.5), FMargin(0.f, -30.f, 1000.f, 240.f),  50 },
	};

	for (const FPlacement& Placement : Placements)
	{
		UWidget* Widget = Tree->ConstructWidget<UWidget>(Placement.Class, FName(Placement.Name));
		if (!Widget)
		{
			continue;
		}
		Widget->SetVisibility(ESlateVisibility::HitTestInvisible);
		if (UCanvasPanelSlot* CanvasSlot = Root->AddChildToCanvas(Widget))
		{
			CanvasSlot->SetAnchors(Placement.Anchors);
			CanvasSlot->SetAlignment(Placement.Alignment);
			CanvasSlot->SetOffsets(Placement.Offsets);
			CanvasSlot->SetZOrder(Placement.ZOrder);
		}
		if (OutCreated)
		{
			OutCreated->Add(Widget);
		}
	}
}

bool UPlayerSubmarineHUDWidget::Initialize()
{
	const bool bOk = Super::Initialize();
	if (bOk && WidgetTree && !WidgetTree->RootWidget)
	{
		// Native class / empty Blueprint: build the reference layout in C++.
		BuildDefaultLayout(WidgetTree);
	}
	return bOk;
}

void UPlayerSubmarineHUDWidget::NativeOnInitialized()
{
	Super::NativeOnInitialized();
	ResolveElements();
	SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UPlayerSubmarineHUDWidget::ResolveElements()
{
	if (!WidgetTree)
	{
		return;
	}
	auto Resolve = [this](auto& Member, const TCHAR* Name)
	{
		using FElementType = typename TRemovePointer<decltype(Member.Get())>::Type;
		if (!Member)
		{
			Member = Cast<FElementType>(WidgetTree->FindWidget(FName(Name)));
		}
	};
	Resolve(CockpitFrame, TEXT("CockpitFrame"));
	Resolve(BatteryGauge, TEXT("BatteryGauge"));
	Resolve(NavigationTape, TEXT("NavigationTape"));
	Resolve(Crosshair, TEXT("Crosshair"));
	Resolve(DroneHoneycomb, TEXT("DroneHoneycomb"));
	Resolve(TerminalLog, TEXT("TerminalLog"));
	Resolve(GlitchOverlay, TEXT("GlitchOverlay"));
	Resolve(KernelPanicPanel, TEXT("KernelPanicPanel"));

	// The arc battery lies along the canopy corner: it must use exactly the frame's rim geometry.
	if (BatteryGauge && CockpitFrame)
	{
		BatteryGauge->SetCanopyGeometry(CockpitFrame->GetCornerRadiusFraction(), CockpitFrame->GetEdgeInset());
	}
}

void UPlayerSubmarineHUDWidget::ForEachElement(TFunctionRef<void(UAOSHudElement&)> Fn) const
{
	UAOSHudElement* Elements[] = { CockpitFrame.Get(), BatteryGauge.Get(), NavigationTape.Get(), Crosshair.Get(), DroneHoneycomb.Get(), TerminalLog.Get(), GlitchOverlay.Get(), KernelPanicPanel.Get() };
	for (UAOSHudElement* Element : Elements)
	{
		if (Element)
		{
			Fn(*Element);
		}
	}
}

// ----------------------------------------------------------------------------------------- binding
void UPlayerSubmarineHUDWidget::BindToShell(AShellPawn* InShell)
{
	if (Shell.Get() == InShell && BoundEnergy.IsValid())
	{
		return;
	}
	UnbindFromShell();
	Shell = InShell;
	if (!InShell)
	{
		return;
	}
	if (UShellEnergyComponent* Energy = InShell->GetEnergy())
	{
		BoundEnergy = Energy;
		Energy->OnEnergyDamaged.AddDynamic(this, &UPlayerSubmarineHUDWidget::HandleEnergyDamaged);
		Energy->OnSubmarineEnergyDepleted.AddDynamic(this, &UPlayerSubmarineHUDWidget::HandleEnergyDepleted);
		Energy->OnChargingChanged.AddDynamic(this, &UPlayerSubmarineHUDWidget::HandleChargingChanged);
		Energy->OnChargeComplete.AddDynamic(this, &UPlayerSubmarineHUDWidget::HandleChargeComplete);
		Energy->OnEnergyRestored.AddDynamic(this, &UPlayerSubmarineHUDWidget::HandleEnergyRestored);
	}
	if (USubDroneBayComponent* Bay = InShell->GetDroneBay())
	{
		BoundBay = Bay;
		Bay->OnReloadRequested.AddDynamic(this, &UPlayerSubmarineHUDWidget::HandleDroneReload);
	}
	// The HUD is pooled: it was hidden mid-animation (e.g. during the Kernel Panic) and hidden widgets
	// do not tick, so wipe that state before the first frame of the new session is painted.
	ResetTransientState(*InShell);
	PushLog(TEXT("shell"), TEXT("session attached - systems online"), EAOSHudLogSeverity::System);
	if (BoundEnergy.IsValid() && BoundEnergy->IsCharging())
	{
		HandleChargingChanged(true, BoundEnergy->GetChargeRatePercent());
	}
}

void UPlayerSubmarineHUDWidget::ResetTransientState(AShellPawn& InShell)
{
	const UShellEnergyComponent* Energy = InShell.GetEnergy();
	const bool bHalted = InShell.IsSystemsHalted() || (Energy && Energy->IsDepleted());
	const float Fraction = Energy ? Energy->GetEnergyFraction() : 1.f;

	DamageGlitch = 0.f;
	PanicAlpha = bHalted ? 1.f : 0.f;
	AimTimer = 0.f;
	bAimLocked = false;
	AimDistanceMeters = 0.f;
	bWarnedLow = Fraction < LowEnergyWarning;
	bWarnedCritical = Fraction < CriticalEnergyWarning;
	SlotWasLowAmmo.Reset();
	SlotWasRingEmpty.Reset();
	SlotWasDepleted.Reset();
	SlotLastMobility.Reset();
	if (TerminalLog)
	{
		TerminalLog->ClearLog();
	}

	// Pull the live telemetry first, then snap every smoothed value / fade to it.
	TickTelemetry(InShell, GetCachedGeometry());
	TickDrones(InShell);
	ForEachElement([](UAOSHudElement& Element) { Element.ResetHud(); });

	if (KernelPanicPanel)
	{
		KernelPanicPanel->SetPanicActive(bHalted);
	}
	if (GlitchOverlay)
	{
		GlitchOverlay->SetPanic(PanicAlpha);
	}
	if (CockpitFrame)
	{
		CockpitFrame->SetPanic(PanicAlpha);
	}
}

void UPlayerSubmarineHUDWidget::UnbindFromShell()
{
	if (UShellEnergyComponent* Energy = BoundEnergy.Get())
	{
		Energy->OnEnergyDamaged.RemoveDynamic(this, &UPlayerSubmarineHUDWidget::HandleEnergyDamaged);
		Energy->OnSubmarineEnergyDepleted.RemoveDynamic(this, &UPlayerSubmarineHUDWidget::HandleEnergyDepleted);
		Energy->OnChargingChanged.RemoveDynamic(this, &UPlayerSubmarineHUDWidget::HandleChargingChanged);
		Energy->OnChargeComplete.RemoveDynamic(this, &UPlayerSubmarineHUDWidget::HandleChargeComplete);
		Energy->OnEnergyRestored.RemoveDynamic(this, &UPlayerSubmarineHUDWidget::HandleEnergyRestored);
	}
	if (USubDroneBayComponent* Bay = BoundBay.Get())
	{
		Bay->OnReloadRequested.RemoveDynamic(this, &UPlayerSubmarineHUDWidget::HandleDroneReload);
	}
	BoundEnergy.Reset();
	BoundBay.Reset();
	Shell.Reset();
	bAimLocked = false;
}

void UPlayerSubmarineHUDWidget::NativeDestruct()
{
	UnbindFromShell();
	Super::NativeDestruct();
}

AShellPawn* UPlayerSubmarineHUDWidget::GetShell() const
{
	return Shell.Get();
}

void UPlayerSubmarineHUDWidget::PushLog(const FString& Source, const FString& Message, EAOSHudLogSeverity Severity)
{
	if (TerminalLog)
	{
		TerminalLog->AddLine(Source, Message, Severity);
	}
}

void UPlayerSubmarineHUDWidget::TriggerGlitch(float Strength)
{
	DamageGlitch = FMath::Max(DamageGlitch, FMath::Clamp(Strength, 0.f, 1.f));
}

// ------------------------------------------------------------------------------------------ events
void UPlayerSubmarineHUDWidget::HandleEnergyDamaged(float EnergyLostPercent, float NewFraction, FVector HitLocation, AActor* DamageCauser)
{
	TriggerGlitch(FMath::Clamp(0.55f + EnergyLostPercent * 0.06f, 0.f, 1.f));
	const FString Amount = EnergyLostPercent >= 1.f
		? FString::Printf(TEXT("%d%%"), FMath::RoundToInt(EnergyLostPercent))
		: FString::Printf(TEXT("%.1f%%"), EnergyLostPercent);
	PushLog(TEXT("shell"), FString::Printf(TEXT("damage %s"), *Amount), EAOSHudLogSeverity::Damage);
}

void UPlayerSubmarineHUDWidget::HandleEnergyDepleted()
{
	TriggerGlitch(1.f);
	PushLog(TEXT("kernel"), TEXT("panic - core depleted, system halted"), EAOSHudLogSeverity::Fatal);
	if (KernelPanicPanel)
	{
		KernelPanicPanel->SetPanicActive(true);
	}
}

void UPlayerSubmarineHUDWidget::HandleChargingChanged(bool bCharging, float ChargeRatePercentPerSecond)
{
	if (bCharging)
	{
		PushLog(TEXT("dock"), FString::Printf(TEXT("charge cycle active +%.1f%%/s"), ChargeRatePercentPerSecond), EAOSHudLogSeverity::Charge);
	}
	else if (!BoundEnergy.IsValid() || !BoundEnergy->IsDepleted())
	{
		PushLog(TEXT("dock"), TEXT("charge cycle closed"), EAOSHudLogSeverity::Info);
	}
}

void UPlayerSubmarineHUDWidget::HandleChargeComplete()
{
	PushLog(TEXT("dock"), TEXT("core charged 100%"), EAOSHudLogSeverity::Charge);
}

void UPlayerSubmarineHUDWidget::HandleEnergyRestored(float NewFraction)
{
	if (AShellPawn* ShellPtr = Shell.Get())
	{
		ResetTransientState(*ShellPtr);
	}
	PushLog(TEXT("kernel"), FString::Printf(TEXT("reboot complete - core %d%%"), FMath::RoundToInt(NewFraction * 100.f)), EAOSHudLogSeverity::System);
}

void UPlayerSubmarineHUDWidget::HandleDroneReload(ASubDroneBase* Drone, ESubDroneReloadResult Result, float EnergyCostPercent)
{
	const ASubDrone_Attacker* Attacker = Cast<ASubDrone_Attacker>(Drone);
	const FString Source = Attacker ? TEXT("attacker") : TEXT("module");
	switch (Result)
	{
	case ESubDroneReloadResult::Accepted:
		if (Attacker && Attacker->GetRingCapacity() > 0)
		{
			// The feed has just started: report the state it will end in.
			const int32 Capacity = Attacker->GetRingCapacity();
			const int32 Moved = FMath::Min(Capacity - Attacker->GetRingAmmo(), Attacker->GetReserveAmmo());
			const int32 Left = Attacker->GetReserveAmmo() - Moved;
			PushLog(Source, FString::Printf(TEXT("reload %d/%d [%02d] -%.1f%% core"), Attacker->GetRingAmmo() + Moved, Capacity,
				FMath::DivideAndRoundUp(Left, Capacity), EnergyCostPercent), EAOSHudLogSeverity::System);
		}
		else
		{
			PushLog(Source, FString::Printf(TEXT("reload -%.1f%% core"), EnergyCostPercent), EAOSHudLogSeverity::System);
		}
		break;
	case ESubDroneReloadResult::NoPower:
		PushLog(Source, FString::Printf(TEXT("reload denied - core power low (%.1f%%)"), EnergyCostPercent), EAOSHudLogSeverity::Warning);
		break;
	case ESubDroneReloadResult::NoReserve:
		PushLog(Source, TEXT("reserve empty - rearm at dock"), EAOSHudLogSeverity::Warning);
		break;
	case ESubDroneReloadResult::Full:
		PushLog(Source, TEXT("ring full - reload skipped"), EAOSHudLogSeverity::Info);
		break;
	case ESubDroneReloadResult::Unavailable:
		PushLog(Source, TEXT("rearm in progress"), EAOSHudLogSeverity::Info);
		break;
	default:
		break; // Busy / NotSupported: silent
	}
}

// -------------------------------------------------------------------------------------------- tick
void UPlayerSubmarineHUDWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);
	const float Dt = FMath::Clamp(InDeltaTime, 0.f, 0.1f);

	bool bHalted = false;
	if (AShellPawn* ShellPtr = Shell.Get())
	{
		bHalted = ShellPtr->IsSystemsHalted();
		TickTelemetry(*ShellPtr, MyGeometry);
		TickAim(*ShellPtr, Dt);
		TickDrones(*ShellPtr);
		if (KernelPanicPanel)
		{
			KernelPanicPanel->SetRecoveryProgress(ShellPtr->GetRecoveryProgress());
		}
	}

	DamageGlitch = FMath::Max(0.f, DamageGlitch - Dt / FMath::Max(DamageGlitchDuration, 0.05f));
	PanicAlpha = AOSHudMath::Approach(PanicAlpha, bHalted ? 1.f : 0.f, bHalted ? 10.f : 4.f, Dt);
	const float Glitch = FMath::Pow(DamageGlitch, 0.7f);

	if (GlitchOverlay)
	{
		GlitchOverlay->SetIntensity(Glitch);
		GlitchOverlay->SetPanic(PanicAlpha);
	}
	if (CockpitFrame)
	{
		CockpitFrame->SetGlitch(FMath::Max(Glitch, PanicAlpha * 0.6f));
		CockpitFrame->SetPanic(PanicAlpha);
	}
	if (Crosshair)
	{
		Crosshair->SetDimmed(bHalted);
	}
	if (NavigationTape)
	{
		NavigationTape->SetDegraded(bHalted);
	}

	ForEachElement([Dt](UAOSHudElement& Element) { Element.AdvanceHud(Dt); });
}

void UPlayerSubmarineHUDWidget::TickTelemetry(AShellPawn& InShell, const FGeometry& MyGeometry)
{
	if (UShellEnergyComponent* Energy = InShell.GetEnergy())
	{
		const float Fraction = Energy->GetEnergyFraction();
		if (BatteryGauge)
		{
			BatteryGauge->SetEnergyFraction(Fraction);
			BatteryGauge->SetBalance(Energy->GetFlow(), Energy->GetNetRatePercent());
			BatteryGauge->SetStatus(Energy->IsCharging(), Energy->IsDepleted() || InShell.IsSystemsHalted());
		}
		if (!Energy->IsDepleted())
		{
			if (Fraction < CriticalEnergyWarning && !bWarnedCritical)
			{
				bWarnedCritical = bWarnedLow = true;
				PushLog(TEXT("shell"), TEXT("core critical - return to dock"), EAOSHudLogSeverity::Damage);
			}
			else if (Fraction < LowEnergyWarning && !bWarnedLow)
			{
				bWarnedLow = true;
				PushLog(TEXT("shell"), FString::Printf(TEXT("core energy low %d%%"), FMath::RoundToInt(Fraction * 100.f)), EAOSHudLogSeverity::Warning);
			}
			bWarnedLow &= Fraction < LowEnergyWarning + 0.05f;
			bWarnedCritical &= Fraction < CriticalEnergyWarning + 0.05f;
		}
	}

	if (NavigationTape)
	{
		NavigationTape->SetTelemetry(InShell.GetDepthMeters(), InShell.GetHeadingDegrees(), InShell.GetPitchDegrees());
		const float FOV = InShell.GetCameraFieldOfView();
		if (bCompassMatchesCameraFOV)
		{
			const float ScreenWidth = MyGeometry.GetAbsoluteSize().X;
			const float TapeWidth = NavigationTape->GetCachedGeometry().GetAbsoluteSize().X * (436.f / 480.f);
			if (ScreenWidth > 1.f && TapeWidth > 1.f)
			{
				NavigationTape->SetVisibleArc(FOV * TapeWidth / ScreenWidth);
			}
		}
		else
		{
			NavigationTape->SetVisibleArc(FOV * CompassArcPerFOV);
		}
	}
}

void UPlayerSubmarineHUDWidget::TickAim(AShellPawn& InShell, float Dt)
{
	AimTimer -= Dt;
	if (AimTimer <= 0.f)
	{
		AimTimer = AimTraceInterval;
		bAimLocked = false;
		AimHealth = -1.f;
		USubDroneBayComponent* Bay = InShell.GetDroneBay();
		if (Bay && !InShell.IsSystemsHalted())
		{
			FVector AimPoint;
			AActor* AimActor = nullptr;
			if (Bay->ComputeAim(AimPoint, AimActor))
			{
				const AAOS_EnemyDaemon* Daemon = Cast<AAOS_EnemyDaemon>(AimActor);
				if (Daemon && Daemon->IsAlive())
				{
					bAimLocked = true;
					AimHealth = Daemon->GetHealthFraction();
					AimDistanceMeters = FVector::Dist(InShell.GetActorLocation(), AimPoint) / 100.f;
					const FVector ToTarget = Daemon->GetActorLocation() - InShell.GetActorLocation();
					AimBearing = AOSHudMath::ClampDegrees(FMath::RadiansToDegrees(float(FMath::Atan2(ToTarget.Y, ToTarget.X))));
				}
			}
		}
	}
	// Interactable focus (the Shell's own 30 Hz query, <= InteractRange): "[F] <ACTION>" under the reticle.
	// Suppressed by a hostile lock so the two reads never mix.
	FText PromptAction;
	bool bPromptAvailable = true;
	const bool bPrompt = !bAimLocked && !InShell.IsSystemsHalted() && !InShell.AreControlsBlocked()
		&& InShell.GetFocusPrompt(PromptAction, bPromptAvailable);
	if (Crosshair)
	{
		Crosshair->SetLock(bAimLocked, AimDistanceMeters, AimHealth);
		Crosshair->SetInteractPrompt(bPrompt, PromptAction, bPromptAvailable);
	}
	if (NavigationTape)
	{
		NavigationTape->SetTargetBearing(bAimLocked, AimBearing);
	}
}

void UPlayerSubmarineHUDWidget::TickDrones(AShellPawn& InShell)
{
	if (!DroneHoneycomb)
	{
		return;
	}
	USubDroneBayComponent* Bay = InShell.GetDroneBay();
	const int32 NumSlots = Bay ? Bay->GetNumSlots() : 0;
	DroneHoneycomb->SetSlotCount(NumSlots);
	SlotWasLowAmmo.SetNumZeroed(NumSlots);
	SlotWasRingEmpty.SetNumZeroed(NumSlots);
	SlotWasDepleted.SetNumZeroed(NumSlots);
	if (SlotLastMobility.Num() != NumSlots)
	{
		SlotLastMobility.Init(0xFF, NumSlots);
	}

	for (int32 i = 0; i < NumSlots; ++i)
	{
		FAOSHudDroneSlotView View;
		const ASubDroneBase* Drone = Bay->GetDrone(i);
		if (IsValid(Drone))
		{
			const ESubDroneMobilityState Mobility = Drone->GetMobilityState();
			const bool bDocking = Mobility == ESubDroneMobilityState::Docking || Mobility == ESubDroneMobilityState::Docked;
			View.Status = bDocking ? EAOSHudDroneStatus::Service
				: (Mobility == ESubDroneMobilityState::Deployed ? EAOSHudDroneStatus::Deployed : EAOSHudDroneStatus::Formation);
			View.Tag = TEXT("MOD");

			const FString Source = TEXT("attacker");
			if (const ASubDrone_Attacker* Attacker = Cast<ASubDrone_Attacker>(Drone))
			{
				View.Tag = TEXT("ATK");
				View.bHasAmmo = true;
				View.RingAmmo = Attacker->GetRingAmmo();
				View.RingCapacity = Attacker->GetRingCapacity();
				View.ReserveAmmo = Attacker->GetReserveAmmo();
				View.ReserveCapacity = Attacker->GetReserveCapacity();
				View.bReloading = Attacker->IsReloading();
				View.Heat = Attacker->GetHeat();
				const EAttackerCombatState Combat = Attacker->GetCombatState();
				View.bPriming = Combat == EAttackerCombatState::SpinUp || Combat == EAttackerCombatState::Attack;

				// Priority: service > depleted > last magazine > firing > position.
				const bool bStationRearm = Attacker->IsBeingServiced() && !(Attacker->IsRingFull() && Attacker->IsReserveFull());
				if (bDocking || bStationRearm)
				{
					View.Status = EAOSHudDroneStatus::Service;
				}
				else if (View.IsDepleted())
				{
					View.Status = EAOSHudDroneStatus::Depleted;
				}
				else if (View.IsLowAmmo())
				{
					View.Status = EAOSHudDroneStatus::LowAmmo;
				}
				else if (View.bPriming)
				{
					View.Status = EAOSHudDroneStatus::Attack;
				}

				// Warnings only in the field: while rearming the counters legitimately pass through "low".
				const bool bInField = View.Status != EAOSHudDroneStatus::Service;
				const bool bLow = bInField && View.IsLowAmmo() && !View.IsDepleted();
				if (bLow && !SlotWasLowAmmo[i])
				{
					PushLog(Source, TEXT("low ammo - last magazine"), EAOSHudLogSeverity::Warning);
				}
				SlotWasLowAmmo[i] = bLow;
				const bool bRingEmpty = bInField && View.NeedsReload();
				if (bRingEmpty && !SlotWasRingEmpty[i])
				{
					PushLog(Source, TEXT("ring empty - RMB to reload"), EAOSHudLogSeverity::Warning);
				}
				SlotWasRingEmpty[i] = bRingEmpty;
				const bool bDepleted = bInField && View.IsDepleted();
				if (bDepleted && !SlotWasDepleted[i])
				{
					PushLog(Source, TEXT("ammo depleted - rearm at hull socket / dock"), EAOSHudLogSeverity::Damage);
				}
				SlotWasDepleted[i] = bDepleted;
			}

			const uint8 MobilityByte = uint8(Mobility);
			if (SlotLastMobility[i] != MobilityByte && SlotLastMobility[i] != 0xFF)
			{
				if (Mobility == ESubDroneMobilityState::Deployed)
				{
					PushLog(View.Tag.ToLower(), TEXT("deployed - combat position"), EAOSHudLogSeverity::System);
				}
				else if (Mobility == ESubDroneMobilityState::Docking)
				{
					PushLog(View.Tag.ToLower(), TEXT("docking for resupply"), EAOSHudLogSeverity::System);
				}
				else if (SlotLastMobility[i] == uint8(ESubDroneMobilityState::Docked))
				{
					PushLog(View.Tag.ToLower(), TEXT("rearm complete - undocked"), EAOSHudLogSeverity::Charge);
				}
			}
			SlotLastMobility[i] = MobilityByte;
		}
		DroneHoneycomb->SetSlotView(i, View);
	}
}
