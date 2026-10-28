#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "AOS_DK/Core/Interfaces/Interactions/Interactable.h"
#include "ShellPawn.generated.h"

class UBoxComponent;
class UStaticMeshComponent;
class UCameraComponent;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

// Analytical representation of a Gerstner Wave harmonic
struct FGerstnerHarmonic
{
	float Amplitude;
	float K; // Wave number
	float Omega; // Angular frequency
	FVector2D Direction;
	float PhaseOffset;

	FGerstnerHarmonic(float InA, float InWavelength, float AngleDeg, float InPhase);
};

UCLASS()
class AOS_DK_API AShellPawn : public APawn, public IInteractable
{
	GENERATED_BODY()

public:
	AShellPawn();

	virtual void Tick(float DeltaTime) override;
	virtual void BeginPlay() override;
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;
	virtual void NotifyControllerChanged() override;
	virtual void Interact_Implementation(AActor* InstigatorActor) override;

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UBoxComponent> BoxRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UStaticMeshComponent> ShellMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UCameraComponent> FPCamera;

	//~ Inputs
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputMappingContext> SubMappingContext;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> MoveAction; // W/S, A/D

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> RotateAction; // Mouse X/Y, Q/E

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> BallastAction; // Shift/Space

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> StabilizeAction; // G

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> InteractAction;

	//~ Environment
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Water")
	float OceanSurfaceZ = 0.f;

	//~ Propulsion Configuration
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Thrust")
	float ForwardThrust = 1500.f; // Acceleration in cm/s^2 (approx 1.5G)

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Thrust")
	float LateralThrust = 500.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Thrust")
	float ThrustRampSpeed = 3.5f;

	//~ Steering Settings
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Control")
	bool bSwapYawAndRoll = false;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Control")
	float PitchSensitivity = 2.2f; // Angular acceleration in rad/s^2

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Control")
	float YawSensitivity = 2.0f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Control")
	float RollSensitivity = 1.5f;

	//~ Ballast System
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Ballast")
	float BallastForce = 600.f; // Ascend/Descend acceleration

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Ballast")
	float BallastChangeSpeed = 3.5f;

	//~ Hydrodynamics (Morison Equation parameters)
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Hydrodynamics")
	float LinearDrag = 1.5f; // Velocity decay multiplier

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Hydrodynamics")
	float QuadraticDrag = 0.001f; // High-speed resistance

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Hydrodynamics")
	float AngularDrag = 2.5f; // Braking for rotation

	// Metacentric restoring force (keeps sub upright naturally)
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Hydrodynamics")
	float RestoringStiffness = 4.0f;

	// Docking floatation characteristics
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Hydrodynamics")
	float DockFlotationStiffness = 5.0f; // Spring force matching the wave

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Hydrodynamics")
	float DockFlotationDamping = 2.0f; // Prevents infinite bouncing

private:
	void ApplyThrust(const FInputActionValue& Value);
	void ResetThrust(const FInputActionValue& Value);
	void ApplyRotation(const FInputActionValue& Value);
	void ApplyBallast(const FInputActionValue& Value);
	void ResetBallast(const FInputActionValue& Value);
	void TriggerStabilization();
	void HandleInteract();

	void InitializeWaves();
	void EvaluateWaveKinematics(const FVector& Location, float Time, float& OutSurfaceZ, FVector& OutFluidVel, FVector& OutWaveNormal);
	void UpdateHydrodynamics(float DeltaTime);

	UPROPERTY()
	TObjectPtr<AController> CachedController;

	TArray<FGerstnerHarmonic> WaveHarmonics;

	float TargetBallastForce = 0.f;
	float CurrentBallastForce = 0.f;
	float TargetThrustScalar = 0.f;
	float CurrentThrustScalar = 0.f;

	FVector CurrentMoveInput = FVector::ZeroVector;
	FVector CurrentRotationInput = FVector::ZeroVector;
	bool bIsStabilizing = false;
};