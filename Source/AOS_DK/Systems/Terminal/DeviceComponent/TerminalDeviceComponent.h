#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TerminalDeviceComponent.generated.h"
#include "Enums.h"


DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnProcessStateChangedDelegate, EProcessState, CurrentProcessState);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnVirtualFileChangedDelegate, FString, Filename, FString, FileContent);

UCLASS(ClassGroup=(Terminal), meta=(BlueprintSpawnableComponent))
class AOS_DK_API UTerminalDeviceComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	// Sets default values for this component's properties
	UTerminalDeviceComponent();

protected:
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "AOS_DK|Terminal")
	EProcessState CurrentProcessState;
	
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "AOS_DK|Terminal")
	TMap<FString, FString> VirtualFiles; //key - filename, value - file content TODO: change to TMap<FString, FVirtualFile> where FVirtualFile is a struct with Content, bRequiresSudo, FilePermission
	
	
	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Terminal")
	FOnProcessStateChangedDelegate ProcessStateChangedDelegate;
	
	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Terminal")
	FOnVirtualFileChangedDelegate VirtualFileChangedDelegate;
	
public:
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Terminal")
	void SetProcessState(EProcessState NewProcessState);
	
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Terminal", meta = (ExpandEnumAsExecs = "UpdateResult"))
	void UpdateVirtualFiles(FString Filename, FString NewValue, EFileUpdateResult& UpdateResult, FString& UpdateMessage);
};
