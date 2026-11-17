#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSDayNightCycle.generated.h"

class ADirectionalLight;
class AAOSOceanDepthController;
class UPostProcessComponent;

/**
 * 24 h clock compressed into DayLengthMinutes. Single writer of the Sun / Moon ROTATIONS.
 * Publishes DayFactor / NightFactor to UAOSEnvironmentStateSubsystem; never sets the sun intensity
 * (AAOSOceanDepthController multiplies the subsystem scales in). Only the moon's own intensity is set here.
 * Console: aos.env.TimeOfDay <h>, aos.env.DayLengthMin <m>, aos.env.Pause 0|1.
 *
 * Smoothness: sun / moon rotations are written EVERY frame (the clock is continuous); only the heavier publishing
 * (moon intensity, DayFactor / NightFactor, forward-shading priority) runs at UpdateHz.
 * Forward shading: the sun and the moon both overlap at dusk / dawn, so the engine warned that several directional
 * lights compete. The brighter of the two always gets ForwardShadingPriority 1, the other 0.
 *
 * Night exposure: the histogram auto-exposure (project range -10..+20 EV) otherwise re-brightens the moonlit
 * atmosphere to daytime levels. An unbound PostProcessComponent pins Min = Max brightness to NightExposureEV with
 * BlendWeight = NightFactor (0 by day => the calibrated daytime/Ocean Optics look is untouched). Priority is below
 * the water body's underwater post-process, so the ocean controller's own exposure floor still wins when submerged.
 */
UCLASS(ClassGroup = "AOS_DK", meta = (DisplayName = "AOS Day Night Cycle"))
class AOS_DK_API AAOSDayNightCycle : public AActor
{
	GENERATED_BODY()

public:
	AAOSDayNightCycle();

	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Env")
	void SetTimeOfDay(float Hour);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Env")
	float GetTimeOfDay() const { return TimeOfDayH; }

	/** Atmosphere sun light (index 0). Auto-found when empty. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Env|Refs")
	TObjectPtr<ADirectionalLight> Sun;

	/** Atmosphere sun light index 1 (DL_Moon). Auto-found when empty. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Env|Refs")
	TObjectPtr<ADirectionalLight> Moon;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Env|Refs")
	TObjectPtr<AAOSOceanDepthController> OceanController;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Env|Clock", meta = (ClampMin = "0", ClampMax = "24"))
	float StartTimeOfDay = 15.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Env|Clock", meta = (ClampMin = "0.05"))
	float DayLengthMinutes = 12.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Env|Clock")
	bool bPaused = false;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Env|Solar", meta = (ClampMin = "-90", ClampMax = "90"))
	float LatitudeDeg = 8.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Env|Solar", meta = (ClampMin = "-24", ClampMax = "24"))
	float DeclinationDeg = 0.f;

	/** Solved at BeginPlay so that the 15:00 sun yaw equals the authored sun yaw (Ocean Optics regression). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Env|Solar")
	bool bSolveAzimuthOffset = true;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Env|Solar")
	float SunAzimuthOffsetDeg = 0.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Env|Moon", meta = (ClampMin = "0"))
	float MoonIntensity = 0.6f;

	/** Apparent moon disk diameter in degrees (the real moon is 0.5; the atmosphere disk is drawn from LightSourceAngle). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Env|Moon", meta = (ClampMin = "0.1", ClampMax = "12"))
	float MoonSourceAngleDeg = 4.5f;

	/** Atmosphere disk colour multiplier for the moon (a bigger disk is dimmer per pixel; keep it near 1-2). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Env|Moon", meta = (ClampMin = "0"))
	float MoonDiskColorScale = 1.5f;

	/**
	 * Storm overcast hides the moon. The moonlight and its atmosphere disk (the disk is drawn by the sky from the light itself, so a
	 * dimmed-but-visible light still shows through gaps / thin spots of the volumetric cloud layer) fade to zero between these two
	 * StormAlpha values and come back when the sky clears. 0 / 0 disables the fade.
	 */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Env|Moon", meta = (ClampMin = "0", ClampMax = "1"))
	float MoonStormFadeStartAlpha = 0.02f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Env|Moon", meta = (ClampMin = "0", ClampMax = "1"))
	float MoonStormFadeEndAlpha = 0.35f;

	/** Rate of the heavy publish step (intensity, factors, priority). Rotations are per-frame regardless. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Env|Update", meta = (ClampMin = "1", ClampMax = "60"))
	float UpdateHz = 10.f;

	/** Fixed EV100 used at full night (Min = Max brightness). Higher = darker night. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Env|Night", meta = (ClampMin = "-6", ClampMax = "10"))
	float NightExposureEV = 1.f;

	/** Disable to fall back to the project default auto-exposure at night. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Env|Night")
	bool bClampNightExposure = true;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|Env|Night")
	TObjectPtr<UPostProcessComponent> NightExposure;

protected:
	virtual void BeginPlay() override;

private:
	void ResolveReferences();
	/** Returns elevation / azimuth (deg, azimuth from north clockwise) for a clock hour. */
	void SolveSun(float Hour, float& OutElevationDeg, float& OutAzimuthDeg) const;
	/** Per-frame: solves the sun and writes the sun / moon rotations. Returns the sun elevation (deg). */
	float UpdateOrientation();
	/** Heavy step: orientation + moon intensity + forward-shading priority + published factors. */
	void Step();
	void ApplyForwardShadingPriority(bool bMoonLeads);

	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Env|Debug")
	float TimeOfDayH = 15.f;

	UPROPERTY(VisibleInstanceOnly, Category = "AOS_DK|Env|Debug")
	float SunElevationDeg = 0.f;

	float Accum = 0.f;
	float LastMoonIntensity = -1.f;
	/** -1 = never applied, 0 = sun leads, 1 = moon leads. */
	int32 ForwardLead = -1;
};
