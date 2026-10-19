#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "AOS_DK/Core/Interfaces/Interactions/Interactable.h"
#include "ShellPawn.generated.h"

class UBoxComponent;
class UStaticMeshComponent;
class UCameraComponent;
class UBuoyancyComponent;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

UCLASS()
class AOS_DK_API AShellPawn : public APawn, public IInteractable
{
	GENERATED_BODY()

public:
	AShellPawn();

	virtual void Tick(float DeltaTime) override;
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

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UBuoyancyComponent> BuoyancyComponent;

	//~ Inputs
	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputMappingContext> SubMappingContext;

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> MoveAction;

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> RotateAction;

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> BallastAction;

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> InteractAction;

	//~ Physics Settings
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics")
	float ThrustMultiplier = 1100.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics")
	float TorqueMultiplier = 110.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics")
	float ThrustRampSpeed = 3.0f; // Плавний розгін

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Ballast")
	float BallastForceLimit = 2200.f; //~ Збільшено для впевненого і швидкого занурення/спливання!

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Ballast")
	float BallastChangeSpeed = 4.0f; //~ Помпи реагують удвічі швидше

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Ballast")
	float DepthStabilizationStiffness = 3.0f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Hydrodynamics")
	float LateralDrag = 2.0f;
	
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics|Ballast") 
	float MaxAscentSpeed = 400.f;

private:
	void ApplyThrust(const FInputActionValue& Value);
	void ResetThrust(const FInputActionValue& Value);
	void ApplyRotation(const FInputActionValue& Value);
	void ApplyBallast(const FInputActionValue& Value);
	void ResetBallast(const FInputActionValue& Value);
	void HandleInteract();

	void UpdateBallastSystem(float DeltaTime, bool bInWater);

	UPROPERTY()
	TObjectPtr<AController> CachedController;

	float TargetBallastForce = 0.f;
	float CurrentBallastForce = 0.f;

	float TargetThrust = 0.f;
	float CurrentThrust = 0.f;
	FVector CurrentMoveInput = FVector::ZeroVector;

	bool bIsThrusting = false;
};