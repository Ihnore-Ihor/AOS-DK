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
struct FInputActionValue;

UCLASS()
class AOS_DK_API AShellPawn : public APawn, public IInteractable
{
	GENERATED_BODY()

public:
	AShellPawn();

	virtual void Tick(float DeltaTime) override;
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;
	virtual void Interact_Implementation(AActor* InstigatorActor) override;

protected:
	virtual void BeginPlay() override;

	//~ Components
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UBoxComponent> BoxRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UStaticMeshComponent> ShellMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UCameraComponent> FPCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UBuoyancyComponent> BuoyancyComponent;

	//~ Input
	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> MoveAction;

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> RotateAction;

	UPROPERTY(EditDefaultsOnly, Category = "AOS_DK|Input")
	TObjectPtr<UInputAction> InteractAction;

	//~ Physics
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics")
	float ThrustMultiplier = 2000.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Physics")
	float TorqueMultiplier = 500.f;

	//~ Interaction
	UPROPERTY()
	TArray<AActor*> OverlapBuffer;

	UFUNCTION()
	void OnOverlapBegin(UPrimitiveComponent* OverlappedComp, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

	UFUNCTION()
	void OnOverlapEnd(UPrimitiveComponent* OverlappedComp, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

private:
	void ApplyThrust(const FInputActionValue& Value);
	void ApplyRotation(const FInputActionValue& Value);
	void HandleInteract();
	void UpdateGyrostabilization(float DeltaTime);

	float TimeSinceLastInput = 0.f;
};