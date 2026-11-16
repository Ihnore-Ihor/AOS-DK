#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSFallRecoveryVolume.generated.h"

class AAdminCharacter;
class APlayerController;
class UBoxComponent;
class UPrimitiveComponent;

/**
 * Surface Fall Recovery, part 2 (Urban Bible 4.5): a query-only water trigger that puts AAdminCharacter back on deck.
 *
 * Overlap with the character capsule -> move/look input ignored and movement disabled -> camera fade out -> velocity zeroed and the character
 * teleported to the newest pose of its UAOSSafeGroundTracker (PlayerStart if the ring is empty) -> camera fade in ->
 * input and movement restored. No damage. Overlaps by other pawns (the Shell, enemies) are ignored.
 *
 * The recovery latch lives in the tracker, so neighbouring volumes never run two recoveries for one character.
 */
UCLASS(Blueprintable)
class AOS_DK_API AAOSFallRecoveryVolume : public AActor
{
	GENERATED_BODY()

public:
	AAOSFallRecoveryVolume();

	UFUNCTION(BlueprintPure, Category = "FallRecovery")
	UBoxComponent* GetRecoveryBox() const { return RecoveryBox; }

	/** Fade to black before the teleport. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "FallRecovery", meta = (ClampMin = "0.0", Units = "s"))
	float FadeOutDuration = 0.35f;

	/** Fade back in after the teleport; controls return when it ends. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "FallRecovery", meta = (ClampMin = "0.0", Units = "s"))
	float FadeInDuration = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "FallRecovery")
	FLinearColor FadeColor = FLinearColor::Black;

	/** The character is dropped this high above the recorded pose so the capsule never starts inside the deck. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "FallRecovery", meta = (ClampMin = "0.0", Units = "cm"))
	float RecoveryLift = 6.f;

protected:
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	UFUNCTION()
	void HandleBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

	void BeginRecovery(AAdminCharacter* Character);
	void TeleportToSafeGround();
	void FinishRecovery();

	UPROPERTY(VisibleAnywhere, Category = "Components")
	TObjectPtr<UBoxComponent> RecoveryBox;

	TWeakObjectPtr<AAdminCharacter> ActiveCharacter;
	TWeakObjectPtr<APlayerController> LockedController;
	FTimerHandle TeleportTimer;
	FTimerHandle FinishTimer;
};
