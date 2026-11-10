#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOS_DK/Core/Interfaces/Interactions/Interactable.h"
#include "ShellDock.generated.h"

class UBoxComponent;
class USceneComponent;
class AShellPawn;
class AAdminCharacter;
class ALARSDockArm;


UCLASS()
class AOS_DK_API AShellDock : public AActor, public IInteractable
{
	GENERATED_BODY()

public:
	AShellDock();

	virtual void Interact_Implementation(AActor* InstigatorActor) override;
	virtual void GetInteractPrompt_Implementation(AActor* InstigatorActor, FText& OutAction, bool& bOutAvailable) override;

	AShellPawn* GetLinkedSubmarine() const { return LinkedSubmarine; }

	/** World transform of the Shell's berth (captured start pose, or ParkingPoint). */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Dock")
	FTransform GetParkingTransform() const;

	/**
	 * Kernel Panic recovery (called under a black screen): the pilot is placed on the surface dock as
	 * the walking character (re-possessed), the Shell is returned to its berth with its base charge.
	 */
	void RecoverShell(AShellPawn* Shell);

	/** Called by the LARS arm once the Shell hangs in the cradle again: the pilot steps out onto the pier on foot. */
	void HandleLARSRecoveryComplete(AShellPawn* Shell);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Dock")
	ALARSDockArm* GetLARSArm() const { return LARSArm; }

protected:
	virtual void BeginPlay() override;
	
	//~ Components
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<USceneComponent> DefaultRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UBoxComponent> DockTrigger;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<USceneComponent> DisembarkPoint;

	/** Berth of the Shell (used when bUseParkingPoint, otherwise the Shell's start pose is captured). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<USceneComponent> ParkingPoint;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Dock")
	bool bUseParkingPoint = false;

	//~ References
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Dock")
	TObjectPtr<AShellPawn> LinkedSubmarine;

	/** Launch-and-recovery arm (auto-resolved). With an arm, boarding lowers the Shell into the water and docking lifts it out. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Dock")
	TObjectPtr<ALARSDockArm> LARSArm;

private:
	void BoardShell(AAdminCharacter* Admin);
	void DisembarkPilot(AShellPawn* Shell);

	FTransform CapturedParking = FTransform::Identity;
	bool bHasCapturedParking = false;
};