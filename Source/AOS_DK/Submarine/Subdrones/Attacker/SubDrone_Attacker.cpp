#include "AOS_DK/Submarine/Subdrones/Attacker/SubDrone_Attacker.h"

#include "AOS_DK/Submarine/Subdrones/Attacker/MicroTorpedo.h"
#include "AOS_DK/Submarine/Subdrones/Attacker/TorpedoReloadPolicy.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneMath.h"
#include "AOS_DK/Enemies/Reaper/AOS_CombatThreatSubsystem.h"
#include "Perception/AISense_Hearing.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraComponent.h"

using namespace SubDroneMath;

namespace AttackerFx
{
	static const FName VortexRate(TEXT("VortexRate"));
	static const FName BubbleRate(TEXT("BubbleRate"));

	/** Small moving visuals: no shadows, no distance fields, no decals, no collision. */
	static void MakeCheapVisual(UPrimitiveComponent* Comp)
	{
		Comp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Comp->SetGenerateOverlapEvents(false);
		Comp->SetCanEverAffectNavigation(false);
		Comp->SetCastShadow(false);
		Comp->bAffectDistanceFieldLighting = false;
		Comp->SetReceivesDecals(false);
	}

	static float EaseInOutCubic(float X)
	{
		X = FMath::Clamp(X, 0.f, 1.f);
		return X < 0.5f ? 4.f * X * X * X : 1.f - FMath::Pow(-2.f * X + 2.f, 3.f) * 0.5f;
	}

	/** Standard ease-out-back: overshoots 1 slightly, settles at exactly 1 for X = 1. */
	static float EaseOutBack(float X, float C1)
	{
		X = FMath::Clamp(X, 0.f, 1.f);
		const float C3 = C1 + 1.f;
		const float Y = X - 1.f;
		return 1.f + C3 * Y * Y * Y + C1 * Y * Y;
	}

	constexpr float BreechSnapTime = 0.12f;      // s: breech slams shut at the start of Raise
	constexpr float BreechSnapOvershoot = 2.3f;  // EaseOutBack C1 -> ~1.5 cm over a 11 cm travel
	constexpr float GlowFlashTime = 0.15f;       // s: glow flash at the start of Raise
	constexpr float BubbleBurstDuration = 0.25f; // s
	constexpr float BubbleBurstMul = 4.f;
	constexpr float FlightStartAxial = -30.f;    // cm: breech point (ring-local X)
	constexpr float FlightStartRadius01 = 0.15f; // fraction of RingRadius
	constexpr float FlightStartScale = 0.35f;
	constexpr float RingAlignHalfLife = 0.07f;   // s: de-rotation of the ring to slot 0 @ 12 o'clock
	constexpr double RingSlot0TopDeg = 90.0;     // ring rotates about +X: +Y -> +Z at 90 deg

	/** Push a Niagara float only when it changed noticeably (relative 2 %). */
	static void SetFxFloat(UNiagaraComponent* Fx, FName Name, float Value, float& LastValue)
	{
		if (FMath::Abs(Value - LastValue) > FMath::Max(0.5f, FMath::Abs(LastValue) * 0.02f))
		{
			Fx->SetVariableFloat(Name, Value);
			LastValue = Value;
		}
	}
}

ASubDrone_Attacker::ASubDrone_Attacker()
{
	CollisionSphere->InitSphereRadius(45.f); // drone is 124 cm long, rotation-invariant sweep body

	auto MakeVisualMesh = [this](const TCHAR* Name, USceneComponent* Parent)
	{
		UStaticMeshComponent* Comp = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Comp->SetupAttachment(Parent);
		AttackerFx::MakeCheapVisual(Comp);
		return Comp;
	};
	HullFront = MakeVisualMesh(TEXT("HullFront"), VisualRoot);
	HullRear  = MakeVisualMesh(TEXT("HullRear"), VisualRoot);
	CoreMesh  = MakeVisualMesh(TEXT("CoreMesh"), VisualRoot);

	RingPivot = CreateDefaultSubobject<USceneComponent>(TEXT("RingPivot"));
	RingPivot->SetupAttachment(VisualRoot);

	TorpedoRing = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("TorpedoRing"));
	TorpedoRing->SetupAttachment(RingPivot);
	AttackerFx::MakeCheapVisual(TorpedoRing);
	TorpedoRing->NumCustomDataFloats = 0;

	// Under the ring pivot: the local-space vapour ring co-rotates with the magnetic ring (vortex swirl).
	CavityFX = CreateDefaultSubobject<UNiagaraComponent>(TEXT("CavityFX"));
	CavityFX->SetupAttachment(RingPivot);
	CavityFX->SetAutoActivate(false);
	CavityFX->SetCastShadow(false);

	HullBubblesFX = CreateDefaultSubobject<UNiagaraComponent>(TEXT("HullBubblesFX"));
	HullBubblesFX->SetupAttachment(VisualRoot);
	HullBubblesFX->SetAutoActivate(false);
	HullBubblesFX->SetCastShadow(false);

	ReserveSupplyPolicy = CreateDefaultSubobject<UTorpedoReloadPolicy_DockResupply>(TEXT("ReserveSupplyPolicy"));
	TorpedoClass = AMicroTorpedo::StaticClass();
}

// ------------------------------------------------------------------------------- lifecycle
void ASubDrone_Attacker::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	BuildRing(); // procedural ring is visible in the BP viewport too
}

