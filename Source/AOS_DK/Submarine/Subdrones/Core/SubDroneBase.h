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
};
