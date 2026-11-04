#pragma once

#include "CoreMinimal.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBase.h"
#include "SubDrone_Attacker.generated.h"

class UStaticMeshComponent;
class UInstancedStaticMeshComponent;
class UNiagaraComponent;
class UTorpedoReloadPolicy;
class AMicroTorpedo;

/** Combat layer of the Attacker (orthogonal to the mobility FSM of ASubDroneBase). */
UENUM(BlueprintType)
enum class EAttackerCombatState : uint8
{
	Idle     UMETA(DisplayName = "Idle"),      // formation / armed idle spin
	SpinUp   UMETA(DisplayName = "Spin Up"),   // counter-rotation accelerates, ring winds up
	Attack   UMETA(DisplayName = "Attack"),    // above threshold: micro-torpedoes leave the ring
	Cooling  UMETA(DisplayName = "Cooling")    // spin-down / generator heat dissipation
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnAttackerCombatStateChanged, EAttackerCombatState, NewState, EAttackerCombatState, OldState);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FOnAttackerAmmoChanged, int32, RingAmmo, int32, RingCapacity, int32, ReserveAmmo, int32, ReserveCapacity);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAttackerResupplyRequest, bool, bResupplyRequested);

/**
 * Attacker module (OS analogue: antivirus).
 * Two counter-rotating hull sections around an induction generator; a magnetic ring of
 * cavitation micro-torpedoes in the central groove.
 *
 * Ammo is two-tier: CurrentRingAmmo (ring, visible) <- InternalReserveAmmo (inside the drone)
 * <- Shell (docking, via the reserve supply policy). An exhausted reserve raises a resupply
 * request; once the ring is empty too, the drone docks on the Shell, reloads and returns.
 */
UCLASS(Blueprintable)
class AOS_DK_API ASubDrone_Attacker : public ASubDroneBase
{
	GENERATED_BODY()

public:
	ASubDrone_Attacker();

	virtual void Tick(float DeltaSeconds) override;
	virtual void OnConstruction(const FTransform& Transform) override;

	virtual void StartPrimaryAction() override;
	virtual void StopPrimaryAction() override;

	// --- Ammo API ------------------------------------------------------------------------------
	/** Entry point for every reserve source (policy, pickups, Shell). Returns accepted count. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Attacker")
	int32 AddToReserve(int32 Count);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	int32 GetRingAmmo() const { return CurrentRingAmmo; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	int32 GetRingCapacity() const { return RingSlotCount; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	int32 GetReserveAmmo() const { return InternalReserveAmmo; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	int32 GetReserveCapacity() const { return InternalReserveCapacity; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	bool IsRingFull() const { return CurrentRingAmmo >= RingSlotCount; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	bool IsReserveFull() const { return InternalReserveAmmo >= InternalReserveCapacity; }

	/** Reserve exhausted and the supply policy needs the Shell. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	bool IsResupplyRequested() const { return bResupplyRequested; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	bool IsFiring() const { return CombatState == EAttackerCombatState::Attack; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	float GetTimeSinceLastShot() const;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	EAttackerCombatState GetCombatState() const { return CombatState; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	float GetSpinAlpha() const { return SpinAlpha; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Attacker")
	float GetHeat() const { return Heat; }

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Attacker")
	FOnAttackerCombatStateChanged OnCombatStateChanged;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Attacker")
	FOnAttackerAmmoChanged OnAmmoChanged;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Attacker")
	FOnAttackerResupplyRequest OnResupplyRequestChanged;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual bool GetDesiredFacing(FQuat& OutFacing) const override;
	virtual void OnMobilityStateEntered(ESubDroneMobilityState NewState, ESubDroneMobilityState OldState) override;

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Attacker", meta = (DisplayName = "On Combat State Changed"))
	void BP_OnCombatStateChanged(EAttackerCombatState NewState, EAttackerCombatState OldState);

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Attacker", meta = (DisplayName = "On Torpedo Fired"))
	void BP_OnTorpedoFired(const FTransform& ReleaseTransform, int32 RingSlot);

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Attacker", meta = (DisplayName = "On Overheated"))
	void BP_OnOverheated();

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Attacker", meta = (DisplayName = "On Resupply Request Changed"))
	void BP_OnResupplyRequestChanged(bool bRequested);

	// --- Components ---------------------------------------------------------------------------
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> HullFront;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> HullRear;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> CoreMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> RingPivot;

	/** One instance per ring slot (SM_MicroTorpedo). Updated only on fire/refill events. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UInstancedStaticMeshComponent> TorpedoRing;

	/** NS_CoreVortex: vapour-gas ring in the groove during spin-up/attack (child of RingPivot -> co-rotates). User.VortexRate. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UNiagaraComponent> CavityFX;

	/** NS_DroneBubbles: micro-bubbles around the hull. User.BubbleRate. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UNiagaraComponent> HullBubblesFX;

	// --- Spin ---------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Spin", meta = (ClampMin = "1", Units = "DegreesPerSecond"))
	float MaxSpinDegPerSec = 2160.f;

	/** Slow "alive" spin while in formation. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Spin", meta = (ClampMin = "0", ClampMax = "1"))
	float FormationSpinAlpha = 0.03f;

	/** Armed idle spin in the working position - visibly "ready". */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Spin", meta = (ClampMin = "0", ClampMax = "1"))
	float ArmedSpinAlpha = 0.12f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Spin", meta = (ClampMin = "0.01", Units = "s"))
	float SpinUpTimeConstant = 0.35f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Spin", meta = (ClampMin = "0.01", Units = "s"))
	float SpinDownTimeConstant = 0.9f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Spin", meta = (ClampMin = "0", ClampMax = "1"))
	float FireSpinThreshold = 0.85f;

