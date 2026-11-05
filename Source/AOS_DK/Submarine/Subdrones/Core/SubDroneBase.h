#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneTypes.h"
#include "SubDroneBase.generated.h"

class USphereComponent;
class USubDroneBayComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FOnSubDroneMobilityChanged, ASubDroneBase*, Drone, ESubDroneMobilityState, NewState, ESubDroneMobilityState, OldState);

/**
 * Base "process" of every Shell module-drone.
 *
 * Passive  (Formation): flies with the Shell in a crescent slot that is always in the camera view.
 * Active   (Deployed) : on R the drone swoops forward/sideways into its working position and floats
 *                       there more loosely, nose following the module's own facing (aim for the Attacker).
 * Resupply (Docking/Docked): flies to its hull socket, attaches, reloads, returns to formation.
 *
 * Formation <-> Deployed is a continuous blend (DeployBlend) of goal position, motion profile and
 * visuals, so there is never a hard snap. Movement: filtered Shell frame + exact critically damped
 * spring with Shell-velocity feed-forward, soft comfort zone, swept against WorldStatic, kept under
 * the water surface. One actor transform update per frame (no per-frame child re-parenting).
 */
UCLASS(Abstract, Blueprintable)
class AOS_DK_API ASubDroneBase : public AActor
{
	GENERATED_BODY()

public:
	ASubDroneBase();

	virtual void Tick(float DeltaSeconds) override;

	/** Called by the bay between SpawnActorDeferred and FinishSpawning. */
	void InitializeDrone(USubDroneBayComponent* InBay, int32 InSlotIndex);

	/** Go to the working position (or remember the wish while a resupply is running). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|SubDrone")
	void RequestDeploy();

	/** Back to the crescent formation (or cancel the deploy wish during a resupply). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|SubDrone")
	void RequestRecall();

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|SubDrone")
	void ToggleDeployment();

	/** Fly to the hull socket for a physical resupply. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|SubDrone")
	void RequestDock();

	/** Leave the hull socket; goes to Deployed if that was requested during the resupply. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|SubDrone")
	void RequestUndock();

	/** Primary module action (Attacker: spin-up & fire; Defender: shield; ...). */
	virtual void StartPrimaryAction() {}
	virtual void StopPrimaryAction() {}

	// --- Manual reload (IA_Sub_DroneReload, routed and paid for by USubDroneBayComponent) ----------
	/** Accepted = a reload can start right now; otherwise the reason. Default: nothing to reload. */
	virtual ESubDroneReloadResult CanStartReload() const { return ESubDroneReloadResult::NotSupported; }

	/** One-shot Shell energy cost of a manual reload, % of the core. */
	virtual float GetReloadEnergyCost() const { return 0.f; }

	/** Starts the reload. Called by the bay only after CanStartReload() == Accepted and the energy was paid. */
	virtual void StartReload() {}