void ASubDrone_Attacker::BeginPlay()
{
	Super::BeginPlay();

	VisualRootBase = VisualRoot->GetRelativeTransform();
	HullRearBase = HullRear->GetRelativeTransform();

	if (SlotLoaded.Num() != RingSlotCount)
	{
		BuildRing();
	}
	InternalReserveAmmo = bStartWithFullAmmo ? GetReserveCapacity() : 0;

	// The first few right away; the rest + the effect warm-up are sliced over later frames (TickPoolWarmup).
	for (int32 Index = 0; Index < FMath::Min(PoolPrewarmCount, PoolImmediateCount); ++Index)
	{
		SpawnPooledTorpedo();
	}
	if (HullBubblesFX->GetAsset())
	{
		HullBubblesFX->Activate(true);
	}
	bAmmoDirty = true;
}

void ASubDrone_Attacker::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	for (AMicroTorpedo* Torpedo : TorpedoPool)
	{
		if (IsValid(Torpedo))
		{
			Torpedo->Destroy();
		}
	}
	TorpedoPool.Reset();
	Super::EndPlay(EndPlayReason);
}

// ------------------------------------------------------------------------------- ring
FVector ASubDrone_Attacker::GetSlotLocalPosition(int32 Slot) const
{
	const double Angle = 2.0 * PI * Slot / FMath::Max(RingSlotCount, 1);
	return FVector(RingAxialOffset, RingRadius * FMath::Cos(Angle), RingRadius * FMath::Sin(Angle));
}

FTransform ASubDrone_Attacker::MakeSlotTransform(int32 Slot, bool bLoaded) const
{
	// Torpedoes lie parallel to the drone axis (nose +X); an empty slot is collapsed.
	return FTransform(FQuat::Identity, GetSlotLocalPosition(Slot), FVector(bLoaded ? 1.f : 0.001f));
}

void ASubDrone_Attacker::BuildRing()
{
	const uint8 Initial = bStartWithFullAmmo ? 1 : 0;
	SlotLoaded.Init(Initial, RingSlotCount);
	CurrentRingAmmo = Initial ? RingSlotCount : 0;
	DirtySlots.Reset();

	if (!TorpedoRing)
	{
		return;
	}
	TArray<FTransform> Transforms;
	Transforms.Reserve(RingSlotCount);
	for (int32 Slot = 0; Slot < RingSlotCount; ++Slot)
	{
		Transforms.Add(MakeSlotTransform(Slot, Initial != 0));
	}
	TorpedoRing->ClearInstances();
	TorpedoRing->AddInstances(Transforms, /*bShouldReturnIndices*/ false, /*bWorldSpace*/ false);
}

void ASubDrone_Attacker::SetSlotLoaded(int32 Slot, bool bLoaded, bool bAnimated)
{
	if (SlotLoaded[Slot] == static_cast<uint8>(bLoaded))
	{
		return;
	}
	SlotLoaded[Slot] = bLoaded ? 1 : 0;
	CurrentRingAmmo += bLoaded ? 1 : -1;
	bAmmoDirty = true;

	if (bLoaded && bAnimated)
	{
		// Manual feed: the torpedo flies breech -> slot (TickReloadAnim); the slot is NOT queued for the instant flush.
		FRoundFlight& Flight = RoundFlights.AddDefaulted_GetRef();
		Flight.Slot = Slot;
		Flight.T = 0.f;
		const FVector Slot0 = GetSlotLocalPosition(Slot);
		const FVector Radial = FVector(0.f, Slot0.Y, Slot0.Z).GetSafeNormal() * (RingRadius * AttackerFx::FlightStartRadius01);
		TorpedoRing->UpdateInstanceTransform(Slot,
			FTransform(FQuat::Identity, FVector(AttackerFx::FlightStartAxial, Radial.Y, Radial.Z), FVector(AttackerFx::FlightStartScale)),
			false, false, true);
		return;
	}
	DirtySlots.AddUnique(Slot);
}

void ASubDrone_Attacker::FlushRingUpdates()
{
	// Incremental GPU-scene instance updates (no MarkRenderStateDirty -> no proxy rebuild).
	for (const int32 Slot : DirtySlots)
	{
		TorpedoRing->UpdateInstanceTransform(Slot, MakeSlotTransform(Slot, SlotLoaded[Slot] != 0), false, false, true);
	}
	DirtySlots.Reset();
}

int32 ASubDrone_Attacker::AddToReserve(int32 Count)
{
	const int32 Accepted = FMath::Clamp(Count, 0, GetReserveCapacity() - InternalReserveAmmo);
	if (Accepted > 0)
	{
		InternalReserveAmmo += Accepted;
		bAmmoDirty = true;
	}
	return Accepted;
}

float ASubDrone_Attacker::GetTimeSinceLastShot() const
{
	const UWorld* World = GetWorld();
	return World ? static_cast<float>(World->GetTimeSeconds() - LastShotTime) : 1000.f;
}

// ------------------------------------------------------------------------------- input
void ASubDrone_Attacker::StartPrimaryAction()
{
	// Defence in depth: the bay already filters, but the drone itself never latches the trigger
	// outside its combat position (Formation / Docking / Docked ignore LMB completely).
	if (!AcceptsPrimaryAction())
	{
		return;
	}
	bTriggerHeld = true;
}

void ASubDrone_Attacker::StopPrimaryAction()
{
	bTriggerHeld = false;
}

