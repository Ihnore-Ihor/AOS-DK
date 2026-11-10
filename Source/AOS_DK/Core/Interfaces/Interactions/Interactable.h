#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "Interactable.generated.h"

UINTERFACE(MinimalAPI)
class UInteractable : public UInterface
{
	GENERATED_BODY()
};

class AOS_DK_API IInteractable
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AOS_DK|Interaction")
	void Interact(AActor* Instigator);

	/**
	 * Cockpit reticle prompt for this target, shown as "[F] <OutAction>". Leave OutAction empty for the generic "INTERACT".
	 * bOutAvailable = false: pressing [F] would be refused (e.g. core already full) - the prompt is drawn dimmed.
	 */
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AOS_DK|Interaction")
	void GetInteractPrompt(AActor* Instigator, FText& OutAction, bool& bOutAvailable);
};