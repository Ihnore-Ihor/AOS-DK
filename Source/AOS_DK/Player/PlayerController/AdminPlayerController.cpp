#include "AdminPlayerController.h"
#include "EnhancedInputComponent.h"
#include "Blueprint/UserWidget.h"
#include "Kismet/GameplayStatics.h"
#include "AOS_DK/Core/Interfaces/Interactions/Interactable.h"

AAdminPlayerController::AAdminPlayerController()
{
	PrimaryActorTick.bCanEverTick = true; 
}


void AAdminPlayerController::BeginPlay()
{
	Super::BeginPlay();

	GetWorld()->GetTimerManager().SetTimer(InteractTimerHandle, this, &AAdminPlayerController::CheckInteractable, 0.1f, true);
}

void AAdminPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	if (UEnhancedInputComponent* EnhancedInputComponent = Cast<UEnhancedInputComponent>(InputComponent))
	{
		EnhancedInputComponent->BindAction(PauseAction, ETriggerEvent::Started, this, &AAdminPlayerController::TogglePause);
	}
}

void AAdminPlayerController::TogglePause()
{
	bool bIsPaused = UGameplayStatics::IsGamePaused(this);
	UGameplayStatics::SetGamePaused(this, !bIsPaused);
	
	bShowMouseCursor = !bIsPaused;
	
	if (!bIsPaused)
	{
		FInputModeUIOnly InputMode;
		SetInputMode(InputMode);
	}
	else
	{
		FInputModeGameOnly InputMode;
		SetInputMode(InputMode);
	}
}

void AAdminPlayerController::ShowHint()
{
	if (!CachedHintWidget && HintWidgetClass)
	{
		CachedHintWidget = CreateWidget<UUserWidget>(this, HintWidgetClass);
		if (CachedHintWidget)
		{
			CachedHintWidget->AddToViewport();
			CachedHintWidget->SetVisibility(ESlateVisibility::Hidden);
		}
	}

	OnHintStateChanged(true);
}

void AAdminPlayerController::HideHint()
{
	OnHintStateChanged(false);
}

void AAdminPlayerController::CheckInteractable()
{
	APawn* ControlledPawn = GetPawn();
	if (!ControlledPawn || !PlayerCameraManager)
	{
		SetCurrentInteractable(nullptr);
		return;
	}

	AActor* BestInteractable = nullptr;

	FVector StartLoc = PlayerCameraManager->GetCameraLocation();
	FVector EndLoc = StartLoc + (PlayerCameraManager->GetActorForwardVector() * 500.f);

	FHitResult HitResult;
	FCollisionQueryParams Params;
	Params.AddIgnoredActor(ControlledPawn);

	if (GetWorld()->LineTraceSingleByChannel(HitResult, StartLoc, EndLoc, ECC_Visibility, Params))
	{
		if (HitResult.GetActor() && HitResult.GetActor()->Implements<UInteractable>())
		{
			BestInteractable = HitResult.GetActor();
		}
	}

	if (!BestInteractable)
	{
		TArray<AActor*> OverlappingActors;
		ControlledPawn->GetOverlappingActors(OverlappingActors);
		
		for (AActor* Actor : OverlappingActors)
		{
			if (Actor && Actor->Implements<UInteractable>() && Actor != ControlledPawn)
			{
				BestInteractable = Actor;
				break;
			}
		}
	}

	SetCurrentInteractable(BestInteractable);
}

void AAdminPlayerController::SetCurrentInteractable(AActor* NewInteractable)
{
	if (CurrentInteractable != NewInteractable)
	{
		CurrentInteractable = NewInteractable;
		
		if (CurrentInteractable)
		{
			ShowHint();
		}
		else
		{
			HideHint();
		}
	}
}

void AAdminPlayerController::TryInteract()
{
	if (CurrentInteractable && GetPawn())
	{
		IInteractable::Execute_Interact(CurrentInteractable, GetPawn());
	}
}