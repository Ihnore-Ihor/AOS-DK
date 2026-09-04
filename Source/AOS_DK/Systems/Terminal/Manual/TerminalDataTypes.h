#pragma once
#include "CoreMinimal.h"
#include"Engine/DataTable.h"
#include "TerminalDataTypes.generated.h"

USTRUCT(BlueprintType)
struct FManPageData : public FTableRowBase
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Terminal|ManPage")
	FString Title;
	
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Terminal|ManPage")
	FString LoreDescription;
	
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Terminal|ManPage")
	FString ConceptExplanation;
};