#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOS_DK/Enemies/Daemon/AOS_EnemyDaemon.h"
#include "AOS_EnemySpawner.generated.h"

class USplineComponent;

/** Where the patrol route of the spawned daemons comes from. */
UENUM(BlueprintType)
enum class EAOSPatrolRouteMode : uint8
{
	/** Hand-edited spline of the spawner (drag points / Alt+drag to add in the viewport). */
	Spline        UMETA(DisplayName = "Edited Spline"),
	/** Closed ring of PatrolRadius around the spawner, gentle vertical wave (procedural). */
	GeneratedRing UMETA(DisplayName = "Generated Ring"),
	/** Local PatrolPoints (3D widgets) converted into the spline. */
	PatrolPoints  UMETA(DisplayName = "Patrol Points")
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnSpawnerDaemonSpawned, AAOS_EnemySpawner*, Spawner, AAOS_EnemyDaemon*, Daemon);

/**
 * Sector spawner of system daemons (Task 1). Keeps up to MaxActiveEnemies alive in its sector,
 * spawning one every SpawnInterval, spaced evenly along its closed patrol spline. Every spawned
 * daemon patrols that spline (deterministic route, no AI). Attack modes can alternate.
 */
UCLASS()
class AOS_DK_API AAOS_EnemySpawner : public AActor
{
	GENERATED_BODY()

public:
	AAOS_EnemySpawner();

	virtual void OnConstruction(const FTransform& Transform) override;

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Spawner")
	AAOS_EnemyDaemon* SpawnDaemon();

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Spawner")
	void SetSpawningEnabled(bool bEnabled);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Spawner")
	int32 GetActiveCount() const;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Spawner")
	USplineComponent* GetPatrolSpline() const { return PatrolSpline; }

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Spawner")
	FOnSpawnerDaemonSpawned OnDaemonSpawned;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> SceneRoot;

	/** Closed patrol route shared by the daemons of this sector. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USplineComponent> PatrolSpline;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner")
	TSubclassOf<AAOS_EnemyDaemon> EnemyClass;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner", meta = (ClampMin = "0", ClampMax = "32"))
	int32 MaxActiveEnemies = 3;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner", meta = (ClampMin = "0.1", Units = "s"))
	float SpawnInterval = 6.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner", meta = (ClampMin = "0", Units = "s"))
	float InitialDelay = 1.f;

	/** 0 = unlimited respawns. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner", meta = (ClampMin = "0"))
	int32 TotalSpawnBudget = 0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner")
	bool bSpawnOnBeginPlay = true;

	/** Spawn only while the player pawn is closer than this (0 = always). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner", meta = (ClampMin = "0", Units = "cm"))
	float ActivationRadius = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner|Combat")
	EDaemonAttackMode DefaultAttackMode = EDaemonAttackMode::Lunge;

	/** Every second daemon uses the other attack mode (Lunge / Pulse). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner|Combat")
	bool bAlternateAttackModes = true;

	// --- Route ---------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner|Route")
	EAOSPatrolRouteMode RouteMode = EAOSPatrolRouteMode::GeneratedRing;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner|Route", meta = (ClampMin = "100", Units = "cm", EditCondition = "RouteMode == EAOSPatrolRouteMode::GeneratedRing"))
	float PatrolRadius = 1400.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner|Route", meta = (ClampMin = "3", ClampMax = "32", EditCondition = "RouteMode == EAOSPatrolRouteMode::GeneratedRing"))
	int32 RingPointCount = 8;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner|Route", meta = (Units = "cm", EditCondition = "RouteMode == EAOSPatrolRouteMode::GeneratedRing"))
	float RingVerticalWave = 180.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Spawner|Route", meta = (MakeEditWidget = true, EditCondition = "RouteMode == EAOSPatrolRouteMode::PatrolPoints"))
	TArray<FVector> PatrolPoints;

private:
	void RebuildRoute();
	void TrySpawn();
	bool IsActivated() const;

	UFUNCTION()
	void HandleDaemonDestroyed(AAOS_EnemyDaemon* Daemon);

	UPROPERTY(Transient)
	TArray<TObjectPtr<AAOS_EnemyDaemon>> ActiveDaemons;

	FTimerHandle SpawnTimer;
	int32 SpawnSerial = 0;
	bool bSpawningEnabled = true;
};
