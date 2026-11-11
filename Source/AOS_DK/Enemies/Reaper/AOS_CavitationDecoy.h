#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOS_CavitationDecoy.generated.h"

class USphereComponent;
class UNiagaraSystem;

/**
 * Collapsing bubble cloud launched from the Reaper's tail tubes. Carries the AOS.FuseTarget tag, so the micro-torpedoes'
 * proximity fuse (and the Retarget() guidance override) detonate on it instead of the Reaper. It absorbs all damage.
 */
UCLASS(Blueprintable)
class AOS_DK_API AAOS_CavitationDecoy : public AActor
{
	GENERATED_BODY()

public:
	AAOS_CavitationDecoy();

	virtual float TakeDamage(float DamageAmount, struct FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override;

	/** Starts the lifetime (seconds) and the bloom FX. */
	void Activate(float InLifetime);

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Reaper", meta = (DisplayName = "On Decoy Activated"))
	void BP_OnActivated();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Reaper|Decoy", meta = (ClampMin = "1", Units = "cm"))
	float Radius = 70.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Reaper|Decoy", meta = (ClampMin = "0.1", Units = "s"))
	float Lifetime = 1.2f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Decoy")
	TObjectPtr<UNiagaraSystem> BloomFX;

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USphereComponent> Sphere;
};
