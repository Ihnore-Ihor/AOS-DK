#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"

#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBase.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "EnhancedInputComponent.h"
#include "Engine/World.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "UObject/StructOnScope.h"

USubDroneBayComponent::USubDroneBayComponent()
{
	PrimaryComponentTick.bCanEverTick = false;

	FSubDroneSlot Right;
	Right.DockTransform = FTransform(FVector(-130.f, 69.f, 69.f));
	Right.CombatOffset = FVector(780.f, 150.f, 10.f);

	FSubDroneSlot Left;
	Left.DockTransform = FTransform(FVector(-130.f, -69.f, 69.f));
	Left.CombatOffset = FVector(780.f, -150.f, 10.f);

	Slots = { Right, Left };
}

void USubDroneBayComponent::BeginPlay()
{
	Super::BeginPlay();

	if (APawn* Host = GetHostPawn())
	{
		Host->ReceiveControllerChangedDelegate.AddDynamic(this, &USubDroneBayComponent::HandleHostControllerChanged);
	}

	if (GetOwner() && GetOwner()->HasAuthority())
	{
		SpawnDrones();
	}
}

void USubDroneBayComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	for (ASubDroneBase* Drone : Drones)
	{
		if (IsValid(Drone))
		{
			Drone->Destroy();
		}
	}
	Drones.Reset();
	Super::EndPlay(EndPlayReason);
}

void USubDroneBayComponent::SpawnDrones()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	Drones.SetNum(Slots.Num());
	for (int32 Index = 0; Index < Slots.Num(); ++Index)
	{
		if (!Slots[Index].DroneClass)
		{
			continue;
		}

		// Drones are born in their formation slot - visible from the first frame.
		const USceneComponent* Root = GetHostRoot();
		const FTransform HostXf = Root ? Root->GetComponentTransform() : FTransform::Identity;
		const FTransform SpawnXf(HostXf.GetRotation(), HostXf.TransformPosition(GetFormationOffset(Index)));
		ASubDroneBase* Drone = World->SpawnActorDeferred<ASubDroneBase>(
			Slots[Index].DroneClass, SpawnXf, GetOwner(), GetHostPawn(), ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
		if (!Drone)
		{
			continue;
		}

		Drone->InitializeDrone(this, Index);
		Drone->FinishSpawning(SpawnXf);
		Drones[Index] = Drone;
		OnDroneSpawned.Broadcast(Drone, Index);

		if (Slots[Index].bDeployOnBeginPlay)
		{
			Drone->RequestDeploy();
		}
	}
}

// ------------------------------------------------------------------------------------- input
void USubDroneBayComponent::BindInput(UEnhancedInputComponent* InputComponent)
{
	if (!InputComponent)
	{
		return;
	}
	if (DroneToggleAction)
	{
		InputComponent->BindAction(DroneToggleAction, ETriggerEvent::Started, this, &USubDroneBayComponent::HandleToggleInput);
	}
	if (DroneAttackAction)
	{
		InputComponent->BindAction(DroneAttackAction, ETriggerEvent::Started, this, &USubDroneBayComponent::HandleAttackStarted);
		InputComponent->BindAction(DroneAttackAction, ETriggerEvent::Completed, this, &USubDroneBayComponent::HandleAttackCompleted);
		InputComponent->BindAction(DroneAttackAction, ETriggerEvent::Canceled, this, &USubDroneBayComponent::HandleAttackCompleted);
	}
}

void USubDroneBayComponent::HandleToggleInput()
{
	ToggleDrones();
}

void USubDroneBayComponent::HandleAttackStarted()
{
	SetPrimaryActionHeld(true);
}

void USubDroneBayComponent::HandleAttackCompleted()
{
	SetPrimaryActionHeld(false);
}

void USubDroneBayComponent::HandleHostControllerChanged(APawn* Pawn, AController* OldController, AController* NewController)
{
	// Leaving the Shell must never leave a drone "trigger held".
	if (!Cast<APlayerController>(NewController))
	{
		SetPrimaryActionHeld(false);
	}
}

void USubDroneBayComponent::ToggleDrones()
{
	bool bAnyDeployed = false;
	for (const ASubDroneBase* Drone : Drones)
	{
		bAnyDeployed |= IsValid(Drone) && Drone->IsDeployed();
	}
	bAnyDeployed ? RecallAllDrones() : DeployAllDrones();
}

void USubDroneBayComponent::DeployAllDrones()
{
	for (ASubDroneBase* Drone : Drones)
	{
		if (IsValid(Drone))
		{
			Drone->RequestDeploy();
		}
	}
}

void USubDroneBayComponent::RecallAllDrones()
{
	for (ASubDroneBase* Drone : Drones)
	{
		if (IsValid(Drone))
		{
			Drone->RequestRecall();
		}
	}
}

void USubDroneBayComponent::SetPrimaryActionHeld(bool bHeld)
{
	if (bPrimaryHeld == bHeld)
	{
		return;
	}
	bPrimaryHeld = bHeld;

	for (ASubDroneBase* Drone : Drones)
	{
		if (!IsValid(Drone))
		{
			continue;
		}
		if (bHeld)
		{
			// Strict filter: LMB never deploys a drone. Only drones already moved to their combat
			// position with R react; drones in Formation / Docking / Docked ignore the press completely.
			if (Drone->AcceptsPrimaryAction())
			{
				Drone->StartPrimaryAction();
			}
		}
		else
		{
			Drone->StopPrimaryAction(); // releasing is always safe and never changes the mobility state
		}
	}
}