	/** -1 = perfect counter-rotation (zero net torque). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Spin", meta = (ClampMin = "-2", ClampMax = "2"))
	float RearSpinRatio = -1.f;

	/** Ring speed at full spin (kept low to avoid wagon-wheel aliasing at 60 fps). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Spin", meta = (Units = "DegreesPerSecond"))
	float RingMaxSpinDegPerSec = 420.f;

	// --- Ammo: ring (tier 1) --------------------------------------------------------------------
	/** CurrentRingAmmo capacity = visible slots in the magnetic ring. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Ammo", meta = (ClampMin = "1", ClampMax = "96"))
	int32 RingSlotCount = 18;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Ammo", meta = (ClampMin = "0", Units = "cm"))
	float RingRadius = 13.5f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Ammo", meta = (Units = "cm"))
	float RingAxialOffset = 0.f;

	/** Ring refill from the reserve (one torpedo per interval). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Ammo", meta = (ClampMin = "0.01", Units = "s"))
	float RingRefillInterval = 0.12f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Ammo", meta = (ClampMin = "0", Units = "s"))
	float RingRefillDelayAfterShot = 0.35f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Ammo", meta = (ClampMin = "0.005", Units = "s"))
	float DockedRingRefillInterval = 0.04f;

	// --- Ammo: internal reserve (tier 2) ---------------------------------------------------------
	/** InternalReserveAmmo capacity (default 3 full ring reloads). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Ammo", meta = (ClampMin = "0"))
	int32 InternalReserveCapacity = 54;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Ammo")
	bool bStartWithFullAmmo = true;

	/** Ring and reserve empty + resupply requested -> fly to the Shell dock automatically. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Ammo")
	bool bAutoDockWhenEmpty = true;

	/** Safety: leave the dock after this long even if the Shell could not supply everything. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Ammo", meta = (ClampMin = "0.5", Units = "s"))
	float DockResupplyTimeout = 6.f;

	/** How the internal reserve is refilled (Dock Resupply by default; Timed Regeneration as alternative). */
	UPROPERTY(EditAnywhere, Instanced, BlueprintReadOnly, Category = "AOS_DK|Attacker|Ammo")
	TObjectPtr<UTorpedoReloadPolicy> ReserveSupplyPolicy;

	// --- Weapon ---------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Weapon")
	TSubclassOf<AMicroTorpedo> TorpedoClass;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Weapon", meta = (ClampMin = "0.01", Units = "s"))
	float FireInterval = 0.085f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Weapon", meta = (Units = "CentimetersPerSecond"))
	float ReleaseAxialSpeed = 150.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Weapon", meta = (Units = "CentimetersPerSecond"))
	float ReleaseRadialSpeed = 600.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Weapon", meta = (Units = "Degrees"))
	float MuzzleStepDegrees = 137.50776f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Weapon", meta = (ClampMin = "0"))
	int32 PoolPrewarmCount = 8;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Weapon", meta = (ClampMin = "1"))
	int32 MaxPoolSize = 48;

