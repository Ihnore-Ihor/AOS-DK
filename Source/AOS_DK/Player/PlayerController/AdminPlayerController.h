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

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|UI")
	void ShowHint();

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|UI")
	void HideHint();

protected:
	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputMappingContext> DefaultMappingContext;
	
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputMappingContext> MouseLookMappingContext;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> PauseAction;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|UI")
	TSubclassOf<UUserWidget> HintWidgetClass;
	
	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|UI")
	void OnHintStateChanged(bool bShow);

private:
	UPROPERTY()
	TObjectPtr<UUserWidget> CachedHintWidget;

	void TogglePause();
};