	/**
	 * Strict input filter for the primary action (LMB): only a drone that was explicitly sent to its
	 * working position with R (MobilityState == Deployed) accepts it. In Formation / Docking / Docked the
	 * press is ignored entirely - the primary action never changes the mobility state (slot-system safe).
	 */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|SubDrone")
	bool AcceptsPrimaryAction() const { return MobilityState == ESubDroneMobilityState::Deployed; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|SubDrone")
	ESubDroneMobilityState GetMobilityState() const { return MobilityState; }

	/** Deployed, or wants to be deployed once the running resupply ends. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|SubDrone")
	bool IsDeployed() const;

	/** 0 = formation, 1 = working position (smoothed). */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|SubDrone")
	float GetDeployBlend() const { return DeployBlend; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|SubDrone")
	APawn* GetHostPawn() const { return HostPawn.Get(); }

	USubDroneBayComponent* GetBay() const { return Bay.Get(); }
	int32 GetSlotIndex() const { return SlotIndex; }
	const FVector& GetKinematicVelocity() const { return Velocity; }

	/** true while the drone is phasing through geometry to get unstuck. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|SubDrone")
	bool IsPhasing() const { return bPhasing; }

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|SubDrone")
	FOnSubDroneMobilityChanged OnMobilityChanged;

protected:
	virtual void BeginPlay() override;

	// --- Hooks for specialised modules ---------------------------------------------------
	virtual void OnMobilityStateEntered(ESubDroneMobilityState NewState, ESubDroneMobilityState OldState) {}
	/** Facing override; return false to follow the filtered Shell frame. */
	virtual bool GetDesiredFacing(FQuat& OutFacing) const { return false; }

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|SubDrone", meta = (DisplayName = "On Mobility State Changed"))
	void BP_OnMobilityStateChanged(ESubDroneMobilityState NewState, ESubDroneMobilityState OldState);

	/** Unstuck hook (FX / sound): phasing through an obstacle started / ended. */
	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|SubDrone", meta = (DisplayName = "On Phase Shift"))
	void BP_OnPhaseShift(bool bPhasingNow);

	/** Unstuck hook: the drone was relocated next to the Shell (last-resort rescue). */
	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|SubDrone", meta = (DisplayName = "On Rescue Teleport"))
	void BP_OnRescueTeleport(const FVector& From, const FVector& To);

	const FQuat& GetFilteredHostFrame() const { return FilteredHostFrame; }
	float GetMobilityStateTime() const { return MobilityStateTime; }

	// --- Components ------------------------------------------------------------------------
	/** Kinematic sweep body: QueryOnly, blocks WorldStatic only (never pushes the Shell). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USphereComponent> CollisionSphere;

	/** Parent of all visuals (static: no per-frame offsets). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> VisualRoot;

	// --- Tuning ------------------------------------------------------------------------------
	/** Passive crescent: tight, calm, follows the Shell heading. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Motion")
	FSubDroneMotionProfile FormationMotion;

	/** Active working position: looser hover, more inertia against Shell turns. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Motion")
	FSubDroneMotionProfile DeployedMotion;

	/** Half-life of the Formation <-> Deployed blend. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Motion", meta = (ClampMin = "0.02", Units = "s"))
	float DeployTransitionHalfLife = 0.3f;

	/** Swoop height of the transition arc (makes the state change readable). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Motion", meta = (Units = "cm"))
	float DeployArcHeight = 45.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Motion", meta = (ClampMin = "100", Units = "cm"))
	float TeleportDistance = 6000.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Motion", meta = (ClampMin = "10", Units = "CentimetersPerSecond"))
	float MaxRelativeSpeed = 2500.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Motion", meta = (ClampMin = "0", ClampMax = "1"))
	float VelocityFeedForward = 1.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Motion", meta = (ClampMin = "0", Units = "cm"))
	float SurfaceClearance = 60.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Dock", meta = (ClampMin = "0.02", Units = "s"))
	float DockingHalfLife = 0.22f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Dock", meta = (ClampMin = "1", Units = "cm"))
	float DockSnapDistance = 35.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Dock", meta = (ClampMin = "0", Units = "s"))
	float DockSettleHalfLife = 0.08f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Dock", meta = (Units = "CentimetersPerSecond"))
	float UndockKickSpeed = 300.f;

	// --- Unstuck --------------------------------------------------------------------------
	/**
	 * Keep the goal on the Shell's side of walls: a sphere trace Shell -> slot clips the slot at the
	 * first obstacle, so a rock between the Shell and the slot never becomes a wall the drone presses into.
	 */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Unstuck")
	bool bClipGoalToShellVisibility = true;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Unstuck")
	bool bEnableUnstuck = true;

	/** Blocked and moving less than StuckProgressRatio of the intended step for this long -> phase. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Unstuck", meta = (ClampMin = "0.05", Units = "s"))
	float StuckTimeToPhase = 0.5f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Unstuck", meta = (ClampMin = "0.01", ClampMax = "1"))
	float StuckProgressRatio = 0.35f;

	/** Closer than this to the goal is never "stuck". */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Unstuck", meta = (ClampMin = "0", Units = "cm"))
	float StuckGoalTolerance = 90.f;

	/** Far behind (no clear path) for this long -> phase, even without a blocking contact. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Unstuck", meta = (ClampMin = "0.1", Units = "s"))
	float LostTimeToPhase = 1.5f;

	/** Glide speed relative to the Shell while phasing through an obstacle. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Unstuck", meta = (ClampMin = "50", Units = "CentimetersPerSecond"))
	float PhaseSpeed = 1500.f;

	/** Still phasing after this long -> rescue teleport to a free point next to the Shell. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Unstuck", meta = (ClampMin = "0.1", Units = "s"))
	float MaxPhaseTime = 2.5f;

private:
	void SetMobilityState(ESubDroneMobilityState NewState);
	void UpdateHostFrame(float Dt, const FSubDroneMotionProfile& Profile);
	void TickDocked(float Dt);
	void TickFree(float Dt, const FSubDroneMotionProfile& Profile);
	void TickDocking(float Dt);
	void MoveKinematic(const FVector& Goal, const FVector& GoalVel, float HalfLife, float Dt, bool bApplyCeiling, const FQuat& FacingTarget, float FacingHalfLife);
	float GetCachedWaterSurfaceZ(const FVector& At, float Dt);
	void AttachToDock();
	void DetachFromDock();

	// Unstuck helpers (same object type / responses as the movement sweep).
	FCollisionQueryParams MakeUnstuckQueryParams() const;
	bool IsBlockedAt(const FVector& Location) const;
	bool SweepBlocked(const FVector& From, const FVector& To, FHitResult& OutHit) const;
	FVector ClipGoalToShell(const FVector& Goal) const;
	FVector FindRescuePoint(const FVector& PreferredGoal) const;
	void SetPhasing(bool bNewPhasing);
	void RescueTeleport(const FVector& PreferredGoal);
	void UpdateStuckWatchdog(const FVector& OldPos, const FVector& IntendedPos, bool bBlocked, const FVector& Goal, float Dt);
	void UpdatePhasing(const FVector& Goal, float Dt);

	TWeakObjectPtr<USubDroneBayComponent> Bay;
	TWeakObjectPtr<APawn> HostPawn;
	int32 SlotIndex = INDEX_NONE;

	ESubDroneMobilityState MobilityState = ESubDroneMobilityState::Formation;
	float MobilityStateTime = 0.f;
	float DeployBlend = 0.f;
	bool bDeployAfterResupply = false;
	bool bDockSettled = false;

	FVector Velocity = FVector::ZeroVector;
	FQuat FilteredHostFrame = FQuat::Identity;

	float WaterCacheTimer = 0.f;
	float CachedWaterZ = 0.f;
	FVector LastWaterQueryPos = FVector::ZeroVector;
	bool bHasWaterCache = false;

	float BobTime = 0.f;
	float BobSeed = 0.f;

	// Unstuck state
	bool bPhasing = false;
	float StuckTime = 0.f;
	float LostTime = 0.f;
	float PhaseTime = 0.f;
	float PhaseCheckTimer = 0.f;
	float LostCheckTimer = 0.f;
	bool bLastPathClear = true;
};
