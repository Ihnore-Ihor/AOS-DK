#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "ManSaveSubsystem.generated.h"

/**
 * 
 */
UENUM(BlueprintType)
enum class EAddPageResult : uint8
{
	Success UMETA(DisplayName = "Page added to man successfully"),
	DuplicatePage UMETA(DisplayName = "Page was already added"),
	Error UMETA(DisplayName = "Error or Null while adding page")
};


UCLASS()
class AOS_DK_API UManSaveSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

protected:
	UPROPERTY(BlueprintReadWrite, Category = "AOS_DK|Terminal|SaveData")
	TSet<FName> CollectedPages;

public:
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Terminal|SaveData", meta = (ExpandEnumAsExecs = "Result"))
	void AddPage(FName PageName, EAddPageResult& Result);

	UFUNCTION(BlueprintCallable, BlueprintPure, Category = "AOS_DK|Terminal|SaveData")
	bool HasPage(FName PageName) const;

	void WriteToFilePageProgress(); //TODO: make saving data to files
};