	/** Deploy blend above which the drone may open fire. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Weapon", meta = (ClampMin = "0", ClampMax = "1"))
	float EngageDeployBlend = 0.85f;

	// --- Heat -----------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Heat", meta = (ClampMin = "0", ClampMax = "1"))
	float HeatPerShot = 0.04f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Heat", meta = (ClampMin = "0"))
	float HeatDissipationPerSec = 0.3f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Heat", meta = (ClampMin = "0", ClampMax = "1"))
	float OverheatResumeHeat = 0.3f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Heat", meta = (ClampMin = "0", Units = "s"))
	float CoolingMinDuration = 0.3f;

	// --- Visual drive (Custom Primitive Data + Niagara user parameters) -------------------------
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual")
	float GlowFormation = 1.2f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual")
	float GlowArmed = 6.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual")
	float GlowMax = 40.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual", meta = (Units = "Hz"))
	float PulseIdleHz = 0.3f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual", meta = (Units = "Hz"))
	float PulseArmedHz = 1.2f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual", meta = (Units = "Hz"))
	float PulseMaxHz = 9.f;

	/** Induction glow of the torpedoes resting in the ring (formation / armed). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual", meta = (ClampMin = "0", ClampMax = "1"))
	float RingChargeFormation = 0.45f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual", meta = (ClampMin = "0", ClampMax = "1"))
	float RingChargeArmed = 0.8f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual", meta = (ClampMin = "0", ClampMax = "1"))
	float CavityFXActivationAlpha = 0.15f;

	/** Peak vortex particle rate (NS_CoreVortex User.VortexRate). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual", meta = (ClampMin = "0"))
	float VortexMaxRate = 900.f;

	/** NS_DroneBubbles User.BubbleRate = Base + Speed * speed01 + Spin * spin01. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual", meta = (ClampMin = "0"))
	float BubbleBaseRate = 25.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual", meta = (ClampMin = "0"))
	float BubbleSpeedRate = 180.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Attacker|Visual", meta = (ClampMin = "0"))
	float BubbleSpinRate = 140.f;

private:
	void BuildRing();
	FVector GetSlotLocalPosition(int32 Slot) const;
	FTransform MakeSlotTransform(int32 Slot, bool bLoaded) const;
	void SetSlotLoaded(int32 Slot, bool bLoaded);
	void FlushRingUpdates();

	void SetCombatState(EAttackerCombatState NewState);
	bool CanEngage() const;
	void TickCombat(float Dt);
	void TickSpin(float Dt);
	void TickAmmo(float Dt);
	void TickVisuals(float Dt);
	void UpdateAim();
	float GetCombatSpinNormalized() const;

	void FireOnce();
	int32 PickReleaseSlot();
	AMicroTorpedo* AcquireTorpedo();
	AMicroTorpedo* SpawnPooledTorpedo();

	EAttackerCombatState CombatState = EAttackerCombatState::Idle;
	float CombatStateTime = 0.f;
	bool bTriggerHeld = false;
	bool bOverheated = false;

	float SpinAlpha = 0.f;
	float RingSpinDegPerSec = 0.f;
	double FrontAngleDeg = 0.0;
	double RearAngleDeg = 0.0;
	double RingAngleDeg = 0.0;
	double MuzzleAngleDeg = 0.0;

	float Heat = 0.f;
	float FireAccumulator = 0.f;
	float RingRefillAccumulator = 0.f;
	double LastShotTime = -1000.0;

	TArray<uint8> SlotLoaded;
	TArray<int32> DirtySlots;
	int32 CurrentRingAmmo = 0;
	int32 InternalReserveAmmo = 0;
	bool bResupplyRequested = false;
	bool bAmmoDirty = true;

	FVector AimPoint = FVector::ZeroVector;
	TWeakObjectPtr<AActor> AimActor;
	bool bHasAimPoint = false;

	// Cached visual state (only push to the renderer / Niagara on change)
	float FrontPulsePhase = 0.f;
	float RearPulsePhase = 0.f;
	float AlertAlpha = 0.f;
	float LastRingCharge = -1.f;
	float LastVortexRate = -1.f;
	float LastBubbleRate = -1.f;
	FVector4f LastFrontCPD = FVector4f(-1.f);
	FVector4f LastRearCPD = FVector4f(-1.f);
	FVector3f LastCoreCPD = FVector3f(-1.f);

	UPROPERTY(Transient)
	TArray<TObjectPtr<AMicroTorpedo>> TorpedoPool;
};
