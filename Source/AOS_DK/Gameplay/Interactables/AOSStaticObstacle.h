#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSStaticObstacle.generated.h"

class UStaticMeshComponent;

/**
 * Rigid static obstacle (bulkhead slab / gate). BlockAll, static mobility, simple collision only.
 * The player has to navigate around it. BP_Obstacle_Bulkhead derives from this class.
 */
UCLASS(Blueprintable, meta = (DisplayName = "AOS Static Obstacle"))
class AOS_DK_API AAOSStaticObstacle : public AActor
{
	GENERATED_BODY()

public:
	AAOSStaticObstacle();

	UFUNCTION(BlueprintPure, Category = "AOS|Interactables")
	UStaticMeshComponent* GetMesh() const { return Mesh; }

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Mesh;
};
