#include "TerminalDeviceComponent.h"

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
