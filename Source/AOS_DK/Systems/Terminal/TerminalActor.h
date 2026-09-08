#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TerminalActor.generated.h"

UCLASS()
class AOS_DK_API ATerminalActor : public AActor
{
	GENERATED_BODY()
	
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Terminal|Info")
	FString DevicePath;
private:
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Terminal|Info")
	UDataTable* CommandDataTable;
	
	TSet<FString> Commands;
	
public: 
	virtual void BeginPlay() override;
	
protected:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Terminal")
	TArray<AActor*> ConnectedDevices;

public:
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Terminal")
	FString ProcessInput(FString RawInput);
private:
	FString HelpCommandFormer() const;
	FString HelpCommandTextWrapper(const int LongestLeftLength, const FString &LeftText, const FString &RightText, int RowLength = 80) const;
	
	FString LsCommandFormer() const;
	
	FString CatCommandFormer(TArray<FString> InputTokens) const;
	
	FString EchoCommandFormer(FString RawInput) const;
	
protected:
	UTerminalDeviceComponent* GetTargetDevice(const FString& TargetPath, FString& OutFileName, FString& OutErrorMessage) const;	
};
