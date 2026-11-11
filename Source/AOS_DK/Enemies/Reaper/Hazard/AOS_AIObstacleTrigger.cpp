#include "AOS_AIObstacleTrigger.h"
#include "AOS_NavArea_Brine.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "NavAreas/NavArea_Default.h"
#include "NavigationSystem.h"
#include "UObject/ConstructorHelpers.h"

AAOS_AIObstacleTrigger::AAOS_AIObstacleTrigger()
{
	PrimaryActorTick.bCanEverTick = false;

	TriggerVolume = CreateDefaultSubobject<UAOS_BrineVolumeComponent>(TEXT("TriggerVolume"));
	RootComponent = TriggerVolume;
	TriggerVolume->SetBoxExtent(FVector(500.f, 400.f, 120.f)); // 10 x 8 m pool
	TriggerVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	TriggerVolume->SetCollisionObjectType(ECC_WorldDynamic);
	TriggerVolume->SetCollisionResponseToAllChannels(ECR_Ignore);
	TriggerVolume->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
	TriggerVolume->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Overlap);
	TriggerVolume->SetGenerateOverlapEvents(true);
	TriggerVolume->SetCanEverAffectNavigation(true);
	TriggerVolume->bDynamicObstacle = true; // exported as a nav area modifier (nav area), not as geometry
	TriggerVolume->SetBrineArea(UAOS_NavArea_Brine::StaticClass());

	Surface = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Surface"));
	Surface->SetupAttachment(TriggerVolume);
	Surface->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
	Surface->SetCanEverAffectNavigation(false);
	Surface->SetCastShadow(false);
	Surface->SetRelativeLocation(FVector(0.f, 0.f, SurfaceHeight));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneMesh(TEXT("/Engine/BasicShapes/Plane.Plane"));
	if (PlaneMesh.Succeeded())
	{
		Surface->SetStaticMesh(PlaneMesh.Object);
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BaseMat(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	if (BaseMat.Succeeded())
	{
		SurfaceMaterial = BaseMat.Object;
	}
}

void AAOS_AIObstacleTrigger::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	// Engine plane is 100 x 100 cm: scale it to the box footprint.
	const FVector Extent = TriggerVolume->GetUnscaledBoxExtent();
	Surface->SetRelativeLocation(FVector(0.f, 0.f, SurfaceHeight));
	Surface->SetRelativeScale3D(FVector(Extent.X / 50.f, Extent.Y / 50.f, 1.f));

	if (SurfaceMaterial)
	{
		SurfaceMID = UMaterialInstanceDynamic::Create(SurfaceMaterial, this);
		if (SurfaceMID)
		{
			SurfaceMID->SetVectorParameterValue(TEXT("Color"), FLinearColor::FromSRGBColor(SurfaceTint));
			Surface->SetMaterial(0, SurfaceMID);
		}
	}
}

void AAOS_AIObstacleTrigger::BeginPlay()
{
	Super::BeginPlay();

	TriggerVolume->OnComponentBeginOverlap.AddDynamic(this, &AAOS_AIObstacleTrigger::OnOverlapBegin);
	TriggerVolume->OnComponentEndOverlap.AddDynamic(this, &AAOS_AIObstacleTrigger::OnOverlapEnd);

	if (!bActive)
	{
		bActive = true; // force a clean transition through SetHazardActive
		SetHazardActive(false);
		return;
	}

	// Receivers already standing in the pool at spawn.
	TArray<AActor*> Initial;
	TriggerVolume->GetOverlappingActors(Initial);
	for (AActor* Other : Initial)
	{
		EnterReceiver(Other);
	}
}

void AAOS_AIObstacleTrigger::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	ReleaseAllReceivers();
	Super::EndPlay(EndPlayReason);
}

void AAOS_AIObstacleTrigger::EnterReceiver(AActor* Other)
{
	if (!bActive || !IsValid(Other) || Other->IsA<AShellPawn>()) // the sub is sealed: immune
	{
		return;
	}
	if (!Other->Implements<UAOS_HazardReceiver>())
	{
		return;
	}
	bool bAlreadyIn = false;
	Receivers.Add(Other, &bAlreadyIn);
	if (!bAlreadyIn)
	{
		IAOS_HazardReceiver::Execute_EnterHazard(Other, this, HazardData);
	}
}

void AAOS_AIObstacleTrigger::ReleaseAllReceivers()
{
	const TSet<TWeakObjectPtr<AActor>> Snapshot = MoveTemp(Receivers);
	Receivers.Reset();
	for (const TWeakObjectPtr<AActor>& Weak : Snapshot)
	{
		if (AActor* Other = Weak.Get())
		{
			IAOS_HazardReceiver::Execute_ExitHazard(Other, this);
		}
	}
}

void AAOS_AIObstacleTrigger::OnOverlapBegin(UPrimitiveComponent* /*OverlappedComp*/, AActor* OtherActor, UPrimitiveComponent* OtherComp,
	int32 /*OtherBodyIndex*/, bool /*bFromSweep*/, const FHitResult& /*SweepResult*/)
{
	// Count the root capsule only, so a receiver with several overlapping components enters once.
	if (!OtherActor || OtherComp != OtherActor->GetRootComponent())
	{
		return;
	}
	EnterReceiver(OtherActor);
}

void AAOS_AIObstacleTrigger::OnOverlapEnd(UPrimitiveComponent* /*OverlappedComp*/, AActor* OtherActor, UPrimitiveComponent* OtherComp,
	int32 /*OtherBodyIndex*/)
{
	if (!OtherActor || OtherComp != OtherActor->GetRootComponent())
	{
		return;
	}
	if (Receivers.Remove(OtherActor) > 0)
	{
		IAOS_HazardReceiver::Execute_ExitHazard(OtherActor, this);
	}
}

void AAOS_AIObstacleTrigger::SetHazardActive(bool bNewActive)
{
	if (bActive == bNewActive)
	{
		return;
	}
	bActive = bNewActive;

	TriggerVolume->SetBrineArea(bActive ? TSubclassOf<UNavAreaBase>(UAOS_NavArea_Brine::StaticClass())
										: TSubclassOf<UNavAreaBase>(UNavArea_Default::StaticClass()));
	FNavigationSystem::UpdateComponentData(*TriggerVolume);

	if (bActive)
	{
		TArray<AActor*> Inside;
		TriggerVolume->GetOverlappingActors(Inside);
		for (AActor* Other : Inside)
		{
			EnterReceiver(Other);
		}
	}
	else
	{
		ReleaseAllReceivers();
	}
}
