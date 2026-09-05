#include "TerminalDeviceComponent.h"


// Sets default values for this component's properties
UTerminalDeviceComponent::UTerminalDeviceComponent()
{
	// Set this component to be initialized when the game starts, and to be ticked every frame.  You can turn these features
	// off to improve performance if you don't need them.
	PrimaryComponentTick.bCanEverTick = true;

	// ...
}

void UTerminalDeviceComponent::SetProcessState(EProcessState NewProcessState)
{
	CurrentProcessState = NewProcessState;
	ProcessStateChangedDelegate.Broadcast(CurrentProcessState);
}

void UTerminalDeviceComponent::UpdateVirtualFiles(FString Filename, FString NewValue, EFileUpdateResult& UpdateResult, FString& UpdateMessage)
{
	if (!VirtualFiles.Contains(Filename))
	{
		UpdateResult = EFileUpdateResult::NotFound;
		UpdateMessage = FString::Printf(TEXT("bash: %s: No such file or directory"), *Filename);
		return;
	} //TODO: add file permission check 
	VirtualFiles[Filename] = NewValue;
	VirtualFileChangedDelegate.Broadcast(Filename, NewValue);
	UpdateResult = EFileUpdateResult::Success;
	UpdateMessage = FString::Printf(TEXT("OK"));
}
