#include "AOSOceanDepthController.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/LightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/SkyLight.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "WaterBodyActor.h"
#include "WaterBodyComponent.h"

namespace AOSOceanParams
{
	static const FName FogAmbientColor(TEXT("Fog Ambient Color"));
	static const FName FogScatterColor(TEXT("Fog Scatter Color"));
	static constexpr float ReapplyDepthStepM = 0.25f;
}

AAOSOceanDepthController::AAOSOceanDepthController()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork; // after the camera manager has moved the view
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	// Underwater medium (PDF: density 0.03-0.08, g 0.65-0.82, extinction scale 1.2-2.2).
	WaterFog = FAOSFogPreset();

	// Air above the ocean: light haze, density thinning with altitude.
	AirFog.Density = 0.01f;
	AirFog.HeightFalloff = 0.2f;
	AirFog.Inscattering = FLinearColor(0.12f, 0.18f, 0.26f);
	AirFog.MaxOpacity = 1.f;
	AirFog.VolumetricAlbedo = FColor::White;
	AirFog.VolumetricExtinctionScale = 1.f;
	AirFog.VolumetricScatteringDistribution = 0.2f;
}

void AAOSOceanDepthController::BeginPlay()
{
	Super::BeginPlay();
	ResolveReferences();
	CaptureBaseline();
}

void AAOSOceanDepthController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (bHasBaseline)
	{
		Apply(/*bUnderwater*/ false, 0.f); // leave the scene in its authored (air) state
	}
	Super::EndPlay(EndPlayReason);
}

void AAOSOceanDepthController::ResolveReferences()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (!WaterBody)
	{
		for (TActorIterator<AWaterBody> It(World); It; ++It)
		{
			const UWaterBodyComponent* Body = It->GetWaterBodyComponent();
			if (Body && Body->GetWaterBodyType() == EWaterBodyType::Ocean)
			{
				WaterBody = *It;
				break;
			}
		}
	}
	if (!Sun)       { for (TActorIterator<ADirectionalLight> It(World); It; ++It) { Sun = *It; break; } }
	if (!SkyLight)  { for (TActorIterator<ASkyLight> It(World); It; ++It) { SkyLight = *It; break; } }
	if (!HeightFog) { for (TActorIterator<AExponentialHeightFog> It(World); It; ++It) { HeightFog = *It; break; } }
}

void AAOSOceanDepthController::CaptureBaseline()
{
	if (Sun && Sun->GetLightComponent())
	{
		BaseSunIntensity = Sun->GetLightComponent()->Intensity;
		BaseSunVolumetric = Sun->GetLightComponent()->VolumetricScatteringIntensity;
	}
	if (SkyLight && SkyLight->GetLightComponent())
	{
		BaseSkyIntensity = SkyLight->GetLightComponent()->Intensity;
		BaseSkyVolumetric = SkyLight->GetLightComponent()->VolumetricScatteringIntensity;
	}
	if (WaterBody && WaterBody->GetWaterBodyComponent())
	{
		UnderwaterMID = WaterBody->GetWaterBodyComponent()->GetUnderwaterPostProcessMaterialInstance();
		if (UnderwaterMID)
		{
			UnderwaterMID->GetVectorParameterValue(FHashedMaterialParameterInfo(AOSOceanParams::FogAmbientColor), PPAmbientColor);
			UnderwaterMID->GetVectorParameterValue(FHashedMaterialParameterInfo(AOSOceanParams::FogScatterColor), PPScatterColor);
		}
	}
	bHasBaseline = true;
}

bool AAOSOceanDepthController::GetViewLocation(FVector& OutLocation) const
{
	if (const APlayerCameraManager* Camera = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		OutLocation = Camera->GetCameraLocation();
		return true;
	}
	return false;
}

float AAOSOceanDepthController::GetWaterSurfaceZ(const FVector& At) const
{
	if (WaterBody)
	{
		if (const UWaterBodyComponent* Body = WaterBody->GetWaterBodyComponent())
		{
			// Wave-aware surface height (PDF: z_wave). GetWaterSurfaceInfoAtLocation() only returns the flat
		// water plane, so the query must explicitly include the Gerstner waves.
		const TValueOrError<FWaterBodyQueryResult, EWaterBodyQueryError> Query = Body->TryQueryWaterInfoClosestToWorldLocation(
			At, EWaterBodyQueryFlags::ComputeLocation | EWaterBodyQueryFlags::IncludeWaves);
		if (Query.HasValue())
		{
			return Query.GetValue().GetWaterSurfaceLocation().Z;
		}
		}
		return WaterBody->GetActorLocation().Z;
	}
	return 0.f;
}

void AAOSOceanDepthController::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bHasBaseline)
	{
		return;
	}

	FVector View;
	if (!GetViewLocation(View))
	{
		return;
	}

	const float RawDepthM = (GetWaterSurfaceZ(View) - View.Z) / 100.f;
	const bool bUnderwater = RawDepthM > 0.f;
	const float TargetDepthM = FMath::Max(RawDepthM, 0.f);
	SmoothedDepthM = (DepthSmoothingSpeed > 0.f)
		? FMath::FInterpTo(SmoothedDepthM, TargetDepthM, DeltaSeconds, DepthSmoothingSpeed)
		: TargetDepthM;

	const bool bCrossed = LastUnderwater != int8(bUnderwater);
	if (bCrossed || FMath::Abs(SmoothedDepthM - LastAppliedDepthM) > AOSOceanParams::ReapplyDepthStepM)
	{
		Apply(bUnderwater, SmoothedDepthM);
	}
}

