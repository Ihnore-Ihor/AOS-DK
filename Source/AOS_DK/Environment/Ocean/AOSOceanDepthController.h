#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSOceanDepthController.generated.h"

class AWaterBody;
class ADirectionalLight;
class ASkyLight;
class AExponentialHeightFog;
class UMaterialInstanceDynamic;

UENUM(BlueprintType)
enum class EAOSOceanZone : uint8
{
	Surface        UMETA(DisplayName = "Surface (air)"),
	Epipelagic     UMETA(DisplayName = "Epipelagic 0-40 m"),
	Mesopelagic    UMETA(DisplayName = "Mesopelagic 40-150 m"),
	Bathypelagic   UMETA(DisplayName = "Bathypelagic 150-1600 m")
};

/** Height-fog preset swapped when the camera crosses the waterline. */
USTRUCT(BlueprintType)
struct FAOSFogPreset
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite) float Density = 0.05f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float HeightFalloff = 0.001f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FLinearColor Inscattering = FLinearColor(0.01f, 0.08f, 0.18f);
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float MaxOpacity = 1.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) FColor VolumetricAlbedo = FColor(82, 223, 255);
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float VolumetricExtinctionScale = 2.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float VolumetricScatteringDistribution = 0.75f;
};

/**
 * Vertical stratification of the open ocean around the tower (0 - 1600 m), driven by the camera depth.
 *
 *  - Epipelagic  (0-40 m):   sun shafts in Volumetric Fog, LF caustics (spatial, in M_LF_OceanCaustics_AOS).
 *  - Mesopelagic (40-150 m): ambient = exp(-Kd_PAR * z), Kd_PAR(Jerlov II) = 0.0725 1/m (1 % at ~63 m).
 *  - Bathypelagic (>150 m):  sun + sky = 0; only headlights, tower beacons and emissive Dracula accents.
 *
 * Surfaces are attenuated per pixel by the sun light function; this actor scales what a light function
 * cannot reach (sky light, volumetric fog, Lumen bounce, the underwater PP fog colours).
 * Runtime only (PIE / game) - the level keeps the epipelagic values set by Tools/aos_ocean_setup.py.
 */
UCLASS(ClassGroup = "AOS_DK", meta = (DisplayName = "AOS Ocean Depth Controller"))
class AOS_DK_API AAOSOceanDepthController : public AActor
{
	GENERATED_BODY()

public:
	AAOSOceanDepthController();

	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Ocean")
	float GetCameraDepthMeters() const { return SmoothedDepthM; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Ocean")
	EAOSOceanZone GetCurrentZone() const { return CurrentZone; }

	// --- Scene references (auto-found when empty) ----------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Ocean|Refs")
	TObjectPtr<AWaterBody> WaterBody;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Ocean|Refs")
	TObjectPtr<ADirectionalLight> Sun;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Ocean|Refs")
	TObjectPtr<ASkyLight> SkyLight;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Ocean|Refs")
	TObjectPtr<AExponentialHeightFog> HeightFog;

	// --- Optics (PDF: Jerlov II) ----------------------------------------------------------------
	/** Diffuse attenuation of PAR, 1/m: mean Kd(525 nm, 460 nm) of Jerlov II = (0.080 + 0.065) / 2. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Ocean|Optics", meta = (ClampMin = "0.001"))
	float KdParPerMeter = 0.0725f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Ocean|Optics", meta = (Units = "m"))
	float EpipelagicBottomM = 40.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Ocean|Optics", meta = (Units = "m"))
	float MesopelagicBottomM = 150.f;

	/** Sun / sky are faded to exact zero between this depth and MesopelagicBottomM (aphotic zone). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Ocean|Optics", meta = (Units = "m"))
	float AphoticFadeStartM = 120.f;

	/** Directional light volumetric scattering in the epipelagic (PDF 4.0-7.0). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Ocean|Light", meta = (ClampMin = "0"))
	float SunVolumetricScatteringUnderwater = 5.f;

	// --- Fog presets ------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Ocean|Fog")
	FAOSFogPreset WaterFog;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Ocean|Fog")
	FAOSFogPreset AirFog;

	// --- Underwater PP (WaterBody MID) intensities, the colours live in MI_UnderwaterPostProcess_AOS -----
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Ocean|PostProcess", meta = (ClampMin = "0"))
	float PPFogAmbientIntensity = 0.35f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Ocean|PostProcess", meta = (ClampMin = "0"))
	float PPFogScatterIntensity = 0.6f;

	/** Seconds-based smoothing of the depth (avoids popping when the camera bobs at the waterline). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Ocean", meta = (ClampMin = "0"))
	float DepthSmoothingSpeed = 6.f;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	void ResolveReferences();
	void CaptureBaseline();
	bool GetViewLocation(FVector& OutLocation) const;
	float GetWaterSurfaceZ(const FVector& At) const;
	void ApplyFogPreset(const FAOSFogPreset& Preset, float InscatterScale);
	void Apply(bool bUnderwater, float DepthM);

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> UnderwaterMID;

	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Ocean|Debug")
	float SmoothedDepthM = 0.f;

	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Ocean|Debug")
	float SunFactor = 1.f;

	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Ocean|Debug")
	float AmbientFactor = 1.f;

	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Ocean|Debug")
	EAOSOceanZone CurrentZone = EAOSOceanZone::Surface;

	float BaseSunIntensity = 0.f;
	float BaseSunVolumetric = 1.f;
	float BaseSkyIntensity = 1.f;
	float BaseSkyVolumetric = 1.f;
	FLinearColor PPAmbientColor = FLinearColor(0.01f, 0.08f, 0.18f, 1.f);
	FLinearColor PPScatterColor = FLinearColor(0.05f, 0.35f, 0.65f, 0.6f);

	bool bHasBaseline = false;
	int8 LastUnderwater = -1;
	float LastAppliedDepthM = -1.f;
};
