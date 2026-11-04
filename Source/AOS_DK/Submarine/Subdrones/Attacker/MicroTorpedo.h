#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Engine/EngineTypes.h"
#include "MicroTorpedo.generated.h"

class UStaticMeshComponent;
class UNiagaraComponent;
class UNiagaraSystem;
class UDamageType;

/** Ballistics of the cavitation micro-torpedo. Units: cm, s, cm/s, cm/s^2. */
USTRUCT(BlueprintType)
struct FMicroTorpedoBallistics
{
	GENERATED_BODY()

	/** Coasting phase after leaving the magnetic ring (no thrust, no steering). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Release", meta = (ClampMin = "0", Units = "s"))
	float EjectDuration = 0.09f;

	/** Exponential velocity decay during the coasting phase (water drag of a still-wetted body). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Release", meta = (ClampMin = "0"))
	float EjectDragPerSec = 5.f;

	/** Rocket/hydro-jet acceleration at full thrust. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Propulsion", meta = (ClampMin = "0"))
	float ThrustAccel = 7000.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Propulsion", meta = (ClampMin = "0.001", Units = "s"))
	float ThrustRampTime = 0.1f;

	/** Quadratic drag coefficient of the wetted body (1/cm). Terminal speed = sqrt(Thrust / C). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cavitation", meta = (ClampMin = "0"))
	float WettedDragCoeff = 0.0014f;

	/** Quadratic drag inside the vapour cavity (~10x lower). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cavitation", meta = (ClampMin = "0"))
	float CavitatingDragCoeff = 0.00016f;

	/** Speed at which the flat cavitator wraps the body in a vapour-gas bubble. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cavitation", meta = (ClampMin = "1", Units = "CentimetersPerSecond"))
	float CavitationOnsetSpeed = 1700.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Cavitation", meta = (ClampMin = "1", Units = "CentimetersPerSecond"))
	float CavitationBlendWidth = 500.f;

	/** Proportional navigation constant N (3..5 typical). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Guidance", meta = (ClampMin = "0"))
	float NavigationConstant = 4.f;

	/** Pure-pursuit gain used while the heading error is large (radial ejection). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Guidance", meta = (ClampMin = "0"))
	float PursuitGain = 7.f;

	/** Thrust vectoring: max angle between the jet and the velocity, steering the slow, freshly
	 *  slung needle back towards the target (keeps the release "bloom" around 1-1.5 m). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Guidance", meta = (ClampMin = "0", ClampMax = "90", Units = "Degrees"))
	float MaxThrustVectorAngle = 45.f;

	/** Structural lateral-acceleration limit -> defines the arc radius (v^2 / a). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Guidance", meta = (ClampMin = "0"))
	float MaxLateralAccel = 30000.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fuse", meta = (ClampMin = "0", Units = "cm"))
	float ProximityFuseRadius = 45.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fuse", meta = (ClampMin = "0", Units = "s"))
	float ArmingTime = 0.06f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fuse", meta = (ClampMin = "0.1", Units = "s"))
	float MaxLifetime = 3.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Simulation", meta = (ClampMin = "0.1", Units = "cm"))
	float CollisionRadius = 1.5f;

	/** Upper bound of a simulation sub-step (high speed -> sub-stepped integration + swept collision). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Simulation", meta = (ClampMin = "0.001", Units = "s"))
	float MaxSubstep = 1.f / 120.f;

	/** Visual roll of the needle around its axis. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Simulation")
	float VisualRollDegPerSec = 900.f;
};

/**
 * Cavitation micro-torpedo. Pooled by its ASubDrone_Attacker (never destroyed during combat).
 * Flight: magnetic sling release -> short wetted coast -> ignition -> supercavitation
 * (drag drops ~10x) -> guided arc (proportional navigation + pursuit blend) -> swept impact.
 */
UCLASS(Blueprintable)
class AOS_DK_API AMicroTorpedo : public AActor
{
	GENERATED_BODY()

public:
	AMicroTorpedo();

	virtual void Tick(float DeltaSeconds) override;

	void Launch(const FVector& Location, const FQuat& Rotation, const FVector& InitialVelocity,
		const FVector& TargetPoint, AActor* InTargetActor);

	bool IsInFlight() const { return bInFlight; }
	bool IsAvailableForReuse(double Now) const { return !bInFlight && Now >= ReuseAvailableTime; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Torpedo")
	bool IsCavitating() const { return bCavitating; }

protected:
	virtual void BeginPlay() override;

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Torpedo", meta = (DisplayName = "On Launched"))
	void BP_OnLaunched();

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Torpedo", meta = (DisplayName = "On Cavitation Started"))
	void BP_OnCavitationStarted();

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Torpedo", meta = (DisplayName = "On Detonated"))
	void BP_OnDetonated(const FHitResult& Hit, bool bHitSomething);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Mesh;

	/** NS_TorpedoCavitation: cavity sheath (User.SheathRate) + world-space bubble wake. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UNiagaraComponent> TrailFX;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Torpedo")
	FMicroTorpedoBallistics Ballistics;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Torpedo|Damage")
	float Damage = 14.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Torpedo|Damage")
	TSubclassOf<UDamageType> DamageType;

	/** Channel used for the swept collision (hits whatever blocks WorldDynamic). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Torpedo|Damage")
	TEnumAsByte<ECollisionChannel> CollisionChannel = ECC_WorldDynamic;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Torpedo|FX")
	TObjectPtr<UNiagaraSystem> ImpactFX;

	/** Time the actor stays parked after impact so the world-space bubble trail can fade. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Torpedo|FX", meta = (ClampMin = "0", Units = "s"))
	float TrailLingerTime = 1.2f;

	/** Sheath particle rate at full supercavitation (User.SheathRate). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Torpedo|FX", meta = (ClampMin = "0"))
	float SheathMaxRate = 700.f;

	/** Sheath rate during the wetted coast (before the cavity forms). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Torpedo|FX", meta = (ClampMin = "0"))
	float SheathCoastRate = 60.f;

private:
	/** Integrates one sub-step in place (no actor transform update). Returns false if the fuse triggered. */
	bool IntegrateStep(float H, FVector& Pos, FVector& OutFuseTarget);
	FVector GetGuidanceTarget(FVector& OutTargetVelocity) const;
	void Detonate(const FHitResult& Hit, bool bHitSomething);
	void Retire();

	FVector Vel = FVector::ZeroVector;
	FQuat Heading = FQuat::Identity;
	float Age = 0.f;
	float RollDeg = 0.f;
	float CavitationAlpha = 0.f;
	bool bInFlight = false;
	bool bCavitating = false;
	double ReuseAvailableTime = 0.0;
	float LastSheathRate = -1.f;

	FVector TargetPointWorld = FVector::ZeroVector;
	FVector TargetLocalOffset = FVector::ZeroVector;
	TWeakObjectPtr<AActor> TargetActor;
	TArray<TWeakObjectPtr<AActor>> PenetrationIgnores;
};
