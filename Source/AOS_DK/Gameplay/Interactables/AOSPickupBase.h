#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOS_DK/Core/Interfaces/Interactions/Interactable.h"
#include "AOSPickupBase.generated.h"

class USphereComponent;
class UStaticMeshComponent;
class UPointLightComponent;
class UNiagaraSystem;
class USoundBase;
class AShellPawn;

/**
 * State-modifying pickup salvaged by Shell-1 on an explicit [F] (IA_Interact) while it is in the reticle focus.
 * Hovers (bob + spin), glows (emissive mesh + point light). The Shell's 30 Hz interaction query finds the Trigger
 * sphere (WorldDynamic, query-only - it blocks nothing, so it never steals the drone aim), the cockpit shows
 * "[F] <GetSalvageLabel()>" under the crosshair, and Interact() calls ApplyPickup; when that succeeds it plays the
 * chime + VFX, hides itself and is destroyed (after CollectFXTime; 0 = DestroyActor immediately).
 * A pickup that cannot be applied (core full, reserve full) stays in the world and is prompted as "[F] FULL".
 * Swimming through it no longer collects it.
 */
UCLASS(Abstract, Blueprintable, meta = (DisplayName = "AOS Pickup Base"))
class AOS_DK_API AAOSPickupBase : public AActor, public IInteractable
{
	GENERATED_BODY()

public:
	AAOSPickupBase();

	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintPure, Category = "AOS|Pickup")
	bool IsCollected() const { return bCollected; }

	/** Tries to apply the pickup to the Shell (also callable from scripts/tests). */
	UFUNCTION(BlueprintCallable, Category = "AOS|Pickup")
	bool TryCollect(AShellPawn* Shell);

	/** Would ApplyPickup succeed right now (core / reserve not full, module online)? Drives "[F] FULL". */
	virtual bool CanApplyPickup(const AShellPawn* Shell) const PURE_VIRTUAL(AAOSPickupBase::CanApplyPickup, return false;);

	/** Prompt action, e.g. "SALVAGE ENERGY (+25%)". */
	virtual FText GetSalvageLabel() const PURE_VIRTUAL(AAOSPickupBase::GetSalvageLabel, return FText::GetEmpty(););

	//~ IInteractable: [F] on the pickup in focus (Instigator = the Shell).
	virtual void Interact_Implementation(AActor* InstigatorActor) override;
	virtual void GetInteractPrompt_Implementation(AActor* InstigatorActor, FText& OutAction, bool& bOutAvailable) override;

protected:
	virtual void BeginPlay() override;

	/** Returns true if the pickup was consumed. */
	virtual bool ApplyPickup(AShellPawn* Shell) PURE_VIRTUAL(AAOSPickupBase::ApplyPickup, return false;);

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS|Pickup", meta = (DisplayName = "On Collected"))
	void BP_OnCollected(AShellPawn* Shell);

	/** Query-only focus volume (WorldDynamic): found by the Shell's interaction sweep; blocks no trace channel. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USphereComponent> Trigger;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Mesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UPointLightComponent> Glow;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup|FX")
	TObjectPtr<USoundBase> CollectSound;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup|FX")
	TObjectPtr<UNiagaraSystem> CollectFX;

	/** Niagara float user parameter driven on CollectFX (e.g. NS_DroneBubbles User.BubbleRate). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup|FX")
	FName CollectFXRateParam = TEXT("BubbleRate");

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup|FX", meta = (ClampMin = "0"))
	float CollectFXRate = 900.f;

	/** Seconds the collect VFX / light flash plays before the actor is destroyed (0 = destroy immediately). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup|FX", meta = (ClampMin = "0", Units = "s"))
	float CollectFXTime = 0.9f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup|Hover", meta = (Units = "cm"))
	float BobAmplitude = 12.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup|Hover", meta = (Units = "Hz"))
	float BobFrequency = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup|Hover", meta = (Units = "DegreesPerSecond"))
	float SpinSpeed = 35.f;

private:
	FVector MeshBaseLocation = FVector::ZeroVector;
	float BaseLightIntensity = 0.f;
	float Phase = 0.f;
	float CollectAge = 0.f;
	bool bCollected = false;
};
