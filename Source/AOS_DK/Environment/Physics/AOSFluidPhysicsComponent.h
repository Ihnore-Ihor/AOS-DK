#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AOSFluidPhysicsComponent.generated.h"

class UPrimitiveComponent;

/** How the component turns fluid kinematics into motion of the driven body. */
UENUM(BlueprintType)
enum class EAOSFluidResponseModel : uint8
{
	/**
	 * Real masses: engine gravity (m*g) against Archimedes buoyancy (BuoyancyFactor*m*g*submersion);
	 * wave forcing obeys a = F_wave / m, so heavy bodies barely notice the chop. Props, cargo, debris.
	 */
	Newtonian           UMETA(DisplayName = "Newtonian (mass-scaled)"),

	/**
	 * Mass-agnostic acceleration control (the Shell's original hydrodynamics): neutral buoyancy underwater,
	 * all terms in cm/s^2. For powered vehicles whose handling is tuned in accelerations.
	 */
	VehicleAcceleration UMETA(DisplayName = "Vehicle (acceleration)")
};

/** One analytic Gerstner harmonic of the sea state (deep-water dispersion, omega = sqrt(g*k)). */
USTRUCT(BlueprintType)
struct AOS_DK_API FAOSWaveHarmonic
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics", meta = (ClampMin = "0", Units = "cm"))
	float Amplitude = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics", meta = (ClampMin = "1", Units = "cm"))
	float Wavelength = 1000.f;

	/** Propagation direction in the XY plane, degrees from +X. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics", meta = (Units = "deg"))
	float DirectionDeg = 0.f;

	/** Phase offset, radians. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics")
	float Phase = 0.f;

	FAOSWaveHarmonic() = default;
	FAOSWaveHarmonic(float InAmplitude, float InWavelength, float InDirectionDeg, float InPhase)
		: Amplitude(InAmplitude), Wavelength(InWavelength), DirectionDeg(InDirectionDeg), Phase(InPhase) {}
};

/** Result of one fluid query / simulation step. */
USTRUCT(BlueprintType)
struct AOS_DK_API FAOSFluidSample
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "AOS|FluidPhysics")
	bool bInWater = false;

	/** Wave-displaced surface height above the sample point (after mass coupling). */
	UPROPERTY(BlueprintReadOnly, Category = "AOS|FluidPhysics")
	float SurfaceZ = 0.f;

	/** Orbital water velocity at the sample point, cm/s (after mass coupling). */
	UPROPERTY(BlueprintReadOnly, Category = "AOS|FluidPhysics")
	FVector FluidVelocity = FVector::ZeroVector;

	/** Wave surface normal the body is rocked towards (after mass coupling). */
	UPROPERTY(BlueprintReadOnly, Category = "AOS|FluidPhysics")
	FVector WaveNormal = FVector::UpVector;

	/** Body angular velocity at the start of the step, rad/s. */
	UPROPERTY(BlueprintReadOnly, Category = "AOS|FluidPhysics")
	FVector AngularVelocity = FVector::ZeroVector;

	/** 0 = dry, 1 = fully submerged (Newtonian); 0/1 in the vehicle model. */
	UPROPERTY(BlueprintReadOnly, Category = "AOS|FluidPhysics")
	float Submersion = 0.f;

	/** 0..N share of the wave field that reaches the body (WaveInfluenceScale x mass inertia factor). */
	UPROPERTY(BlueprintReadOnly, Category = "AOS|FluidPhysics")
	float WaveCoupling = 0.f;
};

/**
 * Water interaction engine: analytic Gerstner sea state + hydrodynamic response of the owner's simulating
 * root primitive (or an explicitly assigned body).
 *  - Newtonian:  a_wave = F_wave / m  (F_wave = WaveReferenceMassKg * a_ref, saturating at full fluid following);
 *                bodies at/above WaveImmuneMassKg ignore the waves entirely. BuoyancyFactor < 1 sinks to the
 *                seabed, > 1 rises and floats with 1/BuoyancyFactor of its height submerged.
 *  - Vehicle:    bit-exact port of AShellPawn's original hydrodynamics (owner adds its own thrust/ballast).
 * Ticks by itself (bAutoSimulate) or is stepped by the owner via StepFluidPhysics for deterministic ordering.
 */
