#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ShellEnergyComponent.generated.h"

/** Sign of the net energy balance shown under the battery. */
UENUM(BlueprintType)
enum class EShellEnergyFlow : uint8
{
	Neutral UMETA(DisplayName = "Neutral"),
	Drain   UMETA(DisplayName = "Drain"),
	Charge  UMETA(DisplayName = "Charge")
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnShellEnergyChanged, float, Energy, float, MaxEnergy);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FOnShellEnergyDamaged, float, EnergyLostPercent, float, NewFraction, FVector, HitLocation, AActor*, DamageCauser);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnSubmarineEnergyDepleted);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnShellChargingChanged, bool, bCharging, float, ChargeRatePercentPerSecond);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnShellChargeComplete);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnShellEnergyRestored, float, NewFraction);

/**
 * Core energy of the Shell: it is the submarine's hit points AND the budget of every system.
 *  - Cruising (thrust, ballast, steering) is free. Only active systems publish a continuous drain
 *    in %/s: the boost and the module drones (deployed hold / firing).
 *  - One-shot system costs (manual drone reload) are paid atomically with TryConsumeEnergy.
 *  - Charge sources (dock charging zones) publish a charge in %/s; the strongest one wins.
 *  - Damage subtracts fixed percent points.
 *  - Energy <= 0 -> OnSubmarineEnergyDepleted (the Shell halts and runs the Kernel Panic recovery).
 * All rates are "% of MaxEnergy per second": 8.5 = full charge in ~11.8 s.
 */
UCLASS(ClassGroup = (AOS_DK), meta = (BlueprintSpawnableComponent))
class AOS_DK_API UShellEnergyComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UShellEnergyComponent();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** Publishes (0 clears) the continuous drain of one consumer, % of MaxEnergy per second. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Energy")
	void SetConsumerDrain(FName Consumer, float PercentPerSecond);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Energy")
	void ClearConsumers();

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Energy")
	void AddChargeSource(UObject* Source, float PercentPerSecond);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Energy")
	void RemoveChargeSource(UObject* Source);

	/**
	 * One-shot system cost in percent points of MaxEnergy (e.g. a manual drone reload).
	 * Atomic: paid only if the core can afford it AND stays alive - a purchase never triggers a Kernel Panic.
	 */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Energy")
	bool TryConsumeEnergy(float Percent, FName Consumer);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Energy")
	bool CanAffordEnergy(float Percent) const;

	/** Fixed damage in percent points of MaxEnergy. Returns the energy actually removed (percent points). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Energy")
	float ApplyEnergyDamage(float Percent, FVector HitLocation, AActor* DamageCauser);

	/** Recovery: clears the depleted state and sets the energy to Fraction of MaxEnergy. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Energy")
	void RestoreEnergy(float Fraction);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Energy")
	float GetEnergy() const { return Energy; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Energy")
	float GetMaxEnergy() const { return MaxEnergy; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Energy")
	float GetEnergyFraction() const { return MaxEnergy > 0.f ? Energy / MaxEnergy : 0.f; }

	/** Smoothed signed net balance actually applied (%/s): + charge, - drain. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Energy")
	float GetNetRatePercent() const { return DisplayedRate; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Energy")
	EShellEnergyFlow GetFlow() const;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Energy")
	bool IsCharging() const { return !bDepleted && ChargeSources.Num() > 0; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Energy")
	bool IsDepleted() const { return bDepleted; }

	/** Strongest registered charge source, %/s. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Energy")
	float GetChargeRatePercent() const;

	/** Sum of the published consumer drains, %/s. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Energy")
	float GetTotalDrainPercent() const;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Energy")
	FOnShellEnergyChanged OnEnergyChanged;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Energy")
	FOnShellEnergyDamaged OnEnergyDamaged;

	/** Energy reached 0: the Shell must halt (Kernel Panic). */
	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Energy")
	FOnSubmarineEnergyDepleted OnSubmarineEnergyDepleted;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Energy")
	FOnShellChargingChanged OnChargingChanged;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Energy")
	FOnShellChargeComplete OnChargeComplete;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Energy")
	FOnShellEnergyRestored OnEnergyRestored;

protected:
	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Energy", meta = (ClampMin = "1"))
	float MaxEnergy = 100.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Energy", meta = (ClampMin = "0", ClampMax = "1"))
	float StartFraction = 1.f;

	/** A charge station reaches its full rate after this time (soft coupling, no jump in the readout). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Charge", meta = (ClampMin = "0", Units = "s"))
	float ChargeRampTime = 0.6f;

	/** Share of the system drain still paid while docked-charging (0 = dock power feeds the systems). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Charge", meta = (ClampMin = "0", ClampMax = "1"))
	float DrainWhileCharging = 1.f;

	/** Smoothing of the displayed balance (higher = snappier readout). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Display", meta = (ClampMin = "0.1"))
	float RateSmoothing = 6.f;

	/** |balance| below this (%/s) is reported as Neutral. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Display", meta = (ClampMin = "0"))
	float NeutralThreshold = 0.005f;

	/** Debug: ignore damage. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Energy|Debug")
	bool bInvulnerable = false;

private:
	void Deplete();
	void PruneChargeSources();

	float Energy = 100.f;
	float ChargeBlend = 0.f;
	float DisplayedRate = 0.f;
	float LastBroadcastEnergy = -1.f;
	bool bDepleted = false;
	bool bChargeCompleteNotified = false;

	TMap<FName, float> ConsumerDrains;
	TMap<TWeakObjectPtr<UObject>, float> ChargeSources;
};
