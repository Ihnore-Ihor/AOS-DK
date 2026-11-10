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

	/** Interactable found by the 10 Hz view trace / overlap check (nullptr while interaction is locked). */
	AActor* GetCurrentInteractable() const { return CurrentInteractable; }

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|UI")
	void ShowHint();

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|UI")
	void HideHint();

	/** The legacy top-left typing hint (W_InteractHint) is an on-foot UI: true only while an AAdminCharacter is possessed. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|UI")
	bool IsOnFoot() const;

protected:
	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;
	virtual void OnPossess(APawn* InPawn) override;

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
	/** Erase + collapse the hint widget (inside the Shell the cockpit reticle prompt is the only interaction UI). */
	void SuppressHint();

	UPROPERTY()
	TObjectPtr<AActor> CurrentInteractable;
	
	FTimerHandle InteractTimerHandle;
	
public:
	UFUNCTION(BlueprintCallable, Category = "Interaction")
	void SetInteractLocked(bool bLocked);

	bool IsInteractLocked() const { return bInteractLocked; }

private:
	UPROPERTY(VisibleInstanceOnly, Category = "Interaction")
	bool bInteractLocked = false;
};