#include "AOS_DK/Submarine/Subdrones/Attacker/SubDrone_Attacker.h"

#include "AOS_DK/Submarine/Subdrones/Attacker/MicroTorpedo.h"
#include "AOS_DK/Submarine/Subdrones/Attacker/TorpedoReloadPolicy.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneMath.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
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

	if (SlotLoaded.Num() != RingSlotCount)
	{
		BuildRing();
	}
	InternalReserveAmmo = bStartWithFullAmmo ? InternalReserveCapacity : 0;

	for (int32 Index = 0; Index < PoolPrewarmCount; ++Index)
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

void ASubDrone_Attacker::SetSlotLoaded(int32 Slot, bool bLoaded)
{
	if (SlotLoaded[Slot] == static_cast<uint8>(bLoaded))
	{
		return;
	}
	SlotLoaded[Slot] = bLoaded ? 1 : 0;
	CurrentRingAmmo += bLoaded ? 1 : -1;
	DirtySlots.AddUnique(Slot);
	bAmmoDirty = true;
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
	const int32 Accepted = FMath::Clamp(Count, 0, InternalReserveCapacity - InternalReserveAmmo);
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
	TickSpin(DeltaSeconds);
	TickAmmo(DeltaSeconds);
	FlushRingUpdates();
	TickVisuals(DeltaSeconds);

	if (bAmmoDirty)
	{
		bAmmoDirty = false;
		OnAmmoChanged.Broadcast(CurrentRingAmmo, RingSlotCount, InternalReserveAmmo, InternalReserveCapacity);
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

	const bool bWantFire = bTriggerHeld && CanEngage() && !bOverheated && CurrentRingAmmo > 0;

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
	float Target = FMath::Lerp(FormationSpinAlpha, ArmedSpinAlpha, GetDeployBlend());
	if (GetMobilityState() == ESubDroneMobilityState::Docked)
	{
		Target = 0.f;
	}
	else if (CombatState == EAttackerCombatState::SpinUp || CombatState == EAttackerCombatState::Attack)
	{
		Target = 1.f;
	}

	const float Tau = Target > SpinAlpha ? SpinUpTimeConstant : SpinDownTimeConstant;
	SpinAlpha = MotorStep(SpinAlpha, Target, Tau, Dt);
	if (SpinAlpha < 1e-4f && Target <= 0.f)
	{
		SpinAlpha = 0.f;
		RingSpinDegPerSec = 0.f;
		return; // parked: no transform updates
	}

	const double OmegaFront = static_cast<double>(SpinAlpha) * MaxSpinDegPerSec;
	RingSpinDegPerSec = SpinAlpha * RingMaxSpinDegPerSec;

	FrontAngleDeg = WrapDegrees(FrontAngleDeg + OmegaFront * Dt);
	RearAngleDeg = WrapDegrees(RearAngleDeg + OmegaFront * RearSpinRatio * Dt);
	RingAngleDeg = WrapDegrees(RingAngleDeg + static_cast<double>(RingSpinDegPerSec) * Dt);

	HullFront->SetRelativeRotation(FQuat(FVector::XAxisVector, FMath::DegreesToRadians(FrontAngleDeg)));
	HullRear->SetRelativeRotation(FQuat(FVector::XAxisVector, FMath::DegreesToRadians(RearAngleDeg)));
	RingPivot->SetRelativeRotation(FQuat(FVector::XAxisVector, FMath::DegreesToRadians(RingAngleDeg)));
}

void ASubDrone_Attacker::TickAmmo(float Dt)
{
	const ESubDroneMobilityState Mobility = GetMobilityState();
	const bool bDocked = Mobility == ESubDroneMobilityState::Docked;

	// Tier 3 -> 2: reserve supply (Shell dock or generator).
	if (ReserveSupplyPolicy)
	{
		const int32 Granted = ReserveSupplyPolicy->TickReserveResupply(*this, Dt);
		if (Granted > 0)
		{
			AddToReserve(Granted);
		}
	}

	// Tier 2 -> 1: magnetic ring refill from the internal reserve.
	const bool bCanRefill = !IsRingFull() && InternalReserveAmmo > 0 &&
		(bDocked || (!IsFiring() && GetTimeSinceLastShot() >= RingRefillDelayAfterShot));
	if (bCanRefill)
	{
		const float Interval = bDocked ? DockedRingRefillInterval : RingRefillInterval;
		RingRefillAccumulator += Dt;
		for (int32 Slot = 0; Slot < SlotLoaded.Num() && RingRefillAccumulator >= Interval && InternalReserveAmmo > 0; ++Slot)
		{
			if (!SlotLoaded[Slot])
			{
				SetSlotLoaded(Slot, true);
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

	// Resupply request: reserve exhausted and the policy needs the Shell.
	const bool bNeedResupply = ReserveSupplyPolicy && ReserveSupplyPolicy->RequiresDocking() && InternalReserveAmmo == 0 && !bDocked;
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

void ASubDrone_Attacker::TickVisuals(float Dt)
{
	const float Armed = FMath::SmoothStep(0.f, 1.f, GetDeployBlend());
	const float Combat = GetCombatSpinNormalized();
	const float OmegaFront = SpinAlpha * MaxSpinDegPerSec;

	// Alert (resupply request): eased so the amber pulse fades in/out.
	AlertAlpha = DampTo(AlertAlpha, bResupplyRequested ? 1.f : 0.f, 0.15f, Dt);

	const float BaseGlow = FMath::Lerp(GlowFormation, GlowArmed, Armed);
	const float Glow = FMath::Lerp(BaseGlow, GlowMax, FMath::Pow(Combat, 1.5f));
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
	if (CavityFX->GetAsset())
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
				BubbleBaseRate + BubbleSpeedRate * Speed01 + BubbleSpinRate * SpinAlpha, LastBubbleRate);
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
