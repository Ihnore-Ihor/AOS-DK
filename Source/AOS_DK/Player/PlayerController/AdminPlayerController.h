#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "AdminPlayerController.generated.h"

class UInputMappingContext;
class UInputAction;
class UUserWidget;

UCLASS()
class AOS_DK_API AAdminPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	AAdminPlayerController();
	
	void TryInteract();

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|UI")
	void ShowHint();

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|UI")
	void HideHint();

protected:
	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> PauseAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|UI")
	TSubclassOf<UUserWidget> HintWidgetClass;
	
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|UI")
	TObjectPtr<UUserWidget> CachedHintWidget;
	
	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|UI")
	void OnHintStateChanged(bool bShow);

private:
	
	void TogglePause();
	void CheckInteractable();
	void SetCurrentInteractable(AActor* NewInteractable);

	UPROPERTY()
	TObjectPtr<AActor> CurrentInteractable;
	
	FTimerHandle InteractTimerHandle;
};