// ------------------------------------------------------------------------------- tick
void ASubDrone_Attacker::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (DeltaSeconds <= 0.f || !GetBay())
	{
		return;
	}

	TickPoolWarmup(DeltaSeconds);

	// Aim only when it matters: armed (nose tracks the crosshair) or trigger held.
	if (GetDeployBlend() > 0.01f || bTriggerHeld)
	{
		UpdateAim();
	}
	else
	{
		bHasAimPoint = false;
	}

	TickCombat(DeltaSeconds);
	TickReloadAnim(DeltaSeconds);
	TickSpin(DeltaSeconds);
	TickAmmo(DeltaSeconds);
	FlushRingUpdates();
	TickVisuals(DeltaSeconds);

	if (bAmmoDirty)
	{
		bAmmoDirty = false;
		OnAmmoChanged.Broadcast(CurrentRingAmmo, RingSlotCount, InternalReserveAmmo, GetReserveCapacity());
	}
}

void ASubDrone_Attacker::UpdateAim()
{
	AActor* HitActor = nullptr;
	FVector Point;
	GetBay()->ComputeAim(Point, HitActor);
	AimPoint = Point;
	AimActor = HitActor;
	bHasAimPoint = true;
}

bool ASubDrone_Attacker::CanEngage() const
{
	return GetMobilityState() == ESubDroneMobilityState::Deployed && GetDeployBlend() >= EngageDeployBlend;
}

void ASubDrone_Attacker::SetCombatState(EAttackerCombatState NewState)
{
	if (NewState == CombatState)
	{
		return;
	}
	const EAttackerCombatState OldState = CombatState;
	CombatState = NewState;
	CombatStateTime = 0.f;
	BP_OnCombatStateChanged(NewState, OldState);
	OnCombatStateChanged.Broadcast(NewState, OldState);
}

void ASubDrone_Attacker::TickCombat(float Dt)
{
	CombatStateTime += Dt;

	Heat = FMath::Max(0.f, Heat - HeatDissipationPerSec * Dt);
	if (bOverheated && Heat <= OverheatResumeHeat)
	{
		bOverheated = false;
	}

	const bool bWantFire = bTriggerHeld && CanEngage() && !bOverheated && !bReloading && CurrentRingAmmo > 0;

	switch (CombatState)
	{
	case EAttackerCombatState::Idle:
		if (bWantFire)
		{
			SetCombatState(EAttackerCombatState::SpinUp);
		}
		break;

	case EAttackerCombatState::SpinUp:
		if (!bWantFire)
		{
			SetCombatState(EAttackerCombatState::Cooling);
		}
		else if (SpinAlpha >= FireSpinThreshold)
		{
			FireAccumulator = FireInterval; // first shot on the threshold frame
			SetCombatState(EAttackerCombatState::Attack);
		}
		break;

	case EAttackerCombatState::Attack:
	{
		if (!bWantFire)
		{
			SetCombatState(EAttackerCombatState::Cooling);
			break;
		}
		FireAccumulator += Dt;
		int32 Shots = 0;
		while (FireAccumulator >= FireInterval && Shots < 3 && CurrentRingAmmo > 0 && !bOverheated)
		{
			FireAccumulator -= FireInterval;
			FireOnce();
			++Shots;
		}
		FireAccumulator = FMath::Min(FireAccumulator, FireInterval);
		break;
	}

	case EAttackerCombatState::Cooling:
		if (CombatStateTime >= CoolingMinDuration)
		{
			if (bWantFire)
			{
				SetCombatState(EAttackerCombatState::SpinUp);
			}
			else
			{
				SetCombatState(EAttackerCombatState::Idle);
			}
		}
		break;
	}
}

float ASubDrone_Attacker::GetCombatSpinNormalized() const
{
	// 0 at armed idle, 1 at full combat spin.
	return FMath::Clamp((SpinAlpha - ArmedSpinAlpha) / FMath::Max(1.f - ArmedSpinAlpha, KINDA_SMALL_NUMBER), 0.f, 1.f);
}

void ASubDrone_Attacker::TickSpin(float Dt)
{
	// Lower / Feed: hulls brake to a stop and the ring parks with slot 0 at 12 o'clock.
	const bool bReloadHold = ReloadPhase == EAttackerReloadPhase::Lower || ReloadPhase == EAttackerReloadPhase::Feed;

	float Target = FMath::Lerp(FormationSpinAlpha, ArmedSpinAlpha, GetDeployBlend());
	if (GetMobilityState() == ESubDroneMobilityState::Docked)
	{
		Target = 0.f;
	}
	else if (CombatState == EAttackerCombatState::SpinUp || CombatState == EAttackerCombatState::Attack)
	{
		Target = 1.f;
	}
	if (bReloadHold)
	{
		Target = 0.f;
	}

	const float Tau = bReloadHold ? ReloadSpinTau : (Target > SpinAlpha ? SpinUpTimeConstant : SpinDownTimeConstant);
	SpinAlpha = MotorStep(SpinAlpha, Target, Tau, Dt);
	if (SpinAlpha < 1e-4f && Target <= 0.f && !bReloadHold)
	{
		SpinAlpha = 0.f;
		RingSpinDegPerSec = 0.f;
		return; // parked: no transform updates
	}

	const double OmegaFront = static_cast<double>(SpinAlpha) * MaxSpinDegPerSec;
	RingSpinDegPerSec = SpinAlpha * RingMaxSpinDegPerSec;

	FrontAngleDeg = WrapDegrees(FrontAngleDeg + OmegaFront * Dt);
	RearAngleDeg = WrapDegrees(RearAngleDeg + OmegaFront * RearSpinRatio * Dt);
	if (bReloadHold)
	{
		RingSpinDegPerSec = 0.f;
		RingAngleDeg = WrapDegrees(RingAngleDeg + FMath::FindDeltaAngleDegrees(RingAngleDeg, AttackerFx::RingSlot0TopDeg) *
			static_cast<double>(HalfLifeAlpha(AttackerFx::RingAlignHalfLife, Dt)));
	}
	else
	{
		RingAngleDeg = WrapDegrees(RingAngleDeg + static_cast<double>(RingSpinDegPerSec) * Dt);
	}

	HullFront->SetRelativeRotation(FQuat(FVector::XAxisVector, FMath::DegreesToRadians(FrontAngleDeg)));
	HullRear->SetRelativeRotation(FQuat(FVector::XAxisVector, FMath::DegreesToRadians(RearAngleDeg)));
	RingPivot->SetRelativeRotation(FQuat(FVector::XAxisVector, FMath::DegreesToRadians(RingAngleDeg)));
}

