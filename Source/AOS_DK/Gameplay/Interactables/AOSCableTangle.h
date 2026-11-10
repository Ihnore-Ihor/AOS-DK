#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSCableTangle.generated.h"

class UStaticMeshComponent;
class UPrimitiveComponent;
class UNiagaraSystem;
class USoundBase;
class AShellPawn;

/**
 * Soft obstacle: a tangle of severed cables. Collision profile AOS_SoftFoliage (query only, overlaps
 * Pawn / PhysicsBody / Vehicle, never blocks movement).
 * Shell-1 entering the tangle is snagged: its velocity drops by VelocityDamping at once and, for
 * EntangleDuration seconds, an extra linear drag scales its steady-state speed by (1 - VelocityDamping).
 * The tangle is a torpedo fuse target (tag AOS.FuseTarget): Integrity damage severs it and frees the Shell.
 */
UCLASS(Blueprintable, meta = (DisplayName = "AOS Cable Tangle"))
class AOS_DK_API AAOSCableTangle : public AActor
{
	GENERATED_BODY()

public:
	AAOSCableTangle();

	virtual void Tick(float DeltaSeconds) override;
	virtual float TakeDamage(float DamageAmount, struct FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override;

	UFUNCTION(BlueprintPure, Category = "AOS|Interactables")
	bool IsEntangling() const { return EntangledShell.IsValid(); }

	UFUNCTION(BlueprintPure, Category = "AOS|Interactables")
	bool IsSevered() const { return bSevered; }

	UFUNCTION(BlueprintPure, Category = "AOS|Interactables")
	float GetIntegrity() const { return Integrity; }

	/** Cuts the tangle (torpedoes or script): frees the Shell, disables collision, plays FX, destroys the actor. */
	UFUNCTION(BlueprintCallable, Category = "AOS|Interactables")
	void Sever(AActor* Cause);

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UFUNCTION()
	void HandleBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS|Interactables", meta = (DisplayName = "On Entangled"))
	void BP_OnEntangled(AActor* Shell);

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS|Interactables", meta = (DisplayName = "On Released"))
	void BP_OnReleased(AActor* Shell);

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS|Interactables", meta = (DisplayName = "On Severed"))
	void BP_OnSevered(AActor* Cause);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> Mesh;

	/** Share of the Shell velocity removed while snagged (0.5 = 50 %). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Tangle", meta = (ClampMin = "0", ClampMax = "0.95"))
	float VelocityDamping = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Tangle", meta = (ClampMin = "0.1", Units = "s"))
	float EntangleDuration = 3.f;

	/** After a release the same Shell is not snagged again for this long (lets it push through). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Tangle", meta = (ClampMin = "0", Units = "s"))
	float ReentangleCooldown = 2.f;

	/** Torpedo damage needed to cut the tangle (MicroTorpedo = 14 per hit). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Tangle", meta = (ClampMin = "1"))
	float MaxIntegrity = 40.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Tangle|FX")
	TObjectPtr<UNiagaraSystem> SeverFX;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Tangle|FX")
	TObjectPtr<USoundBase> SnagSound;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Tangle|FX")
	TObjectPtr<USoundBase> SeverSound;

private:
	void Entangle(AShellPawn* Shell);
	void Release(bool bByTorpedo);
	UPrimitiveComponent* GetShellBody() const;

	TWeakObjectPtr<AShellPawn> EntangledShell;
	TWeakObjectPtr<AShellPawn> CooldownShell;
	float EntangleTimeLeft = 0.f;
	float ExtraDragRate = 0.f;
	double CooldownUntil = -1.0;
	float Integrity = 40.f;
	bool bSevered = false;
};
