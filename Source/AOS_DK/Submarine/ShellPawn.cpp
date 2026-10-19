#include "ShellPawn.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Camera/CameraComponent.h"
#include "BuoyancyComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "AOS_DK/Player/AdminCharacter.h"
#include "AOS_DK/Player/PlayerController/AdminPlayerController.h"

AShellPawn::AShellPawn()
{
	PrimaryActorTick.bCanEverTick = true;

	BoxRoot = CreateDefaultSubobject<UBoxComponent>(TEXT("BoxRoot"));
	RootComponent = BoxRoot;
	BoxRoot->SetSimulatePhysics(true);
	BoxRoot->SetCollisionProfileName(TEXT("PhysicsActor"));

	ShellMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ShellMesh"));
	ShellMesh->SetupAttachment(BoxRoot);
	ShellMesh->SetCollisionProfileName(TEXT("NoCollision"));

	FPCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FPCamera"));
	FPCamera->SetupAttachment(BoxRoot);
	FPCamera->bUsePawnControlRotation = false;

	BuoyancyComponent = CreateDefaultSubobject<UBuoyancyComponent>(TEXT("BuoyancyComponent"));
}

void AShellPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	if (UEnhancedInputComponent* EnhancedInputComp = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		EnhancedInputComp->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AShellPawn::ApplyThrust);
		EnhancedInputComp->BindAction(MoveAction, ETriggerEvent::Completed, this, &AShellPawn::ResetThrust);
		EnhancedInputComp->BindAction(RotateAction, ETriggerEvent::Triggered, this, &AShellPawn::ApplyRotation);
		EnhancedInputComp->BindAction(InteractAction, ETriggerEvent::Started, this, &AShellPawn::HandleInteract);
		EnhancedInputComp->BindAction(BallastAction, ETriggerEvent::Triggered, this, &AShellPawn::ApplyBallast);
		EnhancedInputComp->BindAction(BallastAction, ETriggerEvent::Completed, this, &AShellPawn::ResetBallast);
	}
}

void AShellPawn::NotifyControllerChanged()
{
	Super::NotifyControllerChanged();

	if (APlayerController* OldPC = Cast<APlayerController>(CachedController))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(OldPC->GetLocalPlayer()))
		{
			if (SubMappingContext) Subsystem->RemoveMappingContext(SubMappingContext);
		}
	}

	CachedController = GetController();

	if (APlayerController* NewPC = Cast<APlayerController>(CachedController))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(NewPC->GetLocalPlayer()))
		{
			if (SubMappingContext) Subsystem->AddMappingContext(SubMappingContext, 0);
		}
	}
}

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
	if (AAdminPlayerController* PC = Cast<AAdminPlayerController>(GetController()))
	{
		PC->TryInteract();
	}
}

void AShellPawn::ApplyThrust(const FInputActionValue& Value)
{
	bIsThrusting = true;
	CurrentMoveInput = Value.Get<FVector>();
	TargetThrust = ThrustMultiplier;
}

void AShellPawn::ResetThrust(const FInputActionValue& Value)
{
	bIsThrusting = false;
	CurrentMoveInput = FVector::ZeroVector;
	TargetThrust = 0.f;
}

void AShellPawn::ApplyRotation(const FInputActionValue& Value)
{
	FVector RotationInput = Value.Get<FVector>();
	FVector Torque = BoxRoot->GetComponentTransform().TransformVector(RotationInput * TorqueMultiplier);
	BoxRoot->AddTorqueInDegrees(Torque, NAME_None, true);
}

void AShellPawn::ApplyBallast(const FInputActionValue& Value)
{
	float BallastInput = Value.Get<float>();
	if (BallastInput > 0.1f) TargetBallastForce = BallastForceLimit;
	else if (BallastInput < -0.1f) TargetBallastForce = -BallastForceLimit;
}

void AShellPawn::ResetBallast(const FInputActionValue& Value)
{
	TargetBallastForce = 0.f;
}

void AShellPawn::UpdateBallastSystem(float DeltaTime, bool bInWater)
{
	CurrentBallastForce = FMath::FInterpTo(CurrentBallastForce, TargetBallastForce, DeltaTime, BallastChangeSpeed);
	float CurrentVerticalSpeed = BoxRoot->GetComponentVelocity().Z;

	if (bInWater)
	{
		if (FMath::Abs(TargetBallastForce) < 0.1f && !bIsThrusting)
		{
			BoxRoot->AddForce(FVector(0.f, 0.f, -CurrentVerticalSpeed * DepthStabilizationStiffness), NAME_None, true);
		}
		else
		{
			BoxRoot->AddForce(FVector(0.f, 0.f, CurrentBallastForce), NAME_None, true);
		}
	}
}

void AShellPawn::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	//~ Чиста математика: звіряємо висоту центру субмарини з реальною хвилею
	bool bInWater = false;
	if (BuoyancyComponent)
	{
		FVector WaterPlaneLoc, WaterPlaneNorm, WaterSurfacePos, WaterVel;
		float WaterDepth = 0.f;
		int32 WaterBodyIdx = -1;
		BuoyancyComponent->GetLastWaterSurfaceInfo(WaterPlaneLoc, WaterPlaneNorm, WaterSurfacePos, WaterDepth, WaterBodyIdx, WaterVel);

		// Субмарина у воді, якщо вона в океані (Idx >= 0) і її центр не вилетів вище хвилі (+30 см допуск на рубку)
		bInWater = (WaterBodyIdx >= 0) && (GetActorLocation().Z <= (WaterSurfacePos.Z + 30.f));
	}

	UpdateBallastSystem(DeltaTime, bInWater);

	//~ Плавний розгін тяги
	CurrentThrust = FMath::FInterpTo(CurrentThrust, TargetThrust, DeltaTime, ThrustRampSpeed);

	if (bInWater)
	{
		if (CurrentThrust > 10.f)
		{
			FVector Force = BoxRoot->GetComponentTransform().TransformVector(CurrentMoveInput * CurrentThrust);
			BoxRoot->AddForce(Force, NAME_None, true);
		}

		FVector CurrentVelocity = BoxRoot->GetComponentVelocity();
		FVector ForwardDir = BoxRoot->GetForwardVector();

		FVector ForwardVelocity = ForwardDir * FVector::DotProduct(CurrentVelocity, ForwardDir);
		FVector LateralVelocity = CurrentVelocity - ForwardVelocity;

		BoxRoot->AddForce(-LateralVelocity * LateralDrag, NAME_None, true);
	}
	else
	{
		//~ У повітрі ВСЕ миттєво відрубається!
		CurrentThrust = 0.f;
		CurrentBallastForce = 0.f;
	}
}