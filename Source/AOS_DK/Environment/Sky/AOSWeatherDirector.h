#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSWeatherDirector.generated.h"

class AAOSOceanDepthController;
class AVolumetricCloud;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UNiagaraComponent;
class UNiagaraSystem;

UENUM(BlueprintType)
enum class EAOSWeatherState : uint8
{
	Clear,
	Building,
	Raining,
	Clearing
};

/**
 * Randomized periodic storm FSM: Clear -> Building -> Raining -> Clearing.
 * Publishes StormAlpha / RainRate01 / Wetness / Wind01 to UAOSEnvironmentStateSubsystem at 10 Hz and drives the
 * VolumetricCloud through a runtime MID. Console: aos.env.Storm <0|1|auto>.
 */
UCLASS(ClassGroup = "AOS_DK", meta = (DisplayName = "AOS Weather Director"))
class AOS_DK_API AAOSWeatherDirector : public AActor
{
	GENERATED_BODY()

public:
	AAOSWeatherDirector();

	virtual void Tick(float DeltaSeconds) override;

	/** Test override: 1 = storm now and hold it, 0 = clear now and hold it, -1 = back to the random cycle. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Weather")
	void ForceStorm(int32 Mode);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Weather")
	EAOSWeatherState GetWeatherState() const { return State; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Weather")
	float GetStormAlpha() const { return StormAlpha; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Weather")
	float GetWetness() const { return Wetness; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Weather")
	float GetWind01() const { return Wind01; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Weather")
	float GetRainRate01() const { return RainRate01; }

	/** Audio / FX hook (Batch C). */
	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Weather")
	void BP_OnWeatherStateChanged(EAOSWeatherState NewState, EAOSWeatherState OldState);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Weather|Refs")
	TObjectPtr<AVolumetricCloud> VolumetricCloud;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Weather|Refs")
	TObjectPtr<AAOSOceanDepthController> OceanController;

	/** Rain Niagara system (NS_AOS_Rain, authored in Batch C). Null = no rain FX, state machine still runs. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Weather|Rain")
	TObjectPtr<UNiagaraSystem> RainSystem;

	/**
	 * Overcast mapping. The engine simple cloud material is NOT monotonic: Cloud_GlobalCoverage ~0.3 is a full overcast, but
	 * values towards 1.0 thin the layer out to an empty sky, and StormClouds > 0 swaps the layout to isolated storm cells.
	 * So a storm blends Cloud_GlobalCoverage from the clear value up to StormCoverage (reached at StormAlpha = CloudsFullAtStorm)
	 * and keeps StormClouds at StormCloudsAtPeak (0 = never use the storm-cell layout).
	 */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Clouds", meta = (ClampMin = "-1", ClampMax = "1"))
	float StormCoverage = 0.3f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Clouds", meta = (ClampMin = "0.05", ClampMax = "1"))
	float CloudsFullAtStorm = 0.5f;

	/** Cloud_GlobalDensity multiplier at full storm. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Clouds", meta = (ClampMin = "0.5", ClampMax = "4"))
	float StormDensityScale = 1.5f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Clouds", meta = (ClampMin = "0", ClampMax = "1"))
	float StormCloudsAtPeak = 0.f;

	/** Ocean surface Z used for User.WaterZ (cm). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Rain")
	float WaterSurfaceZ = 40.f;

	/**
	 * Rain lattice (cm). Streaks are wrapped by M_AOS_RainStreak with period (5000, 5000, 2000) and splashes by M_AOS_RainSplash with
	 * period (3000, 3000), both around the camera, so the rain field is a periodic lattice anchored in the world. The Niagara component
	 * hops with the camera ONLY in whole multiples of the common period: the picture is identical after a hop (nothing drags or pops),
	 * while the emitter bounds stay around the viewer, so the rain is complete anywhere on the map (open ocean included).
	 * RainLatticeXY must be a multiple of lcm(5000, 3000) = 15000; RainLatticeZ a multiple of 2000.
	 */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Rain", meta = (ClampMin = "15000", Units = "cm"))
	float RainLatticeXY = 15000.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Rain", meta = (ClampMin = "2000", Units = "cm"))
	float RainLatticeZ = 2000.f;

	/** 0 = time-based seed; fixed seed gives reproducible demos. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Random")
	int32 Seed = 0;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Durations", meta = (Units = "s")) FVector2D ClearDuration = FVector2D(150.0, 330.0);
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Durations", meta = (Units = "s")) FVector2D FirstStormDelay = FVector2D(60.0, 120.0);
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Durations", meta = (Units = "s")) FVector2D BuildingDuration = FVector2D(25.0, 40.0);
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Durations", meta = (Units = "s")) FVector2D RainingDuration = FVector2D(90.0, 180.0);
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Durations", meta = (Units = "s")) FVector2D ClearingDuration = FVector2D(30.0, 50.0);
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Durations") FVector2D PeakRange = FVector2D(0.55, 1.0);

	/** Building / Clearing length when the storm is forced with aos.env.Storm 1|0 (fast tests). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Durations", meta = (Units = "s", ClampMin = "1"))
	float ForcedTransitionSeconds = 10.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Wetness", meta = (Units = "s"))
	float WetRiseSeconds = 25.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Wetness", meta = (Units = "s"))
	float DryFallSeconds = 120.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Weather|Update", meta = (ClampMin = "1", ClampMax = "60"))
	float PublishHz = 10.f;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	void ResolveReferences();
	void SetState(EAOSWeatherState NewState, float Duration);
	void EnterClear();
	void StepFsm(float Dt);
	void UpdateClouds();
	void UpdateRain();
	bool GetViewLocation(FVector& OutLocation) const;
	/** Lattice node nearest to the view; keeps the current node while the view is within half a cell + margin (no flip-flop). */
	FVector SnapRainOrigin(const FVector& View, const FVector& Current) const;
	void Publish();
	float RandRange(const FVector2D& Range);

	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Weather|Debug") EAOSWeatherState State = EAOSWeatherState::Clear;
	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Weather|Debug") float StateTime = 0.f;
	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Weather|Debug") float StateDuration = 0.f;
	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Weather|Debug") float StormAlpha = 0.f;
	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Weather|Debug") float RainRate01 = 0.f;
	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Weather|Debug") float Wetness = 0.f;
	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Weather|Debug") float Wind01 = 0.2f;

	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> CloudMID;
	UPROPERTY(Transient) TObjectPtr<UMaterialInterface> OriginalCloudMaterial;
	UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> RainComponent;

	FRandomStream Random;
	/** -1 = random cycle, 0 = held clear, 1 = held storm. */
	int32 ForcedMode = -1;
	float Peak = 1.f;
	float ClearingStartAlpha = 0.f;
	float BuildStartAlpha = 0.f;
	float WindBase = 0.2f;
	float WindBaseTarget = 0.2f;
	float GustOffset = 0.f;
	float ElapsedTime = 0.f;
	float PublishAccum = 0.f;
	bool bFirstClear = true;

	float BaseCoverage = 0.5f, BaseDensity = 0.5f, BaseStorm = 0.f;
	float LastCoverage = -1.f, LastDensity = -1.f, LastStormClouds = -1.f;
};
