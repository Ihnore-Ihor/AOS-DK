#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOS_DK/Core/Interfaces/Interactions/Interactable.h"
#include "ShellDock.generated.h"

class UBoxComponent;
class USceneComponent;
class AShellPawn;


UCLASS()
class AOS_DK_API AShellDock : public AActor, public IInteractable
{
	GENERATED_BODY()

public:
	AShellDock();

	virtual void Interact_Implementation(AActor* InstigatorActor) override;

protected:
	virtual void BeginPlay() override;
	
	//~ Components
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<USceneComponent> DefaultRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<UBoxComponent> DockTrigger;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
	TObjectPtr<USceneComponent> DisembarkPoint;

	//~ References
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Dock")
	TObjectPtr<AShellPawn> LinkedSubmarine;
};