#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "InteractableDevice.generated.h"

UINTERFACE(MinimalAPI)
class UInteractableDevice : public UInterface
{
	GENERATED_BODY()
};

/**
 * 
 */
class AOS_DK_API IInteractableDevice
{
	GENERATED_BODY()

public:
	// UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Terminal")
	// FString ExecuteCommand(const FString& Command, const TArray<FString>& Args);
	//
	// UFUNCTION(BlueprintNativeEvent, BlueprintPure, Category = "Terminal")
	// TArray<FString> GetAvailableCommands() const;
};
