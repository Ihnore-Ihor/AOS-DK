#include "ShellPawn.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Camera/CameraComponent.h"
#include "BuoyancyComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "InputMappingContext.h"
#include "AOS_DK/Player/AdminCharacter.h"
#include "AOS_DK/Player/PlayerController/AdminPlayerController.h"

class AAdminPlayerController;

AShellPawn::AShellPawn()
{
	PrimaryActorTick.bCanEverTick = true;

	//~ Initialization
	BoxRoot = CreateDefaultSubobject<UBoxComponent>(TEXT("BoxRoot"));
	RootComponent = BoxRoot;
	BoxRoot->SetSimulatePhysics(true);
	BoxRoot->SetLinearDamping(5.f);
	BoxRoot->SetAngularDamping(8.f);
	BoxRoot->SetCollisionProfileName(TEXT("PhysicsActor"));

	ShellMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ShellMesh"));
	ShellMesh->SetupAttachment(BoxRoot);
	ShellMesh->SetCollisionProfileName(TEXT("NoCollision"));

	FPCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FPCamera"));
	FPCamera->SetupAttachment(BoxRoot);
	FPCamera->bUsePawnControlRotation = false; 

	BuoyancyComponent = CreateDefaultSubobject<UBuoyancyComponent>(TEXT("BuoyancyComponent"));
}

void AShellPawn::BeginPlay()
{
	Super::BeginPlay();

	BoxRoot->OnComponentBeginOverlap.AddDynamic(this, &AShellPawn::OnOverlapBegin);
	BoxRoot->OnComponentEndOverlap.AddDynamic(this, &AShellPawn::OnOverlapEnd);
}

void AShellPawn::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	UpdateGyrostabilization(DeltaTime);
}

void AShellPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			if (SubMappingContext)
			{
				Subsystem->AddMappingContext(SubMappingContext, 1); 
			}
		}
	}

	if (UEnhancedInputComponent* EnhancedInputComp = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		EnhancedInputComp->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AShellPawn::ApplyThrust);
		EnhancedInputComp->BindAction(RotateAction, ETriggerEvent::Triggered, this, &AShellPawn::ApplyRotation);
		EnhancedInputComp->BindAction(InteractAction, ETriggerEvent::Started, this, &AShellPawn::HandleInteract);
	}
}

//~ Interaction
void AShellPawn::Interact_Implementation(AActor* InstigatorActor)
{
	if (AAdminCharacter* Admin = Cast<AAdminCharacter>(InstigatorActor))
	{
		if (AController* PC = Admin->GetController())
		{
			PC->Possess(this);
			
			Admin->AttachToComponent(BoxRoot, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
			Admin->SetActorHiddenInGame(true);
			Admin->SetActorEnableCollision(false);
		}
	}
}

void AShellPawn::HandleInteract()
{
	if (OverlapBuffer.IsEmpty()) return;

	AActor* TargetActor = OverlapBuffer.Last();
	if (TargetActor && TargetActor->Implements<UInteractable>())
	{
		IInteractable::Execute_Interact(TargetActor, this);
	}
}

void AShellPawn::OnOverlapBegin(UPrimitiveComponent* OverlappedComp, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	if (OtherActor && OtherActor != this)
	{
		OverlapBuffer.AddUnique(OtherActor);

		if (OtherActor->Implements<UInteractable>())
		{
			if (AAdminPlayerController* PC = Cast<AAdminPlayerController>(GetController()))
			{
				PC->ShowHint();
			}
		}
	}
}

void AShellPawn::OnOverlapEnd(UPrimitiveComponent* OverlappedComp, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex)
{
	if (OtherActor)
	{
		OverlapBuffer.Remove(OtherActor);

		if (OtherActor->Implements<UInteractable>())
		{
			if (AAdminPlayerController* PC = Cast<AAdminPlayerController>(GetController()))
			{
				PC->HideHint();
			}
		}
	}
}

//~ Movement
void AShellPawn::ApplyThrust(const FInputActionValue& Value)
{
	FVector MovementInput = Value.Get<FVector>();
	FVector Force = BoxRoot->GetComponentTransform().TransformVector(MovementInput * ThrustMultiplier);
	
	BoxRoot->AddForce(Force, NAME_None, true);
	TimeSinceLastInput = 0.f;
}

void AShellPawn::ApplyRotation(const FInputActionValue& Value)
{
	FVector RotationInput = Value.Get<FVector>();
	FVector Torque = BoxRoot->GetComponentTransform().TransformVector(RotationInput * TorqueMultiplier);
	
	BoxRoot->AddTorqueInDegrees(Torque, NAME_None, true);
	TimeSinceLastInput = 0.f;
}

void AShellPawn::UpdateGyrostabilization(float DeltaTime)
{
	TimeSinceLastInput += DeltaTime;

	if (TimeSinceLastInput >= 2.0f)
	{
		FRotator CurrentRot = BoxRoot->GetComponentRotation();
		FRotator TargetRot = FRotator(0.f, CurrentRot.Yaw, 0.f);
		FRotator NewRot = FMath::RInterpTo(CurrentRot, TargetRot, DeltaTime, 2.f);
		
		BoxRoot->SetWorldRotation(NewRot);
	}
}