void ASubDrone_Attacker::TickAmmo(float Dt)
{
	const ESubDroneMobilityState Mobility = GetMobilityState();
	const bool bDocked = Mobility == ESubDroneMobilityState::Docked;

	const bool bServiced = IsBeingServiced();

	// Tier 3 -> 2: physical resupply from the Shell only (hull socket / dock). Nothing regenerates.
	if (ReserveSupplyPolicy)
	{
		const int32 Granted = ReserveSupplyPolicy->TickReserveResupply(*this, Dt);
		if (Granted > 0)
		{
			AddToReserve(Granted);
		}
	}

	// Tier 2 -> 1: the ring is fed from the reserve only by a manual reload (RMB) or while serviced.
	// Manual reload feeds only in the Feed phase (Lower opens the breech first, Raise closes it). Dock refill is instant-ish, no fly-in.
	const bool bManualFeed = bReloading && ReloadPhase == EAttackerReloadPhase::Feed && !bServiced;
	const bool bFeeding = (bManualFeed || bServiced) && !IsRingFull() && InternalReserveAmmo > 0;
	if (bFeeding)
	{
		const float Interval = bServiced ? DockedRingRefillInterval : ReloadRoundInterval;
		RingRefillAccumulator += Dt;
		for (int32 Slot = 0; Slot < SlotLoaded.Num() && RingRefillAccumulator >= Interval && InternalReserveAmmo > 0; ++Slot)
		{
			if (!SlotLoaded[Slot])
			{
				SetSlotLoaded(Slot, true, bManualFeed);
				--InternalReserveAmmo;
				RingRefillAccumulator -= Interval;
			}
		}
		RingRefillAccumulator = FMath::Min(RingRefillAccumulator, Interval);
	}
	else
	{
		RingRefillAccumulator = 0.f;
	}
	if (bReloading && (IsRingFull() || InternalReserveAmmo <= 0))
	{
		EndFeed();
	}

	// Resupply request: reserve exhausted and the policy needs the Shell.
	const bool bNeedResupply = ReserveSupplyPolicy && ReserveSupplyPolicy->RequiresDocking() && InternalReserveAmmo == 0 && !bServiced;
	if (bNeedResupply != bResupplyRequested)
	{
		bResupplyRequested = bNeedResupply;
		BP_OnResupplyRequestChanged(bResupplyRequested);
		OnResupplyRequestChanged.Broadcast(bResupplyRequested);
	}

	// Completely dry -> dock automatically; full (or timed out) -> back to work.
	if (bAutoDockWhenEmpty && bResupplyRequested && CurrentRingAmmo == 0 && !IsFiring() &&
		(Mobility == ESubDroneMobilityState::Formation || Mobility == ESubDroneMobilityState::Deployed))
	{
		RequestDock();
	}
	else if (bDocked && ((IsReserveFull() && IsRingFull()) || GetMobilityStateTime() > DockResupplyTimeout))
	{
		RequestUndock();
	}
}

bool ASubDrone_Attacker::IsBeingServiced() const
{
	if (GetMobilityState() == ESubDroneMobilityState::Docked)
	{
		return true;
	}
	const USubDroneBayComponent* BayPtr = GetBay();
	return BayPtr && BayPtr->IsAtServiceStation();
}

ESubDroneReloadResult ASubDrone_Attacker::CanStartReload() const
{
	const ESubDroneMobilityState Mobility = GetMobilityState();
	if (Mobility == ESubDroneMobilityState::Docking || IsBeingServiced())
	{
		return ESubDroneReloadResult::Unavailable;
	}
	if (bReloading)
	{
		return ESubDroneReloadResult::Busy;
	}
	if (IsRingFull())
	{
		return ESubDroneReloadResult::Full;
	}
	if (InternalReserveAmmo <= 0)
	{
		return ESubDroneReloadResult::NoReserve;
	}
	return ESubDroneReloadResult::Accepted;
}

void ASubDrone_Attacker::StartReload()
{
	if (CanStartReload() != ESubDroneReloadResult::Accepted)
	{
		return;
	}
	bReloading = true;
	RingRefillAccumulator = 0.f;
	if (CombatState == EAttackerCombatState::SpinUp || CombatState == EAttackerCombatState::Attack)
	{
		SetCombatState(EAttackerCombatState::Cooling); // the feed and the launcher never run together
	}
	bAmmoDirty = true;
	RoundFlights.Reset();
	ReloadFeedTime = 0.f;
	SetReloadPhase(EAttackerReloadPhase::Lower);
	BP_OnReloadStarted(FMath::Min(RingSlotCount - CurrentRingAmmo, InternalReserveAmmo));
}

