#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Curves/RichCurve.h"
#include "AOSGateBeacon.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class USpotLightComponent;
class URotatingMovementComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;

/**
 * Breakwater gate marker beacon (Lab 6 / Task 3 UE-native object U1).
 *
 * Hierarchy: Root -> BaseMesh (housing), YawPivot (URotatingMovementComponent, yaw) -> LensHead (mesh, tilt pitch)
 *            -> SpotFront / SpotBack (back-to-back, 180 deg apart).
 * Gating (polled every PollInterval s): ON when max(NightFactor, StormAlpha) of UAOSEnvironmentStateSubsystem > OnThreshold,
 * OFF again below OnThreshold - Hysteresis. ON  = yaw 90 deg/s, 4 s Flash/Tilt loop, lights at full pulse.
 *                                            OFF = yaw IdleYawRateDegPerSec, lights at OffIntensityFraction, pulse frozen.
 * OnAlpha ramps over RampTime so the transition has no pop. The visual child Blueprint (BP_AOS_GateBeacon) only assigns materials.
 */
UCLASS(ClassGroup = "AOS_DK", meta = (DisplayName = "AOS Gate Beacon"))
class AOS_DK_API AAOSGateBeacon : public AActor
{
	GENERATED_BODY()

public:
	AAOSGateBeacon();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** True while the beacon is switched on (dusk / night / storm). */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Beacon")
	bool IsBeaconOn() const { return bBeaconOn; }

	/** 0..1 ramp towards the on state (1 = fully on). */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Beacon")
	float GetOnAlpha() const { return OnAlpha; }

	/** Current yaw rate of the rotating movement component, deg/s. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Beacon")
	float GetYawRateDegPerSec() const;

	/** Pulse curve value (0..1) used for the current frame. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Beacon")
	float GetFlash() const { return CurrentFlash; }

	/** Current spot light intensity (cd) of the front spot. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Beacon")
	float GetSpotIntensity() const;

	/** Current lens pitch tilt, degrees. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Beacon")
	float GetTiltDeg() const { return CurrentTiltDeg; }

	/** Position inside the 4 s loop. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Beacon")
	float GetPulseTime() const { return PulseTime; }

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|Beacon|Components")
	TObjectPtr<UStaticMeshComponent> BaseMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|Beacon|Components")
	TObjectPtr<USceneComponent> YawPivot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|Beacon|Components")
	TObjectPtr<UStaticMeshComponent> LensHead;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|Beacon|Components")
	TObjectPtr<USpotLightComponent> SpotFront;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|Beacon|Components")
	TObjectPtr<USpotLightComponent> SpotBack;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|Beacon|Components")
	TObjectPtr<URotatingMovementComponent> Rotation;

	// ---- visual (set by the child Blueprint) -------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Visual")
	TObjectPtr<UMaterialInterface> HousingMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Visual")
	TObjectPtr<UMaterialInterface> LensMaterial;

	/** Scalar parameter of the lens material that carries the emissive multiplier. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Visual")
	FName LensEmissiveParam = TEXT("EmissiveIntensity");

	/** Lens emissive multiplier at Flash = 1 (the material's NightResponse still applies). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Visual", meta = (ClampMin = "0"))
	float LensEmissiveMax = 12.f;

	// ---- gating ------------------------------------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Gating", meta = (ClampMin = "0", ClampMax = "1"))
	float OnThreshold = 0.3f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Gating", meta = (ClampMin = "0", ClampMax = "0.3"))
	float Hysteresis = 0.03f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Gating", meta = (ClampMin = "0.05"))
	float PollInterval = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Gating", meta = (ClampMin = "0.05"))
	float RampTime = 1.f;

	// ---- motion / pulse ----------------------------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Motion")
	float OnYawRateDegPerSec = 90.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Motion")
	float IdleYawRateDegPerSec = 20.f;

	/** Loop length of the Flash / Tilt curves. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Motion", meta = (ClampMin = "0.5"))
	float PulsePeriod = 4.f;

	/** Per-instance offset into the loop so the three beacons do not flash in unison. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Motion")
	float PhaseOffsetSec = 0.f;

	/** Lens pitch amplitude of the sinusoidal tilt, degrees. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Motion", meta = (ClampMin = "0"))
	float TiltAmplitudeDeg = 2.f;

	// ---- lights ------------------------------------------------------------------------------------------------------------
	/** Spot intensity (cd) at Flash = 1 and fully on. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Light", meta = (ClampMin = "0"))
	float SpotIntensityMax = 150000.f;

	/** Fraction of SpotIntensityMax while switched off (spec: 5 %). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Light", meta = (ClampMin = "0", ClampMax = "1"))
	float OffIntensityFraction = 0.05f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Light")
	FLinearColor LightColor = FLinearColor(1.f, 0.82f, 0.55f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Light")
	float InnerConeDeg = 2.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Light")
	float OuterConeDeg = 8.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Light")
	float AttenuationRadius = 8000.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Beacon|Light")
	float VolumetricScattering = 2.f;

private:
	void PollEnvironment();
	void ApplyLights(float Flash);
	void ApplyStaticSettings();

	bool bBeaconOn = false;
	float OnAlpha = 0.f;
	float PulseTime = 0.f;
	float CurrentFlash = 0.f;
	float CurrentTiltDeg = 0.f;
	float PollAccum = 0.f;

	FRichCurve FlashCurve;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> LensMID;
};
