#include "AdminPlayerController.h"
#include "EnhancedInputComponent.h"
#include "Blueprint/UserWidget.h"
#include "Kismet/GameplayStatics.h"
#include "AOS_DK/Core/Interfaces/Interactions/Interactable.h"
#include "AOS_DK/Player/AdminCharacter.h"

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

bool AAdminPlayerController::IsOnFoot() const
{
	const APawn* ControlledPawn = GetPawn();
	return ControlledPawn && ControlledPawn->IsA<AAdminCharacter>();
}

void AAdminPlayerController::OnPossess(APawn* InPawn)
{
	Super::OnPossess(InPawn);
	if (!IsOnFoot())
	{
		SuppressHint();
	}
	else if (CurrentInteractable)
	{
		ShowHint(); // back on foot next to something interactable
	}
}

void AAdminPlayerController::SuppressHint()
{
	if (CachedHintWidget)
	{
		OnHintStateChanged(false);
		CachedHintWidget->SetVisibility(ESlateVisibility::Collapsed);
	}
}

void AAdminPlayerController::ShowHint()
{
	// Every caller (C++ focus change, Blueprints, dock flow) goes through here: no typing hint inside the Shell.
	if (!IsOnFoot())
	{
		SuppressHint();
		return;
	}
	if (CachedHintWidget && CachedHintWidget->GetVisibility() == ESlateVisibility::Collapsed)
	{
		CachedHintWidget->SetVisibility(ESlateVisibility::Hidden); // initial state; OnHintStateChanged reveals it
	}
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
	if (bInteractLocked)
	{
		return;
	}

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

void AAdminPlayerController::SetInteractLocked(bool bLocked)
{
	bInteractLocked = bLocked;

	if (bInteractLocked)
	{
		SetCurrentInteractable(nullptr);
	}
}