// ------------------------------------------------------------------------------- reload choreography
void ASubDrone_Attacker::SetReloadPhase(EAttackerReloadPhase NewPhase)
{
	if (NewPhase == ReloadPhase)
	{
		return;
	}
	ReloadPhase = NewPhase;
	ReloadPhaseTime = 0.f;
	switch (NewPhase)
	{
	case EAttackerReloadPhase::Feed:
		ReloadFeedTime = 0.f;
		ReloadBubbleBurstTime = AttackerFx::BubbleBurstDuration; // breech opened: gas burst
		break;
	case EAttackerReloadPhase::Raise:
		ReloadRaiseDuration = ReloadRaiseTime;
		ReloadRaiseFromPose = FMath::Max(ReloadPoseAlpha, 0.f);
		ReloadRaiseFromBreech = FMath::Max(ReloadBreechAlpha, 0.f);
		ReloadBubbleBurstTime = AttackerFx::BubbleBurstDuration; // purge before closing
		break;
	default:
		break;
	}
	const UWorld* World = GetWorld();
	UE_LOG(LogSubDrone, Log, TEXT("%s reload phase -> %s (t=%.3f)"), *GetName(),
		*UEnum::GetValueAsString(NewPhase), World ? World->GetTimeSeconds() : 0.0);
	BP_OnReloadPhaseChanged(NewPhase);
}

void ASubDrone_Attacker::ApplyReloadPose(float PoseAlpha, float BreechAlpha)
{
	ReloadPoseAlpha = PoseAlpha;
	ReloadBreechAlpha = BreechAlpha;
	ReloadSafeAlpha = FMath::Clamp(PoseAlpha, 0.f, 1.f);

	// Inboard = toward the Shell centre line = opposite to the slot's lateral combat offset.
	const USubDroneBayComponent* BayPtr = GetBay();
	const float OffsetY = BayPtr ? static_cast<float>(BayPtr->GetCombatOffset(GetSlotIndex()).Y) : 1.f;
	const float YawSign = OffsetY >= 0.f ? -1.f : 1.f;

	const FRotator PoseRot(ReloadNosePitchDeg * PoseAlpha, YawSign * ReloadInboardYawDeg * PoseAlpha, 0.f);
	VisualRoot->SetRelativeTransform(VisualRootBase * FTransform(PoseRot, FVector(0.f, 0.f, -ReloadDropCm * PoseAlpha)));

	// Translation only: the hull roll is owned by TickSpin.
	HullRear->SetRelativeLocation(HullRearBase.GetLocation() + FVector(-ReloadBreechTravelCm * BreechAlpha, 0.f, 0.f));
}

void ASubDrone_Attacker::FinalizeRoundFlights()
{
	for (const FRoundFlight& Flight : RoundFlights)
	{
		TorpedoRing->UpdateInstanceTransform(Flight.Slot, MakeSlotTransform(Flight.Slot, SlotLoaded[Flight.Slot] != 0), false, false, true);
	}
	RoundFlights.Reset();
}

void ASubDrone_Attacker::BeginRaiseFromService()
{
	// Docking / service station mid-reload: the hardware is refilled anyway -> skip the feed, re-arm quickly. No energy refund.
	FinalizeRoundFlights();
	SetReloadPhase(EAttackerReloadPhase::Raise);
	ReloadRaiseDuration = ReloadRaiseTime * 0.5f;
}

void ASubDrone_Attacker::TickReloadAnim(float Dt)
{
	ReloadBubbleBurstTime = FMath::Max(0.f, ReloadBubbleBurstTime - Dt);
	if (ReloadPhase == EAttackerReloadPhase::None)
	{
		return;
	}
	ReloadPhaseTime += Dt;

	if ((ReloadPhase == EAttackerReloadPhase::Lower || ReloadPhase == EAttackerReloadPhase::Feed) &&
		(IsBeingServiced() || GetMobilityState() == ESubDroneMobilityState::Docking))
	{
		BeginRaiseFromService();
	}

	// Torpedoes in flight: breech -> slot, EaseOutBack, scale 0.35 -> 1.
	for (int32 Index = RoundFlights.Num() - 1; Index >= 0; --Index)
	{
		FRoundFlight& Flight = RoundFlights[Index];
		Flight.T += Dt;
		const float X = FMath::Clamp(Flight.T / FMath::Max(ReloadRoundFlightTime, 0.01f), 0.f, 1.f);
		if (X >= 1.f)
		{
			TorpedoRing->UpdateInstanceTransform(Flight.Slot, MakeSlotTransform(Flight.Slot, SlotLoaded[Flight.Slot] != 0), false, false, true);
			RoundFlights.RemoveAtSwap(Index, EAllowShrinking::No);
			continue;
		}
		const float E = AttackerFx::EaseOutBack(X, 1.f);
		const FVector SlotPos = GetSlotLocalPosition(Flight.Slot);
		const FVector Radial = FVector(0.f, SlotPos.Y, SlotPos.Z).GetSafeNormal() * (RingRadius * AttackerFx::FlightStartRadius01);
		const FVector StartPos(AttackerFx::FlightStartAxial, Radial.Y, Radial.Z);
		TorpedoRing->UpdateInstanceTransform(Flight.Slot,
			FTransform(FQuat::Identity, FMath::Lerp(StartPos, SlotPos, static_cast<double>(E)),
				FVector(FMath::Lerp(AttackerFx::FlightStartScale, 1.f, FMath::Clamp(E, 0.f, 1.f)))),
			false, false, true);
	}

	switch (ReloadPhase)
	{
	case EAttackerReloadPhase::Lower:
	{
		const float X = FMath::Clamp(ReloadPhaseTime / FMath::Max(ReloadLowerTime, 0.01f), 0.f, 1.f);
		ApplyReloadPose(AttackerFx::EaseInOutCubic(X), FMath::SmoothStep(0.6f, 1.f, X)); // breech opens in the last 40 %
		if (X >= 1.f)
		{
			SetReloadPhase(EAttackerReloadPhase::Feed);
		}
		break;
	}
	case EAttackerReloadPhase::Feed:
		ReloadFeedTime += Dt;
		ApplyReloadPose(1.f, 1.f);
		break;

	case EAttackerReloadPhase::Raise:
	{
		const float U = FMath::Clamp(ReloadPhaseTime / FMath::Max(ReloadRaiseDuration, 0.01f), 0.f, 1.f);
		const float C1 = ReloadRaiseOvershoot * 10.f;
		const float Pose = ReloadRaiseFromPose * (1.f - AttackerFx::EaseOutBack(U, C1));
		const float UB = FMath::Clamp(ReloadPhaseTime / AttackerFx::BreechSnapTime, 0.f, 1.f);
		const float Breech = ReloadRaiseFromBreech * (1.f - AttackerFx::EaseOutBack(UB, AttackerFx::BreechSnapOvershoot));
		if (U >= 1.f)
		{
			ApplyReloadPose(0.f, 0.f);
			SetReloadPhase(EAttackerReloadPhase::None);
			CompleteReload();
		}
		else
		{
			ApplyReloadPose(Pose, Breech);
		}
		break;
	}
	default:
		break;
	}
}

