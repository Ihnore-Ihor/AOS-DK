#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSDampingPerimeter.generated.h"

class UMaterialParameterCollection;
class UNiagaraComponent;
class UNiagaraSystem;

/**
 * Always-loaded owner of the Atoll calm-lagoon mask (Urban Bible 2.3-2.5):
 *  - writes UAOSAtollSettings into MPC_AOS_Atoll (GPU wave mask + analytic foam) and warns in the editor
 *    when the collection defaults drift from the settings by more than 1 cm;
 *  - lays out the Taylor bubble curtains from the same settings: one gate system per ocean gate
 *    (local +X radially outward), the BC-R ring boil and a camera-following near-ring bubble patch.
 * The actor's Z is the calm water level.
 */
UCLASS()
class AOS_DK_API AAOSDampingPerimeter : public AActor
{
	GENERATED_BODY()

public:
	AAOSDampingPerimeter();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Pushes the settings into the collection instance of this world. */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "AOS|Atoll")
	void PushMaskParameters();

	/** Re-places the curtain components from the settings. */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "AOS|Atoll")
	void LayoutCurtains();

	/**
	 * Verification probe (editor / PIE): sweeps the water-plugin CPU waves at a point over [0, Duration] s.
	 * X = min, Y = max attenuated wave height (cm, relative to the calm level), Z = attenuation factor.
	 */
	UFUNCTION(BlueprintCallable, Category = "AOS|Atoll|Debug")
	FVector ProbeWaterWaves(const FVector& At, float Duration = 60.f, int32 Steps = 600) const;

	/** Verification probe: water surface Z from TryQueryWaterInfoClosestToWorldLocation(IncludeWaves) at the current wave time. */
	UFUNCTION(BlueprintCallable, Category = "AOS|Atoll|Debug")
	float QueryWaterSurfaceZ(const FVector& At) const;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Atoll")
	TObjectPtr<UMaterialParameterCollection> AtollCollection;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Atoll|Curtains")
	TObjectPtr<UNiagaraSystem> GateCurtainSystem;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Atoll|Curtains")
	TObjectPtr<UNiagaraSystem> RingCurtainSystem;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Atoll|Curtains")
	TObjectPtr<UNiagaraSystem> RingNearSystem;

	/** Gate curtains are culled beyond this camera distance (0 = never). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Atoll|Curtains", meta = (ClampMin = "0", Units = "cm"))
	float GateCullDistance = 20000.f;

	/** Ring boil sits this far above the calm water level. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Atoll|Curtains", meta = (Units = "cm"))
	float RingZOffset = 3.f;

	/** The near-ring bubble patch runs while the camera is within this distance of the BC-R line. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Atoll|Curtains", meta = (ClampMin = "0", Units = "cm"))
	float RingNearActivationDistance = 4000.f;

protected:
	UPROPERTY(VisibleAnywhere, Category = "AOS|Atoll")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, Category = "AOS|Atoll|Curtains")
	TObjectPtr<UNiagaraComponent> RingCurtain;

	UPROPERTY(VisibleAnywhere, Category = "AOS|Atoll|Curtains")
	TObjectPtr<UNiagaraComponent> RingNearCurtain;

	UPROPERTY(VisibleAnywhere, Category = "AOS|Atoll|Curtains")
	TArray<TObjectPtr<UNiagaraComponent>> GateCurtains;

private:
	void UpdateViewDependent();
#if WITH_EDITOR
	void ValidateCollectionDefaults() const;
#endif
};