UCLASS(ClassGroup = (AOS), meta = (BlueprintSpawnableComponent, DisplayName = "AOS Fluid Physics"))
class AOS_DK_API UAOSFluidPhysicsComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UAOSFluidPhysicsComponent();

	virtual void OnRegister() override;
	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
#if WITH_EDITOR
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

	/** Applies one step of fluid forces to the driven body. Called from TickComponent when bAutoSimulate is on. */
	UFUNCTION(BlueprintCallable, Category = "AOS|FluidPhysics")
	FAOSFluidSample StepFluidPhysics(float DeltaTime);

	/** Raw (uncoupled) sea state at a world location, current world time. */
	UFUNCTION(BlueprintPure, Category = "AOS|FluidPhysics")
	FAOSFluidSample SampleFluidAt(const FVector& WorldLocation) const;

	UFUNCTION(BlueprintPure, Category = "AOS|FluidPhysics")
	float GetWaveHeightAt(const FVector& WorldLocation) const;

	/** Mean sea level (calm-water plane). */
	UFUNCTION(BlueprintPure, Category = "AOS|FluidPhysics")
	float GetOceanSurfaceZ() const { return OceanSurfaceZ; }

	/** MassOverrideKg if set, otherwise the driven body's simulated mass (kg). */
	UFUNCTION(BlueprintPure, Category = "AOS|FluidPhysics")
	float GetEffectiveMass() const;

	/** Share of the wave field acting on the body at its current mass. */
	UFUNCTION(BlueprintPure, Category = "AOS|FluidPhysics")
	float GetWaveCoupling() const;

	UFUNCTION(BlueprintPure, Category = "AOS|FluidPhysics")
	FAOSFluidSample GetLastSample() const { return LastSample; }

	UFUNCTION(BlueprintPure, Category = "AOS|FluidPhysics")
	UPrimitiveComponent* GetDrivenBody() const;

	/** Overrides the body to drive (default: the owner's root primitive). */
	UFUNCTION(BlueprintCallable, Category = "AOS|FluidPhysics")
	void SetDrivenBody(UPrimitiveComponent* NewBody);

	UFUNCTION(BlueprintCallable, Category = "AOS|FluidPhysics")
	void SetAutoSimulate(bool bEnabled);

	/** Vehicle model: unmanned hull floats on the waves (Archimedes spring) and aligns to the wave normal. */
	UFUNCTION(BlueprintCallable, Category = "AOS|FluidPhysics")
	void SetPassiveFlotation(bool bEnabled) { bPassiveFlotation = bEnabled; }

	UFUNCTION(BlueprintCallable, Category = "AOS|FluidPhysics")
	void SetWaveHarmonics(const TArray<FAOSWaveHarmonic>& NewHarmonics);

	/** Applies MassOverrideKg to the driven body (no-op when 0). */
	UFUNCTION(BlueprintCallable, Category = "AOS|FluidPhysics")
	void ApplyMassOverride();

	float GetRightingStiffness() const { return RightingStiffness; }

	//~ General ---------------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|FluidPhysics")
	EAOSFluidResponseModel ResponseModel = EAOSFluidResponseModel::Newtonian;

	/** Tick by itself (PrePhysics). Disable when the owner calls StepFluidPhysics from its own Tick. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|FluidPhysics")
	bool bAutoSimulate = true;

	//~ Water -----------------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Water", meta = (Units = "cm"))
	float OceanSurfaceZ = 0.f;

	/** Analytic sea state (defaults match the level's Gerstner water: A 10-200 cm, L 8-140 m, dominant 35 deg). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|FluidPhysics|Water")
	TArray<FAOSWaveHarmonic> WaveHarmonics;

	/** Global multiplier of the wave field felt by this body (heave, orbital drift, rocking). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Water", meta = (ClampMin = "0"))
	float WaveInfluenceScale = 1.f;

	//~ Mass (Newtonian) -----------------------------------------------------------------------------
	/** > 0: forces this mass on the body at BeginPlay (collisions and fluid response). 0: use the body's mass. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Mass", meta = (ClampMin = "0", Units = "kg"))
	float MassOverrideKg = 0.f;

	/** Bodies at or below this mass follow the waves fully; above it, wave acceleration falls off as Ref/m. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Mass", meta = (ClampMin = "0.1", Units = "kg"))
	float WaveReferenceMassKg = 50.f;

	/** Wave forcing fades out between 0.5x and 1x this mass and is exactly zero above it (0 disables the cutoff). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Mass", meta = (ClampMin = "0", Units = "kg"))
	float WaveImmuneMassKg = 1000.f;

	/** Displaced-water weight / body weight when fully submerged. < 1 sinks, 1 neutral, > 1 rises and floats. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Mass", meta = (ClampMin = "0"))
	float BuoyancyFactor = 1.5f;

	/** Half height used for the submerged fraction. 0 = derive from the body bounds. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Mass", meta = (ClampMin = "0", Units = "cm"))
	float SubmersionHalfHeight = 0.f;

	//~ Drag (both models) --------------------------------------------------------------------------
	/** Linear drag rate against the relative water velocity, 1/s. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Drag", meta = (ClampMin = "0"))
	float FluidDrag = 1.0f;

	/** Quadratic (form) drag, 1/cm: terminal rise/sink speed of props (~5 m/s for a 4x buoyant drum). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Drag", meta = (ClampMin = "0"))
	float FluidQuadraticDrag = 0.01f;

	/** Rotational damping rate, 1/s. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Drag", meta = (ClampMin = "0"))
	float AngularFluidDrag = 2.5f;

	/**
	 * Newtonian: damping of the waterline heave spring as a fraction of critical damping
	 * (omega = sqrt(BuoyancyFactor * g / (2 * HalfHeight))). 1 = no bobbing, 0 = undamped.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Drag", meta = (ClampMin = "0", ClampMax = "2"))
	float HeaveDampingRatio = 0.7f;

	/** Metacentric restoring stiffness towards the (mass-coupled) wave normal, rad/s^2. 0 = none. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Drag", meta = (ClampMin = "0"))
	float RightingStiffness = 4.f;

	//~ Vehicle model ---------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Vehicle")
	bool bPassiveFlotation = true;

	/** Residual gravity while piercing the surface (fades to 0 over SurfaceEntryDepth), cm/s^2. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Vehicle", meta = (ClampMin = "0"))
	float SurfaceEntryGravity = 980.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Vehicle", meta = (ClampMin = "1", Units = "cm"))
	float SurfaceEntryDepth = 150.f;

	/** Passive flotation: the hull rides this far below the local wave surface. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Vehicle", meta = (Units = "cm"))
	float FlotationDraft = 25.f;

	/** Passive flotation spring acts only within this depth of the surface; deeper, the heave is braked. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Vehicle", meta = (ClampMin = "0", Units = "cm"))
	float FlotationCaptureDepth = 500.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Vehicle", meta = (ClampMin = "0"))
	float FlotationStiffness = 5.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Vehicle", meta = (ClampMin = "0"))
	float FlotationDamping = 2.f;

	/** Deep parking brake on vertical velocity below the capture band, 1/s. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS|FluidPhysics|Vehicle", meta = (ClampMin = "0"))
	float DeepHeaveBrake = 4.f;

private:
	struct FWaveRuntime
	{
		float Amplitude = 0.f;
		float K = 0.f;
		float Omega = 0.f;
		FVector2D Direction = FVector2D(1.0, 0.0);
		float PhaseOffset = 0.f;
	};

	void RebuildWaveSpectrum();
	void EvaluateWaves(const FVector& Location, float Time, bool bDecayNormalWithDepth,
		float& OutSurfaceZ, FVector& OutFluidVel, FVector& OutWaveNormal) const;
	float ComputeWaveCoupling(float Mass) const;
	void ApplyWaveCoupling(float Coupling, float& InOutSurfaceZ, FVector& InOutFluidVel, FVector& InOutNormal) const;
	float GetWaveTime() const;

	FAOSFluidSample StepVehicle(UPrimitiveComponent* Body, float DeltaTime);
	FAOSFluidSample StepNewtonian(UPrimitiveComponent* Body, float DeltaTime);

	UPROPERTY(Transient)
	TWeakObjectPtr<UPrimitiveComponent> DrivenBody;

	TArray<FWaveRuntime> WaveRuntime;
	FAOSFluidSample LastSample;
	bool bWarnedNotSimulating = false;
};