ASubDroneBase* USubDroneBayComponent::GetDrone(int32 SlotIndex) const
{
	return Drones.IsValidIndex(SlotIndex) ? Drones[SlotIndex].Get() : nullptr;
}

// ---------------------------------------------------------------------------------- services
APawn* USubDroneBayComponent::GetHostPawn() const
{
	return Cast<APawn>(GetOwner());
}

USceneComponent* USubDroneBayComponent::GetHostRoot() const
{
	return GetOwner() ? GetOwner()->GetRootComponent() : nullptr;
}

FVector USubDroneBayComponent::GetHostVelocity() const
{
	// Root is the simulated BoxRoot -> physics linear velocity.
	return GetOwner() ? GetOwner()->GetVelocity() : FVector::ZeroVector;
}

FTransform USubDroneBayComponent::GetDockRelativeTransform(int32 SlotIndex) const
{
	return Slots.IsValidIndex(SlotIndex) ? Slots[SlotIndex].DockTransform : FTransform::Identity;
}

FTransform USubDroneBayComponent::GetDockWorldTransform(int32 SlotIndex) const
{
	const USceneComponent* Root = GetHostRoot();
	const FTransform HostXf = Root ? Root->GetComponentTransform() : FTransform::Identity;
	return GetDockRelativeTransform(SlotIndex) * HostXf;
}

FVector USubDroneBayComponent::GetFormationOffset(int32 SlotIndex) const
{
	// Crescent (like the legacy BP_SubDrone): slots spread over FormationArcDegrees, slot 0 on the right.
	const int32 Num = FMath::Max(Slots.Num(), 1);
	const float AngleDeg = Num > 1 ? FormationArcDegrees * 0.5f - SlotIndex * (FormationArcDegrees / (Num - 1)) : 0.f;
	const float Rad = FMath::DegreesToRadians(AngleDeg);
	return FormationCenter + FVector(FormationRadius * FMath::Cos(Rad), FormationRadius * FMath::Sin(Rad), FormationHeight);
}

FVector USubDroneBayComponent::GetCombatOffset(int32 SlotIndex) const
{
	return Slots.IsValidIndex(SlotIndex) ? Slots[SlotIndex].CombatOffset : GetFormationOffset(SlotIndex);
}

bool USubDroneBayComponent::ComputeAim(FVector& OutPoint, AActor*& OutActor) const
{
	OutActor = nullptr;
	APawn* Host = GetHostPawn();
	UWorld* World = GetWorld();
	if (!Host || !World)
	{
		OutPoint = FVector::ZeroVector;
		return false;
	}

	FVector ViewLoc;
	FRotator ViewRot;
	if (AController* Controller = Host->GetController())
	{
		Controller->GetPlayerViewPoint(ViewLoc, ViewRot); // PlayerController -> active camera (FPCamera)
	}
	else
	{
		Host->GetActorEyesViewPoint(ViewLoc, ViewRot);
	}

	const FVector End = ViewLoc + ViewRot.Vector() * AimTraceDistance;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SubDroneAim), false, Host);
	for (const ASubDroneBase* Drone : Drones)
	{
		Params.AddIgnoredActor(Drone);
	}

	FHitResult Hit;
	if (World->LineTraceSingleByChannel(Hit, ViewLoc, End, AimTraceChannel, Params))
	{
		OutPoint = Hit.ImpactPoint;
		OutActor = Hit.GetActor();
		return true;
	}
	OutPoint = End;
	return false;
}

float USubDroneBayComponent::QueryWaterSurfaceZ(const FVector& Location) const
{
	const UWorld* World = GetWorld();
	if (AGameModeBase* GameMode = World ? World->GetAuthGameMode() : nullptr)
	{
		if (UFunction* Fn = GameMode->FindFunction(WaterSurfaceFunctionName))
		{
			// Generic reflection call: first FVector input = location, first numeric output = surface Z.
			FStructOnScope Params(Fn);
			uint8* Memory = Params.GetStructMemory();
			FNumericProperty* OutProp = nullptr;
			for (TFieldIterator<FProperty> It(Fn); It && It->HasAnyPropertyFlags(CPF_Parm); ++It)
			{
				FProperty* Prop = *It;
				if (Prop->HasAnyPropertyFlags(CPF_OutParm | CPF_ReturnParm))
				{
					OutProp = OutProp ? OutProp : CastField<FNumericProperty>(Prop);
				}
				else if (const FStructProperty* StructProp = CastField<FStructProperty>(Prop))
				{
					if (StructProp->Struct == TBaseStructure<FVector>::Get())
					{
						*StructProp->ContainerPtrToValuePtr<FVector>(Memory) = Location;
					}
				}
			}
			if (OutProp && OutProp->IsFloatingPoint())
			{
				GameMode->ProcessEvent(Fn, Memory);
				return static_cast<float>(OutProp->GetFloatingPointPropertyValue(OutProp->ContainerPtrToValuePtr<void>(Memory)));
			}
		}
	}

	if (const AShellPawn* Shell = Cast<AShellPawn>(GetOwner()))
	{
		return Shell->GetOceanSurfaceZ();
	}
	return FallbackSurfaceZ;
}

int32 USubDroneBayComponent::RequestMunitionResupply_Implementation(ASubDroneBase* Drone, int32 Requested)
{
	return FMath::Max(0, Requested);
}