void ASubDrone_Attacker::EndFeed()
{
	// Replaces the old direct FinishReload: wait for the last torpedo to land (and the minimum readable feed time), then re-arm.
	if (ReloadPhase != EAttackerReloadPhase::Feed || !RoundFlights.IsEmpty() || ReloadFeedTime < ReloadMinFeedTime)
	{
		return;
	}
	SetReloadPhase(EAttackerReloadPhase::Raise);
}

void ASubDrone_Attacker::CompleteReload()
{
	bReloading = false;
	bAmmoDirty = true;
	BP_OnReloadFinished();
}

void ASubDrone_Attacker::TickVisuals(float Dt)
{
	const float Armed = FMath::SmoothStep(0.f, 1.f, GetDeployBlend()) * (1.f - ReloadSafeAlpha);
	const float Combat = GetCombatSpinNormalized();
	const float OmegaFront = SpinAlpha * MaxSpinDegPerSec;

	// Alert (resupply request): eased so the amber pulse fades in/out.
	AlertAlpha = DampTo(AlertAlpha, bResupplyRequested ? 1.f : 0.f, 0.15f, Dt);

	const float BaseGlow = FMath::Lerp(GlowFormation, GlowArmed, Armed);
	float Glow = FMath::Lerp(BaseGlow, GlowMax, FMath::Pow(Combat, 1.5f));
	if (ReloadPhase == EAttackerReloadPhase::Raise && ReloadPhaseTime < AttackerFx::GlowFlashTime)
	{
		Glow = FMath::Max(Glow, GlowArmed * 2.f); // re-arm flash
	}
	const float Hz = FMath::Lerp(FMath::Lerp(PulseIdleHz, PulseArmedHz, Armed), PulseMaxHz, Combat);

	// Pulse PHASE is integrated on the CPU: changing the frequency never makes the pulse jump.
	FrontPulsePhase = FMath::Frac(FrontPulsePhase + Hz * Dt);
	RearPulsePhase = FMath::Frac(RearPulsePhase + Hz * FMath::Abs(RearSpinRatio) * Dt);

	// Custom Primitive Data (no MIDs): pushed only when changed.
	auto PushSpiral = [this](UStaticMeshComponent* Comp, const FVector4f& Value, FVector4f& Last)
	{
		if (!Value.Equals(Last, 1e-3f))
		{
			Comp->SetCustomPrimitiveDataVector4(SubDroneCPD::GlowIntensity, FVector4(Value));
			Last = Value;
		}
	};
	const float Dir = OmegaFront >= 0.f ? 1.f : -1.f;
	PushSpiral(HullFront, FVector4f(Glow, FrontPulsePhase, Dir, Combat), LastFrontCPD);
	PushSpiral(HullRear, FVector4f(Glow, RearPulsePhase, Dir * FMath::Sign(RearSpinRatio), Combat), LastRearCPD);

	const FVector3f CoreValue(SpinAlpha, AlertAlpha, Heat);
	if (!CoreValue.Equals(LastCoreCPD, 1e-3f))
	{
		// Alert also drives the spiral slot 4 on both hull halves.
		HullFront->SetCustomPrimitiveDataFloat(SubDroneCPD::AlertAlpha, AlertAlpha);
		HullRear->SetCustomPrimitiveDataFloat(SubDroneCPD::AlertAlpha, AlertAlpha);
		CoreMesh->SetCustomPrimitiveDataVector3(SubDroneCPD::SpinAlpha, FVector(CoreValue));
		LastCoreCPD = CoreValue;
	}

	// Induction glow of the resting torpedoes.
	const float RingCharge = FMath::Lerp(FMath::Lerp(RingChargeFormation, RingChargeArmed, Armed), 1.f, Combat);
	if (FMath::Abs(RingCharge - LastRingCharge) > 0.01f)
	{
		TorpedoRing->SetCustomPrimitiveDataFloat(SubDroneCPD::TorpedoCharge, RingCharge);
		LastRingCharge = RingCharge;
	}

	// NS_CoreVortex: vapour-gas ring only while winding up / attacking.
	if (CavityFX->GetAsset() && !bVortexWarming)
	{
		const bool bWant = GetMobilityState() == ESubDroneMobilityState::Deployed && SpinAlpha > CavityFXActivationAlpha;
		if (bWant != CavityFX->IsActive())
		{
			bWant ? CavityFX->Activate(true) : CavityFX->Deactivate();
			LastVortexRate = -1.f;
		}
		if (bWant)
		{
			AttackerFx::SetFxFloat(CavityFX, AttackerFx::VortexRate, VortexMaxRate * FMath::Pow(Combat, 1.2f), LastVortexRate);
		}
	}

	// NS_DroneBubbles: always alive while flying, denser with speed and spin.
	if (HullBubblesFX->GetAsset())
	{
		const bool bWant = GetMobilityState() != ESubDroneMobilityState::Docked;
		if (bWant != HullBubblesFX->IsActive())
		{
			bWant ? HullBubblesFX->Activate(true) : HullBubblesFX->Deactivate();
			LastBubbleRate = -1.f;
		}
		if (bWant)
		{
			const float Speed01 = FMath::Clamp(static_cast<float>(GetKinematicVelocity().Size()) / 1500.f, 0.f, 1.f);
			AttackerFx::SetFxFloat(HullBubblesFX, AttackerFx::BubbleRate,
				(BubbleBaseRate + BubbleSpeedRate * Speed01 + BubbleSpinRate * SpinAlpha) *
					(ReloadBubbleBurstTime > 0.f ? AttackerFx::BubbleBurstMul : 1.f), LastBubbleRate);
		}
	}
}

