#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "AOS_HazardReceiver.generated.h"

/** Effects an AI hazard volume (heap brine pool) applies to a receiver. */
USTRUCT(BlueprintType)
struct AOS_DK_API FAOSHazardParams
{
	GENERATED_BODY()

	/** MaxWalkSpeed multiplier. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Hazard", meta = (ClampMin = "0.05", ClampMax = "1"))
	float SpeedScale = 0.4f;

	/** Sight radius multiplier (perception reduction). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Hazard", meta = (ClampMin = "0.05", ClampMax = "1"))
	float SightRadiusScale = 0.5f;

	/** Sight half-angle while inside, degrees. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Hazard", meta = (ClampMin = "5", ClampMax = "180", Units = "deg"))
	float SightHalfAngle = 40.f;

	/** M_hazard of the evasion model. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Hazard", meta = (ClampMin = "0", ClampMax = "1"))
	float DodgeScale = 0.25f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Hazard")
	bool bBlockDecoyRegen = true;
};

UINTERFACE(MinimalAPI, BlueprintType)
class UAOS_HazardReceiver : public UInterface
{
	GENERATED_BODY()
};

/** Implemented by actors that a hazard volume may hinder (only the Reaper in Lab 5; Shell-1 and Daemons do not). */
class AOS_DK_API IAOS_HazardReceiver
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AOS_DK|Hazard")
	void EnterHazard(AActor* Source, const FAOSHazardParams& Params);

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "AOS_DK|Hazard")
	void ExitHazard(AActor* Source);
};
