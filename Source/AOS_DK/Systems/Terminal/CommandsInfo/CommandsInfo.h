#pragma once

USTRUCT(BlueprintType)
struct FCommandsInfo : public FTableRowBase
{
	GENERATED_BODY()
	
public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Terminal|Info")
	FString Description;
	
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Terminal|Info")
	TMap<FString, FString> Syntax; //key - syntax example, value - explanation
};
