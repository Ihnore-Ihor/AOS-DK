#include "AdminPlayerController.h"
#include "EnhancedInputSubsystems.h"
#include "EnhancedInputComponent.h"
#include "Blueprint/UserWidget.h"
#include "Kismet/GameplayStatics.h"

AAdminPlayerController::AAdminPlayerController()
{
}

void AAdminPlayerController::BeginPlay()
{
	Super::BeginPlay();

	if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
	{
		if (DefaultMappingContext)
		{
			Subsystem->AddMappingContext(DefaultMappingContext, 0);
		}
		if (MouseLookMappingContext)
		{
			Subsystem->AddMappingContext(MouseLookMappingContext, 1);
		}
	}
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