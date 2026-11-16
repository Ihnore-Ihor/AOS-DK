#pragma once

#include "CoreMinimal.h"
#include "WaterWaves.h"
#include "AOSAtollGerstnerWaves.generated.h"

/**
 * Wave source for WaterBodyOcean: the Gerstner waves of a UWaterWavesAsset (DA_OceanWaves_AOS) with the
 * Atoll radial mask folded into GetWaveAttenuationFactor, so every CPU water query returns flat water in
 * the lagoon and the full spectrum outside (Urban Bible 2.3).
 *
 * UE 5.7.4: UGerstnerWaterWaves is MinimalAPI and exports neither its constructor nor its UObject
 * overrides, so it cannot be subclassed from a game module. This class is the sanctioned extension point
 * instead (same pattern as UWaterWavesAssetReference): GetWaterWaves() still hands the plugin the asset's
 * UGerstnerWaterWaves, so GPU wave data, the snow field and the depth controller are unchanged.
 */
UCLASS(EditInlineNew, BlueprintType, NotBlueprintable, meta = (DisplayName = "AOS Atoll Gerstner Waves"))
class AOS_DK_API UAOSAtollGerstnerWaves : public UWaterWavesBase
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AOS|Atoll")
	void SetWaterWavesAsset(UWaterWavesAsset* InWaterWavesAsset);

	UFUNCTION(BlueprintPure, Category = "AOS|Atoll")
	UWaterWavesAsset* GetWaterWavesAsset() const { return WaterWavesAsset; }

	virtual const UWaterWaves* GetWaterWaves() const override;
	virtual UWaterWaves* GetWaterWaves() override;

	virtual float GetMaxWaveHeight() const override;
	virtual float GetWaveHeightAtPosition(const FVector& InPosition, float InWaterDepth, float InTime, FVector& OutNormal) const override;
	virtual float GetSimpleWaveHeightAtPosition(const FVector& InPosition, float InWaterDepth, float InTime) const override;
	virtual float GetWaveAttenuationFactor(const FVector& InPosition, float InWaterDepth, float InTargetWaveMaskDepth) const override;

	virtual void BeginDestroy() override;
#if WITH_EDITOR
	virtual void PostLoad() override;
	virtual void PreEditChange(FProperty* PropertyAboutToChange) override;
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

private:
#if WITH_EDITOR
	void RegisterAssetCallback(bool bRegister);
	void OnWavesAssetUpdated(UWaterWavesAsset* InWaterWavesAsset, EPropertyChangeType::Type InChangeType);
#endif

	UPROPERTY(EditAnywhere, Category = "Water Waves Asset")
	TObjectPtr<UWaterWavesAsset> WaterWavesAsset;
};
