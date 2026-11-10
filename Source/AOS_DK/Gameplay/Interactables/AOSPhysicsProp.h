#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSPhysicsProp.generated.h"

class UStaticMeshComponent;
class UAOSFluidPhysicsComponent;
class UPhysicalMaterial;

/**
 * Movable physical prop driven by UAOSFluidPhysicsComponent (Newtonian model).
 * The mesh is the simulating root; the fluid component adds buoyancy, drag and mass-scaled wave forcing.
 * Configure per Blueprint: mesh, FluidPhysics->MassOverrideKg, FluidPhysics->BuoyancyFactor.
 *  - BP_Phys_CargoPod:     1500 kg, B 0.4  -> sinks, rests on its skids, wave coupling C(m) = 0.
 *  - BP_Phys_BuoyantDrum:    45 kg, B 3.5  -> rises, floats ~29 % submerged, full wave coupling.
 */
UCLASS(Blueprintable, meta = (DisplayName = "AOS Physics Prop"))
class AOS_DK_API AAOSPhysicsProp : public AActor
{
	GENERATED_BODY()

public:
	AAOSPhysicsProp();

	virtual void OnConstruction(const FTransform& Transform) override;

	UFUNCTION(BlueprintPure, Category = "AOS|Interactables")
	UStaticMeshComponent* GetMesh() const { return Mesh; }

	UFUNCTION(BlueprintPure, Category = "AOS|Interactables")
	UAOSFluidPhysicsComponent* GetFluidPhysics() const { return FluidPhysics; }

protected:
	/** Simulating root body (PhysicsActor profile). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UAOSFluidPhysicsComponent> FluidPhysics;

	/** Optional physical material for the contact patch (e.g. low-friction skids so the Shell can push the pod). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Interactables")
	TObjectPtr<UPhysicalMaterial> ContactMaterial;
};
