#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "AOSEnvironmentState.generated.h"

class UMaterialParameterCollection;

/** Published day/night + weather inputs and the composed light/fog scales derived from them. */
USTRUCT(BlueprintType)
struct FAOSEnvironmentState
{
	GENERATED_BODY()

	// Day / night (AAOSDayNightCycle)
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float TimeOfDayH = 15.f;
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float SunElevationDeg = 40.f;
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float DayFactor = 1.f;
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float NightFactor = 0.f;

	// Weather (AAOSWeatherDirector)
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float StormAlpha = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float RainRate01 = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float Wetness = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float Wind01 = 0.f;

	// Composed (single place: UAOSEnvironmentStateSubsystem)
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float SunScale = 1.f;
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float SkyScale = 1.f;
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float FogDensityScale = 1.f;
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float FogInscatterScale = 1.f;

	/** Stars-only visibility = pure day/night NightFactor, faded out by cloud cover (storm). Not storm-lamp boosted. */
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") float StarVisibility = 0.f;

	/** Incremented whenever a composed scale changes by more than 0.002. */
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") int32 Revision = 0;

	/** True while storm gloom (not the sun position) is what drives MPC NightFactor above DayNight's own value. */
	UPROPERTY(BlueprintReadOnly, Category = "AOS_DK|Env") bool bStormLightsLamps = false;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAOSEnvironmentChanged, const FAOSEnvironmentState&, State);

/**
 * Single place that composes the environment light scales and the only writer of the environment scalars of
 * MPC_AOS_Atoll (NightFactor, Wetness, StormAlpha, Wind01). Light intensities are NOT written here:
 * AAOSOceanDepthController multiplies its cached base intensities by these scales.
 */
UCLASS()
class AOS_DK_API UAOSEnvironmentStateSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	void PublishDayNight(float TimeOfDayH, float SunElevationDeg, float DayFactor, float NightFactor);
	void PublishWeather(float StormAlpha, float RainRate01, float Wetness, float Wind01);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Env")
	const FAOSEnvironmentState& GetState() const { return State; }

	/** Fired at most at the publishers' rate (10 Hz) and only when something changed. */
	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Env")
	FOnAOSEnvironmentChanged OnChanged;

private:
	void Recompose();
	/** Writes changed scalars to the MPC; returns true when anything was written. */
	bool WriteCollection();

	FAOSEnvironmentState State;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialParameterCollection> Collection;

	// last values written to the MPC (change threshold 0.002)
	float WrittenNight = -1.f, WrittenWetness = -1.f, WrittenStorm = -1.f, WrittenWind = -1.f, WrittenStars = -1.f;
	// composed scales at the last Revision bump
	float RevSun = -1.f, RevSky = -1.f, RevFogD = -1.f, RevFogI = -1.f;
};