// ------------------------------------------------------------------------------- firing
int32 ASubDrone_Attacker::PickReleaseSlot()
{
	// Muzzle advances by the golden angle; the loaded slot closest to it is released
	// -> evenly spread release directions (spiral "bloom" that converges on the target).
	MuzzleAngleDeg = WrapDegrees(MuzzleAngleDeg + MuzzleStepDegrees);

	const double Step = 360.0 / FMath::Max(RingSlotCount, 1);
	int32 Best = INDEX_NONE;
	double BestDelta = TNumericLimits<double>::Max();
	for (int32 Slot = 0; Slot < SlotLoaded.Num(); ++Slot)
	{
		if (!SlotLoaded[Slot])
		{
			continue;
		}
		const double Delta = FMath::Abs(FMath::FindDeltaAngleDegrees(WrapDegrees(Slot * Step + RingAngleDeg), MuzzleAngleDeg));
		if (Delta < BestDelta)
		{
			BestDelta = Delta;
			Best = Slot;
		}
	}
	return Best;
}

void ASubDrone_Attacker::FireOnce()
{
	UWorld* World = GetWorld();
	const int32 Slot = PickReleaseSlot();
	if (!World || Slot == INDEX_NONE)
	{
		return;
	}
	AMicroTorpedo* Torpedo = AcquireTorpedo();
	if (!Torpedo)
	{
		return;
	}

	const FTransform PivotXf = RingPivot->GetComponentTransform();
	const FVector Axis = PivotXf.GetUnitAxis(EAxis::X);
	const FVector SlotWorld = PivotXf.TransformPosition(GetSlotLocalPosition(Slot));
	FVector Radial = SlotWorld - PivotXf.GetLocation();
	Radial -= Axis * FVector::DotProduct(Radial, Axis);
	const FVector RadialDir = Radial.GetSafeNormal();

	// Sling kinematics: v = v_drone + (omega x r) + radial push + axial push (exact ring derivative).
	const FVector Tangential = FVector::CrossProduct(Axis, Radial) * FMath::DegreesToRadians(static_cast<double>(RingSpinDegPerSec));
	const FVector ReleaseVel = GetKinematicVelocity() + Tangential + RadialDir * ReleaseRadialSpeed + Axis * ReleaseAxialSpeed;
	const FQuat ReleaseRot = FRotationMatrix::MakeFromXZ(Axis, RadialDir.IsNearlyZero() ? GetActorUpVector() : RadialDir).ToQuat();

	SetSlotLoaded(Slot, false); // flushed with the other ring changes this frame

	const FVector Target = bHasAimPoint ? AimPoint : GetActorLocation() + GetActorForwardVector() * 3000.f;
	Torpedo->Launch(SlotWorld, ReleaseRot, ReleaseVel, Target, AimActor.Get());

	// Lab 5: salvo -> evasion model of the Reapers, and the launch noise for AI hearing.
	if (UAOS_CombatThreatSubsystem* Threats = World->GetSubsystem<UAOS_CombatThreatSubsystem>())
	{
		Threats->ReportTorpedoLaunch(Torpedo, GetOwner(), SlotWorld, Target, AimActor.Get());
	}
	UAISense_Hearing::ReportNoiseEvent(World, SlotWorld, 1.0f, GetOwner(), 4500.f, TEXT("TorpedoLaunch"));

	LastShotTime = World->GetTimeSeconds();
	Heat += HeatPerShot;
	if (Heat >= 1.f)
	{
		Heat = 1.f;
		bOverheated = true;
		BP_OnOverheated();
	}
	BP_OnTorpedoFired(FTransform(ReleaseRot, SlotWorld), Slot);
}

AMicroTorpedo* ASubDrone_Attacker::AcquireTorpedo()
{
	const UWorld* World = GetWorld();
	if (!World)
	{
		return nullptr;
	}
	const double Now = World->GetTimeSeconds();
	for (AMicroTorpedo* Torpedo : TorpedoPool)
	{
		if (IsValid(Torpedo) && Torpedo->IsAvailableForReuse(Now))
		{
			return Torpedo;
		}
	}
	return TorpedoPool.Num() < MaxPoolSize ? SpawnPooledTorpedo() : nullptr;
}

