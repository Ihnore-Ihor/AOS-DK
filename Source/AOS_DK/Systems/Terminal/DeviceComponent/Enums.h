#pragma once

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

UENUM(BlueprintType)
enum class EFileUpdateResult : uint8
{
	NotFound UMETA(DisplayName = "bash: [/path/to/file]: No such file or directory"),	
	PermissionDenied UMETA(DisplayName = "bash: [file]: Permission denied"),
	NotAFile UMETA(DisplayName = "bash: [file]: Is a directory"),
	Success UMETA(DisplayName = "OK"),
};