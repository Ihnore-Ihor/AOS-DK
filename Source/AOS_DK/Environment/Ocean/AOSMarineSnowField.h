#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSMarineSnowField.generated.h"

class UProceduralMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class AWaterBody;
class ADirectionalLight;
class USpotLightComponent;

/**
 * Marine snow (organic detritus) around the camera - one draw call, zero per-particle CPU work.
 *
 * Architecture
 *  - A single procedural mesh with N camera-facing quads is built once at BeginPlay. Every quad stores a
 *    world-fixed seed position (its local vertex position inside one Box period) + per-particle random data.
 *  - M_MarineSnow_AOS (masked, unlit, two-sided) wraps each seed into a Box centred on the camera in WPO:
 *        c = Cam + (frac((P0 + Drift*t - Cam) / Box) - 0.5) * Box
 *    so particles are fixed in the water (true parallax = sense of speed) yet the field is infinite, and the
 *    1 x 1 x 1.6 km level costs exactly one Box of particles. The actor only moves its bounds with the camera.
 *  - Lighting is analytic in the pixel shader (no lit translucency, no shadow / Lumen cost):
 *    two headlight cones (taken from the view target's spot lights) + depth-attenuated sun, both weighted by the
 *    two-term Henyey-Greenstein phase from the optics reference (g1 = 0.92, g2 = -0.35, alpha = 0.98).
 *    Opaque masked output writes depth, so the underwater post process absorbs each flake by its own distance.
 *  - Motion streaks: quads are stretched along the camera velocity projected on the screen.
 */
UCLASS(ClassGroup = "AOS_DK", meta = (DisplayName = "AOS Marine Snow Field"))
class AOS_DK_API AAOSMarineSnowField : public AActor
{
	GENERATED_BODY()

public:
	AAOSMarineSnowField();

	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|MarineSnow")
	TObjectPtr<UMaterialInterface> SnowMaterial;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow|Refs")
	TObjectPtr<AWaterBody> WaterBody;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow|Refs")
	TObjectPtr<ADirectionalLight> Sun;

	/** Particles at Epic effects quality (scaled down for lower scalability levels). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow", meta = (ClampMin = "500", ClampMax = "60000"))
	int32 ParticleCount = 20000;

	/** Edge of the wrapping cube around the camera, cm. 4000 = flakes up to 20 m (headlight reach). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow", meta = (ClampMin = "500", Units = "cm"))
	float BoxSize = 4000.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow")
	int32 RandomSeed = 1337;

	/** Slow ocean current carrying the detritus, cm/s (z < 0: sinking). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow")
	FVector DriftVelocity = FVector(3.f, 1.5f, -0.6f);

	/** Headlight lumens -> shader units. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow|Light", meta = (ClampMin = "0"))
	float HeadlightScale = 0.001f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow|Light", meta = (ClampMin = "0"))
	float SunScale = 0.0005f;

	/** Fraction of flakes kept right below the surface (wave-mixed layer breaks marine-snow aggregates). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow|Waves", meta = (ClampMin = "0", ClampMax = "1"))
	float SurfaceDensity = 0.25f;

	/** Depth below the local wave surface where the full flake density is reached, cm. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow|Waves", meta = (ClampMin = "1", Units = "cm"))
	float FullDensityDepth = 2500.f;

	/** Flakes closer than this to the local wave surface are removed (never rendered in air), cm. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow|Waves", meta = (ClampMin = "0", Units = "cm"))
	float SurfaceClearance = 20.f;

	/** Camera velocity smoothing (1/s). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|MarineSnow", meta = (ClampMin = "0"))
	float VelocitySmoothing = 10.f;

protected:
	virtual void BeginPlay() override;

private:
	void BuildMesh(int32 Count);
	void ResolveReferences();
	float GetWaterSurfaceZ(const FVector& At) const;
	void UpdateHeadlights(const AActor* ViewTarget);
	void SetupWaves();
	FVector ComputeWaterOrbitalVelocity(const FVector& At, float WaveTime) const;

	/** Gerstner waves of the ocean (same data the GPU water mesh and the buoyancy use). */
	struct FSnowWave
	{
		FVector2D WaveVector;  // k * direction, 1/cm
		FVector2D Direction;
		float Speed = 0.f;     // angular frequency, rad/s
		float Amplitude = 0.f; // cm
		float Q = 0.f;         // horizontal (steepness) amplitude, cm
		float K = 0.f;         // wave number, 1/cm
	};
	TArray<FSnowWave> Waves;
	float WaveBaseZ = 0.f;

	UPROPERTY(VisibleAnywhere, Category = "AOS_DK|MarineSnow")
	TObjectPtr<UProceduralMeshComponent> Mesh;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> SnowMID;

	FVector PrevCameraLocation = FVector::ZeroVector;
	FVector SmoothedCameraVelocity = FVector::ZeroVector;
	bool bHasPrevCamera = false;
	bool bVisibleUnderwater = false;
};