void ASubDrone_Attacker::TickPoolWarmup(float Dt)
{
	if (bPoolWarmupDone)
	{
		return;
	}
	// 1) Finish the pool in small slices (no spawn spike at BeginPlay, none during fire).
	if (TorpedoPool.Num() < PoolPrewarmCount)
	{
		for (int32 Count = 0; Count < PoolSpawnPerFrame && TorpedoPool.Num() < PoolPrewarmCount; ++Count)
		{
			if (!SpawnPooledTorpedo())
			{
				break;
			}
		}
		return;
	}
	// 2) Invisible draw of every torpedo visual, one torpedo per frame: PSOs, Niagara simulations and
	//    per-component render state are created now instead of on the first shot.
	PoolWarmupClock += Dt;
	if (PoolWarmupClock < PoolWarmupDelay)
	{
		return;
	}
	// The engine only draws what the camera sees, so the warm-up pieces are parked 1.5 m in front of the active camera
	// (microscopic and at zero intensity, nothing visible). No camera yet -> try again next frame.
	const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0);
	if (!Cam)
	{
		return;
	}
	const FVector WarmLoc = Cam->GetCameraLocation() + Cam->GetCameraRotation().Vector() * 150.0;
	if (PoolWarmupIndex < TorpedoPool.Num())
	{
		if (AMicroTorpedo* Torpedo = TorpedoPool[PoolWarmupIndex])
		{
			Torpedo->BeginWarmup(/*bSpawnImpactFx*/ PoolWarmupIndex == 0, WarmLoc);
		}
		++PoolWarmupIndex;
		return;
	}
	// 3) NS_CoreVortex: otherwise its first activation and first particle draw (~70 ms render thread) hit the first wind-up.
	//    Emits at microscopic scale for VortexWarmupFrames frames (the cost lands ~6 frames after Activate), then is cleared.
	if (VortexWarmupFrame < VortexWarmupFrames)
	{
		if (!CavityFX->GetAsset() || (VortexWarmupFrame == 0 && CavityFX->IsActive()))
		{
			VortexWarmupFrame = VortexWarmupFrames; // nothing to warm / combat already started
			return;
		}
		if (VortexWarmupFrame == 0 && GetMobilityState() != ESubDroneMobilityState::Deployed)
		{
			return; // wait for the first deploy: the effect is first used in the water, warm it in the same context
		}
		if (VortexWarmupFrame == 0)
		{
			// Real scale, in place, in the water (tiny-scale / camera-parked warm-ups did not remove the first-wind-up stall):
			// a brief faint vapour puff on the drone while it deploys instead of a 65 ms hitch on the first shot.
			CavityFX->SetVariableFloat(AttackerFx::VortexRate, VortexMaxRate * 0.3f);
			CavityFX->Activate(true);
			bVortexWarming = true;
		}
		if (++VortexWarmupFrame >= VortexWarmupFrames)
		{
			CavityFX->DeactivateImmediate();
			LastVortexRate = -1.f;
			bVortexWarming = false;
		}
		return;
	}
	bPoolWarmupDone = true;
	UE_LOG(LogSubDrone, Log, TEXT("%s torpedo pool ready: %d pooled, effects warmed"), *GetName(), TorpedoPool.Num());
}

AMicroTorpedo* ASubDrone_Attacker::SpawnPooledTorpedo()
{
	UWorld* World = GetWorld();
	if (!World || !TorpedoClass)
	{
		return nullptr;
	}
	FActorSpawnParameters Params;
	Params.Owner = this;
	Params.Instigator = GetHostPawn(); // damage is attributed to the Shell's controller
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	AMicroTorpedo* Torpedo = World->SpawnActor<AMicroTorpedo>(TorpedoClass, GetActorTransform(), Params);
	if (Torpedo)
	{
		TorpedoPool.Add(Torpedo);
	}
	return Torpedo;
}

// ------------------------------------------------------------------------------- facing / FSM
bool ASubDrone_Attacker::GetDesiredFacing(FQuat& OutFacing) const
{
	// Deployed: the nose tracks the crosshair continuously ("ready to fire" is readable at a glance).
	if (bHasAimPoint && GetMobilityState() == ESubDroneMobilityState::Deployed)
	{
		OutFacing = MakeLookQuat(AimPoint - GetActorLocation(), GetFilteredHostFrame().GetUpVector(), GetActorQuat());
		return true;
	}
	return false;
}

void ASubDrone_Attacker::OnMobilityStateEntered(ESubDroneMobilityState NewState, ESubDroneMobilityState OldState)
{
	Super::OnMobilityStateEntered(NewState, OldState);
	if ((NewState == ESubDroneMobilityState::Docking || NewState == ESubDroneMobilityState::Docked) &&
		(ReloadPhase == EAttackerReloadPhase::Lower || ReloadPhase == EAttackerReloadPhase::Feed))
	{
		BeginRaiseFromService();
	}
	if (NewState != ESubDroneMobilityState::Deployed)
	{
		// Leaving the combat position drops a held trigger: after the next R the player must press LMB again.
		bTriggerHeld = false;
		if (CombatState == EAttackerCombatState::SpinUp || CombatState == EAttackerCombatState::Attack)
		{
			SetCombatState(EAttackerCombatState::Cooling);
		}
	}
}
