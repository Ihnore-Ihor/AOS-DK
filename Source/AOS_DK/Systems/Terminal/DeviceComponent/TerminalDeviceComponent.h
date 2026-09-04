#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TerminalDeviceComponent.generated.h"

UENUM(BlueprintType)
enum class EProcessState : uint8 
{
	Runnable UMETA(DisplayName = "Runnable waiting for context switch"),
	Running UMETA(DisplayName = "Runnning executes in cpu"),
	Stopped UMETA(DisplayName = "Stopped waiting for sigcont"),
	UninterruptibleSleep UMETA(DisplayName = "UninterruptibleSleep waiting for specific signal or resources"),
	InterruptibleSleep UMETA(DisplayName = "InterruptibleSleep waiting for signal or resources"),
	Deadlock UMETA(DisplayName = "Deadlock waiting for resources in cycle with another process(-es)"),
	Zombie UMETA(DisplayName = "Zombie waiting for parent to release him"),
	Orphan UMETA(DisplayName = "Orphan lost his parent"),
	Reaped UMETA(DisplayName = "Reaped releases from process table")
};

UCLASS(ClassGroup=(Terminal), meta=(BlueprintSpawnableComponent))
class AOS_DK_API UTerminalDeviceComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	// Sets default values for this component's properties
	UTerminalDeviceComponent();

public:
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "AOS_DK|Terminal")
	EProcessState CurrentProcessState;
	
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "AOS_DK|Terminal")
	TMap<FString, FString> VirtualFiles; //key - filename, value - file content
};
