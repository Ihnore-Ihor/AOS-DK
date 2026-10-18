#include "AdminCharacter.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "AOS_DK/Core/Interfaces/Interactions/Interactable.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Kismet/KismetSystemLibrary.h"
#include "PlayerController/AdminPlayerController.h"


// Sets default values
AAdminCharacter::AAdminCharacter()
{
	// Set this character to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;
	
	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = true;
	bUseControllerRotationRoll = false;
    
	FirstPersonMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FirstPersonMesh"));
	FirstPersonMesh->SetupAttachment(GetMesh());
    
	CameraComponent = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
	CameraComponent->SetupAttachment(FirstPersonMesh, FName("head"));
	
	//~ Input
	CameraComponent->bUsePawnControlRotation = true; 
}

// Called when the game starts or when spawned
void AAdminCharacter::BeginPlay()
{
	Super::BeginPlay();
}


// Called every frame
void AAdminCharacter::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
}

// Called to bind functionality to input
void AAdminCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	
	if (UEnhancedInputComponent* EnhancedInputComponent = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		EnhancedInputComponent->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AAdminCharacter::Move);
		EnhancedInputComponent->BindAction(LookAction, ETriggerEvent::Triggered, this, &AAdminCharacter::Look);
		EnhancedInputComponent->BindAction(JumpAction, ETriggerEvent::Started, this, &ACharacter::Jump);
		EnhancedInputComponent->BindAction(JumpAction, ETriggerEvent::Completed, this, &ACharacter::StopJumping);
		EnhancedInputComponent->BindAction(InteractAction, ETriggerEvent::Started, this, &AAdminCharacter::Interact);
	}
}

void AAdminCharacter::NotifyControllerChanged()
{
	Super::NotifyControllerChanged();

	if (APlayerController* OldPC = Cast<APlayerController>(CachedController))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(OldPC->GetLocalPlayer()))
		{
			if (DefaultMappingContext) Subsystem->RemoveMappingContext(DefaultMappingContext);
			if (MouseLookMappingContext) Subsystem->RemoveMappingContext(MouseLookMappingContext);
		}
	}

	CachedController = GetController();

	if (APlayerController* NewPC = Cast<APlayerController>(CachedController))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(NewPC->GetLocalPlayer()))
		{
			if (DefaultMappingContext) Subsystem->AddMappingContext(DefaultMappingContext, 0);
			if (MouseLookMappingContext) Subsystem->AddMappingContext(MouseLookMappingContext, 1);
		}
	}
}

void AAdminCharacter::PawnClientRestart()
{
	Super::PawnClientRestart();

	//~ Гарантоване підключення інпутів на старті рівня
	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			if (DefaultMappingContext) Subsystem->AddMappingContext(DefaultMappingContext, 0);
			if (MouseLookMappingContext) Subsystem->AddMappingContext(MouseLookMappingContext, 1);
		}
	}
}

void AAdminCharacter::Move(const FInputActionValue& Value)
{
	FVector2D MovementVector = Value.Get<FVector2D>();
	
	if (Controller != nullptr)
	{
		const FRotator Rotation = Controller->GetControlRotation();
		
		const FRotator YawRotation(0, Rotation.Yaw, 0);
		
		const FVector ForwardDirection = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X);
		
		const FVector RightDirection = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y);
		
		AddMovementInput(ForwardDirection, MovementVector.Y);
		AddMovementInput(RightDirection, MovementVector.X);
	}
}

void AAdminCharacter::Look(const FInputActionValue& Value)
{
	FVector2D LookAxisVector = Value.Get<FVector2D>();

	if (Controller != nullptr)
	{
		AddControllerYawInput(LookAxisVector.X);
		AddControllerPitchInput(LookAxisVector.Y);
	}
}


void AAdminCharacter::Interact()
{
	if (AAdminPlayerController* PC = Cast<AAdminPlayerController>(GetController()))
	{
		PC->TryInteract();
	}
}
