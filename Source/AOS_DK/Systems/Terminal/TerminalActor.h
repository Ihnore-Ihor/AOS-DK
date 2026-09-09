#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Templates/Function.h"
#include "TerminalActor.generated.h"

USTRUCT(BlueprintType)
struct FTerminalCommandContext
{
	GENERATED_BODY()
	
	FString RawPrompt;
	TArray<FString> ParsedPrompt;
};

UCLASS()
class AOS_DK_API ATerminalActor : public AActor
{
	GENERATED_BODY()

private:
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Terminal|Info")
	UDataTable* CommandDataTable;
	
	TSet<FString> Commands;
	
	TMap<FString, TFunction<FString(const FTerminalCommandContext&)>> CommandRouters;
	
public: 
	virtual void BeginPlay() override;
	
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Terminal|Info")
	FString DevicePath;
	
protected:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Terminal")
	TArray<AActor*> ConnectedDevices;

public:
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Terminal")
	FString ProcessInput(FString RawInput);
private:
	FString HelpCommandFormer(const FTerminalCommandContext& Prompt) const;
	FString HelpCommandTextWrapper(const int LongestLeftLength, const FString &LeftText, const FString &RightText, int RowLength = 80) const;
	
	FString LsCommandFormer(const FTerminalCommandContext& Prompt) const;
	
	FString CatCommandFormer(const FTerminalCommandContext& Prompt) const;
	
	FString EchoCommandFormer(const FTerminalCommandContext& Prompt) const;
	
protected:
	UTerminalDeviceComponent* GetTargetDevice(const FString& TargetPath, FString& OutFileName, FString& OutErrorMessage) const;	
};
