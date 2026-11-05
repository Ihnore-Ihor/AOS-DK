#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ShellChargingZone.generated.h"

class UBoxComponent;
class UPointLightComponent;
class UPrimitiveComponent;
class AShellPawn;

/**
 * Fast-charge station (dock berth or a deep-sea power socket). While a Shell is inside the volume
 * it receives ChargeRatePercentPerSecond (default 8.5 %/s -> 0..100 % in ~11.8 s). The HUD shows
 * the positive balance ("+8.5%/s") and logs the active charge cycle. A beacon light breathes
 * while charging. The berth also rearms the Shell's module drones (their only resupply besides
 * the hull socket - drone munitions never regenerate).
 */
UCLASS()
class AOS_DK_API AShellChargingZone : public AActor
{
	GENERATED_BODY()

public:
	AShellChargingZone();

	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Charging")
	bool IsChargingAnyShell() const { return ChargingShells.Num() > 0; }

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UBoxComponent> ChargeVolume;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UPointLightComponent> BeaconLight;

	/** % of the core per second (balanced: full charge in 8-15 s). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Charging", meta = (ClampMin = "0.1", ClampMax = "100"))
	float ChargeRatePercentPerSecond = 8.5f;

	/** Charge only a piloted Shell (false = a moored, empty Shell recharges too). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Charging")
	bool bRequirePilot = false;

	/** Rearm the module drones (reserve + ring) while the Shell is inside. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Charging")
	bool bRearmDrones = true;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Charging|Beacon", meta = (ClampMin = "0"))
	float BeaconIdleIntensity = 0.6f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Charging|Beacon", meta = (ClampMin = "0"))
	float BeaconChargeIntensity = 9.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Charging|Beacon", meta = (ClampMin = "0.05", Units = "Hz"))
	float BeaconPulseHz = 0.8f;

	UFUNCTION()
	void OnVolumeBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

	UFUNCTION()
	void OnVolumeEndOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex);

private:
	void ScanInitialOverlaps();
	void RefreshShell(AShellPawn* Shell);

	TArray<TWeakObjectPtr<AShellPawn>> ChargingShells;
	float BeaconTime = 0.f;
	float BeaconBlend = 0.f;
};
