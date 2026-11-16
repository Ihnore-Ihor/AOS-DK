#include "AOS_DK/Environment/Ocean/AOSAtollGerstnerWaves.h"

#include "AOS_DK/Environment/Ocean/AOSAtollSettings.h"

void UAOSAtollGerstnerWaves::SetWaterWavesAsset(UWaterWavesAsset* InWaterWavesAsset)
{
#if WITH_EDITOR
	RegisterAssetCallback(false);
#endif
	WaterWavesAsset = InWaterWavesAsset;
#if WITH_EDITOR
	RegisterAssetCallback(true);
	OnUpdateWavesData.Broadcast(this, EPropertyChangeType::ValueSet);
#endif
}

const UWaterWaves* UAOSAtollGerstnerWaves::GetWaterWaves() const
{
	return WaterWavesAsset ? WaterWavesAsset->GetWaterWaves() : nullptr;
}

UWaterWaves* UAOSAtollGerstnerWaves::GetWaterWaves()
{
	return WaterWavesAsset ? WaterWavesAsset->GetWaterWaves() : nullptr;
}

float UAOSAtollGerstnerWaves::GetMaxWaveHeight() const
{
	const UWaterWaves* Waves = GetWaterWaves();
	return Waves ? Waves->GetMaxWaveHeight() : 0.f;
}

float UAOSAtollGerstnerWaves::GetWaveHeightAtPosition(const FVector& InPosition, float InWaterDepth, float InTime, FVector& OutNormal) const
{
	if (const UWaterWaves* Waves = GetWaterWaves())
	{
		return Waves->GetWaveHeightAtPosition(InPosition, InWaterDepth, InTime, OutNormal);
	}
	OutNormal = FVector::UpVector;
	return 0.f;
}

float UAOSAtollGerstnerWaves::GetSimpleWaveHeightAtPosition(const FVector& InPosition, float InWaterDepth, float InTime) const
{
	const UWaterWaves* Waves = GetWaterWaves();
	return Waves ? Waves->GetSimpleWaveHeightAtPosition(InPosition, InWaterDepth, InTime) : 0.f;
}

float UAOSAtollGerstnerWaves::GetWaveAttenuationFactor(const FVector& InPosition, float InWaterDepth, float InTargetWaveMaskDepth) const
{
	const UWaterWaves* Waves = GetWaterWaves();
	if (!Waves)
	{
		return 0.f;
	}
	// Depth attenuation of the plugin x Atoll radial amplitude mask (0 lagoon .. 1 open ocean).
	return Waves->GetWaveAttenuationFactor(InPosition, InWaterDepth, InTargetWaveMaskDepth) * AOSAtoll::WaveScale(InPosition);
}

void UAOSAtollGerstnerWaves::BeginDestroy()
{
#if WITH_EDITOR
	RegisterAssetCallback(false);
#endif
	Super::BeginDestroy();
}

#if WITH_EDITOR
void UAOSAtollGerstnerWaves::PostLoad()
{
	Super::PostLoad();
	RegisterAssetCallback(true);
}

void UAOSAtollGerstnerWaves::PreEditChange(FProperty* PropertyAboutToChange)
{
	Super::PreEditChange(PropertyAboutToChange);
	RegisterAssetCallback(false);
}

void UAOSAtollGerstnerWaves::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
	RegisterAssetCallback(true);
	Super::PostEditChangeProperty(PropertyChangedEvent);
}

void UAOSAtollGerstnerWaves::RegisterAssetCallback(bool bRegister)
{
	if (WaterWavesAsset)
	{
		WaterWavesAsset->OnUpdateWavesAssetData.RemoveAll(this);
		if (bRegister)
		{
			WaterWavesAsset->OnUpdateWavesAssetData.AddUObject(this, &UAOSAtollGerstnerWaves::OnWavesAssetUpdated);
		}
	}
}

void UAOSAtollGerstnerWaves::OnWavesAssetUpdated(UWaterWavesAsset* InWaterWavesAsset, EPropertyChangeType::Type InChangeType)
{
	OnUpdateWavesData.Broadcast(this, InChangeType);
}
#endif
