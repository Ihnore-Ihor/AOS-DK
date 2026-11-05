#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/EngineTypes.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneTypes.h"
#include "SubDroneBayComponent.generated.h"

class ASubDroneBase;
class UInputAction;
class UEnhancedInputComponent;
class AController;

/** One CPU core of the Shell's "Dual-Core" drone architecture. */
USTRUCT(BlueprintType)
struct FSubDroneSlot
{
	GENERATED_BODY()

	/** Module that runs in this slot (BP_SubDrone_Attacker, later Defender / Pathfinder ...). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Slot")
	TSubclassOf<ASubDroneBase> DroneClass;

	/** Hull socket used ONLY for physical resupply (relative to the Shell root, cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Slot")
	FTransform DockTransform;

	/** Working (Deployed) position in the filtered Shell frame: X forward, Y right, Z up (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Slot")
	FVector CombatOffset = FVector(780.f, 150.f, 10.f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Slot")
	bool bDeployOnBeginPlay = false;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnSubDroneSpawned, ASubDroneBase*, Drone, int32, SlotIndex);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FOnSubDroneReloadRequested, ASubDroneBase*, Drone, ESubDroneReloadResult, Result, float, EnergyCostPercent);

/**
 * Lives on the Shell (AShellPawn::DroneBay). Owns the drone processes, routes Shell input
 * (IA_Sub_DroneToggle / IA_Sub_DroneAttack / IA_Sub_DroneReload) and offers Shell-side services to
 * the drones: crescent formation, combat positions, dock sockets, aim ray, water surface, munition
 * gate, service-station link and the energy payment of manual reloads.
 * Never ticks.
 */
UCLASS(ClassGroup = (AOS_DK), meta = (BlueprintSpawnableComponent))
class AOS_DK_API USubDroneBayComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	USubDroneBayComponent();

	/** Called from AShellPawn::SetupPlayerInputComponent. */
	void BindInput(UEnhancedInputComponent* InputComponent);

	/** R: Formation <-> Deployed for every drone. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Drones")
	void ToggleDrones();

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Drones")
	void DeployAllDrones();

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Drones")
	void RecallAllDrones();

	/** Hold-to-fire: forwarded only to drones that accept it (Deployed via R); never deploys a drone. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Drones")
	void SetPrimaryActionHeld(bool bHeld);

	/**
	 * RMB: every module that can reload loads its next magazine from its internal reserve. Each started
	 * reload is paid once from the Shell core (blocked if the core cannot afford it). Broadcasts the result.
	 */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Drones")
	void RequestReload();

	/** A dock berth / service station links (or unlinks) the Shell: drones are rearmed in place. */
	void SetServiceStationLinked(UObject* Station, bool bLinked);

	/** The Shell is moored at a service station (dock): drone munitions are being replenished. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Drones")
	bool IsAtServiceStation() const;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Drones")
	ASubDroneBase* GetDrone(int32 SlotIndex) const;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Drones")
	int32 GetNumSlots() const { return Slots.Num(); }

	// --- Services for drones -------------------------------------------------------------
	APawn* GetHostPawn() const;
	USceneComponent* GetHostRoot() const;
	FVector GetHostVelocity() const;
	FTransform GetDockRelativeTransform(int32 SlotIndex) const;
	FTransform GetDockWorldTransform(int32 SlotIndex) const;
	/** Crescent formation slot (Shell frame). Slot 0 is on the right. */
	FVector GetFormationOffset(int32 SlotIndex) const;
	/** Working position when Deployed (Shell frame). */
	FVector GetCombatOffset(int32 SlotIndex) const;

	/** Player's aim: camera ray against the world. Returns true if something was hit. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Drones")
	bool ComputeAim(FVector& OutPoint, AActor*& OutActor) const;

	/**
	 * Water surface Z at Location: GameMode implementation of BPI_WaterSystem::GetWaterSurfaceHeight
	 * via reflection, then AShellPawn::OceanSurfaceZ, then FallbackSurfaceZ.
	 */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Water")
	float QueryWaterSurfaceZ(const FVector& Location) const;

	/**
	 * Munition gate for PHYSICAL resupply at the Shell. Default grants everything;
	 * the Shell RAM inventory overrides this later (C++ or Blueprint).
	 */
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AOS_DK|Drones")
	int32 RequestMunitionResupply(ASubDroneBase* Drone, int32 Requested);

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Drones")
	FOnSubDroneSpawned OnDroneSpawned;

	/** Result of every manual reload request (HUD terminal log, audio). */
	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Drones")
	FOnSubDroneReloadRequested OnReloadRequested;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	/** Dual-Core architecture: two active module slots by default (right / left). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Drones")
	TArray<FSubDroneSlot> Slots;

	/** Centre of the crescent in the Shell frame (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Formation")
	FVector FormationCenter = FVector(300.f, 0.f, 0.f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Formation", meta = (ClampMin = "0", Units = "cm"))
	float FormationRadius = 370.f;

	/** Total angular spread of the crescent across all slots. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Formation", meta = (ClampMin = "0", ClampMax = "180", Units = "Degrees"))
	float FormationArcDegrees = 56.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Formation", meta = (Units = "cm"))
	float FormationHeight = 95.f;

	/** IA_Sub_DroneToggle (R): Formation <-> Deployed. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> DroneToggleAction;

	/** IA_Sub_DroneAttack (LMB, hold): primary module action. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> DroneAttackAction;

	/** IA_Sub_DroneReload (RMB, press): load the next magazine from the drone reserve. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> DroneReloadAction;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Aim", meta = (Units = "cm"))
	float AimTraceDistance = 8000.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Aim")
	TEnumAsByte<ECollisionChannel> AimTraceChannel = ECC_Visibility;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Water")
	FName WaterSurfaceFunctionName = TEXT("GetWaterSurfaceHeight");

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Water", meta = (Units = "cm"))
	float FallbackSurfaceZ = 0.f;

private:
	void SpawnDrones();
	void HandleToggleInput();
	void HandleAttackStarted();
	void HandleAttackCompleted();
	void HandleReloadInput();

	UFUNCTION()
	void HandleHostControllerChanged(APawn* Pawn, AController* OldController, AController* NewController);

	UPROPERTY(Transient)
	TArray<TObjectPtr<ASubDroneBase>> Drones;

	bool bPrimaryHeld = false;

	/** Linked service stations (normally 0 or 1). */
	TArray<TWeakObjectPtr<UObject>> ServiceStations;
};
