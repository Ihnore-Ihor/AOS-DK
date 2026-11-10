#include "AOSPhysicsProp.h"
#include "Components/StaticMeshComponent.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "AOS_DK/Environment/Physics/AOSFluidPhysicsComponent.h"

AAOSPhysicsProp::AAOSPhysicsProp()
{
	PrimaryActorTick.bCanEverTick = false;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	SetRootComponent(Mesh);
	Mesh->SetMobility(EComponentMobility::Movable);
	Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));
	Mesh->SetSimulatePhysics(true);
	Mesh->SetEnableGravity(true);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->BodyInstance.bUseCCD = false;
	Mesh->SetCanEverAffectNavigation(false);

	FluidPhysics = CreateDefaultSubobject<UAOSFluidPhysicsComponent>(TEXT("FluidPhysics"));
	FluidPhysics->ResponseModel = EAOSFluidResponseModel::Newtonian;
	FluidPhysics->bAutoSimulate = true;
}

void AAOSPhysicsProp::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	if (Mesh && ContactMaterial)
	{
		Mesh->SetPhysMaterialOverride(ContactMaterial);
	}
}