void AAOSOceanDepthController::ApplyFogPreset(const FAOSFogPreset& Preset, float InscatterScale)
{
	UExponentialHeightFogComponent* Fog = HeightFog ? HeightFog->GetComponent() : nullptr;
	if (!Fog)
	{
		return;
	}
	Fog->SetFogDensity(Preset.Density);
	Fog->SetFogHeightFalloff(Preset.HeightFalloff);
	Fog->SetFogInscatteringColor(Preset.Inscattering * InscatterScale);
	Fog->SetFogMaxOpacity(Preset.MaxOpacity);
	Fog->SetVolumetricFogAlbedo(Preset.VolumetricAlbedo);
	Fog->SetVolumetricFogExtinctionScale(Preset.VolumetricExtinctionScale);
	Fog->SetVolumetricFogScatteringDistribution(Preset.VolumetricScatteringDistribution);
}

void AAOSOceanDepthController::Apply(bool bUnderwater, float DepthM)
{
	LastUnderwater = int8(bUnderwater);
	LastAppliedDepthM = DepthM;

	float Aphotic = 1.f;
	if (bUnderwater)
	{
		SunFactor = FMath::Exp(-KdParPerMeter * DepthM);                                   // Beer-Lambert
		Aphotic = 1.f - FMath::SmoothStep(AphoticFadeStartM, MesopelagicBottomM, DepthM);  // aphotic zone
		AmbientFactor = SunFactor * Aphotic;
		CurrentZone = DepthM < EpipelagicBottomM ? EAOSOceanZone::Epipelagic
			: DepthM < MesopelagicBottomM ? EAOSOceanZone::Mesopelagic
			: EAOSOceanZone::Bathypelagic;
	}
	else
	{
		SunFactor = 1.f;
		AmbientFactor = 1.f;
		CurrentZone = EAOSOceanZone::Surface;
	}

	if (ULightComponent* SunLight = Sun ? Sun->GetLightComponent() : nullptr)
	{
		// Surfaces get exp(-Kd z) per pixel from the light function; here only the global cut-off,
		// so Lumen does not bounce sunlight into the aphotic zone and VSM pages are freed.
		// Energy-conserving caustics: boost by 1 / mean(LF) where the caustic pattern is active.
		float CausticCompensation = 1.f;
		if (bUnderwater)
		{
			const float Fade = FMath::Exp(-DepthM / FMath::Max(CausticExtinctionDepthM, 0.1f))
				* (1.f - FMath::SmoothStep(CausticCutStartM, CausticCutEndM, DepthM));
			CausticCompensation = 1.f / FMath::Max(1.f - Fade * (1.f - CausticMeanTransmission), 0.05f);
		}
		SunLight->SetIntensity(BaseSunIntensity * Aphotic * CausticCompensation);
		SunLight->SetVisibility(Aphotic > KINDA_SMALL_NUMBER);
		SunLight->SetVolumetricScatteringIntensity(bUnderwater
			? SunVolumetricScatteringUnderwater * SunFactor * Aphotic
			: BaseSunVolumetric);
	}

	if (USkyLightComponent* Sky = SkyLight ? SkyLight->GetLightComponent() : nullptr)
	{
		Sky->SetIntensity(BaseSkyIntensity * AmbientFactor);
		Sky->SetVolumetricScatteringIntensity(BaseSkyVolumetric * AmbientFactor);
	}

	ApplyFogPreset(bUnderwater ? WaterFog : AirFog, AmbientFactor);

	if (bUnderwater && WaterBody && WaterBody->GetWaterBodyComponent())
	{
		UWaterBodyComponent* Body = WaterBody->GetWaterBodyComponent();

		// Exposure floor follows the light field: daylight-compatible in the epipelagic, black in the abyss.
		FPostProcessSettings& PP = Body->UnderwaterPostProcessSettings.PostProcessSettings;
		PP.bOverride_AutoExposureMinBrightness = true;
		PP.bOverride_AutoExposureMaxBrightness = true;
		PP.AutoExposureMinBrightness = FMath::Lerp(ExposureMinEVSurface, ExposureMinEVDeep,
			FMath::SmoothStep(EpipelagicBottomM, MesopelagicBottomM, DepthM));
		PP.AutoExposureMaxBrightness = ExposureMaxEV;

		// Re-fetch: the water body recreates its MID when its materials are rebuilt. This call also copies
		// UnderwaterPostProcessSettings into the transient settings used by the renderer.
		UnderwaterMID = Body->GetUnderwaterPostProcessMaterialInstance();
		if (UnderwaterMID)
		{
			FLinearColor Ambient = PPAmbientColor;
			Ambient.A = PPFogAmbientIntensity * AmbientFactor;
			FLinearColor Scatter = PPScatterColor;
			Scatter.A = PPFogScatterIntensity * SunFactor * Aphotic;
			UnderwaterMID->SetVectorParameterValue(AOSOceanParams::FogAmbientColor, Ambient);
			UnderwaterMID->SetVectorParameterValue(AOSOceanParams::FogScatterColor, Scatter);
		}
	}
}
