#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Components/BoxComponent.h"
#include "AOS_DK/Enemies/Reaper/AOS_HazardReceiver.h"
#include "AOS_AIObstacleTrigger.generated.h"

class UNavAreaBase;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

/** Box that exposes the (protected in UE 5.7) shape nav-area override: the pool volume doubles as a nav modifier. */
UCLASS(ClassGroup = (AOS_DK), meta = (BlueprintSpawnableComponent))
class AOS_DK_API UAOS_BrineVolumeComponent : public UBoxComponent
{
	GENERATED_BODY()

public:
	/** Sets the nav area exported by this (dynamic obstacle) box. */
	void SetBrineArea(TSubclassOf<UNavAreaBase> InAreaClass)
	{
		bUseSystemDefaultObstacleAreaClass = false;
		AreaClassOverride = InAreaClass;
	}
};

/**
 * "Heap Brine Pool": a floor volume that hinders only actors implementing IAOS_HazardReceiver (the OOM Reaper).
 * Shell-1 (AShellPawn) is hermetically sealed and ignored. The root box doubles as a nav modifier (UAOS_NavArea_Brine).
 * Requires Project Settings > Navigation Mesh > Runtime Generation = Dynamic Modifiers Only (or Dynamic).
 */
UCLASS(Blueprintable)
class AOS_DK_API AAOS_AIObstacleTrigger : public AActor
{
	GENERATED_BODY()

public:
	AAOS_AIObstacleTrigger();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	/** Master switch. Off: every receiver is released and the nav area reverts to default. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Hazard|Brine")
	void SetHazardActive(bool bNewActive);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Hazard|Brine")
	bool IsHazardActive() const { return bActive; }

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UAOS_BrineVolumeComponent> TriggerVolume;

	/** Flat pool surface, Dracula Purple tint. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Surface;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Hazard|Brine")
	bool bActive = true;

	/** Effects applied on entry: speed -60 %, sight halved, dodge x0.25, decoy regeneration paused. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Hazard|Brine")
	FAOSHazardParams HazardData;

	/** Surface height above the actor origin (floor level), cm. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Hazard|Brine|Visual", meta = (Units = "cm"))
	float SurfaceHeight = 2.f;

	/** Base material exposing a "Color" vector parameter. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Hazard|Brine|Visual")
	TObjectPtr<UMaterialInterface> SurfaceMaterial;

	/** #BD93F9 (MS_Status). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Hazard|Brine|Visual")
	FColor SurfaceTint = FColor(0xBD, 0x93, 0xF9);

protected:
	UFUNCTION()
	void OnOverlapBegin(UPrimitiveComponent* OverlappedComp, AActor* OtherActor, UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

	UFUNCTION()
	void OnOverlapEnd(UPrimitiveComponent* OverlappedComp, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

private:
	void EnterReceiver(AActor* Other);
	void ReleaseAllReceivers();

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> SurfaceMID;

	TSet<TWeakObjectPtr<AActor>> Receivers;
};
