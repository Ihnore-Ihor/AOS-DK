#include "ShellEnergyComponent.h"

DEFINE_LOG_CATEGORY_STATIC(LogShellEnergy, Log, All);

UShellEnergyComponent::UShellEnergyComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
}

void UShellEnergyComponent::BeginPlay()
{
	Super::BeginPlay();
	Energy = MaxEnergy * StartFraction;
	bDepleted = Energy <= 0.f;
	LastBroadcastEnergy = Energy;
	OnEnergyChanged.Broadcast(Energy, MaxEnergy);
}

void UShellEnergyComponent::PruneChargeSources()
{
	const bool bWasCharging = ChargeSources.Num() > 0;
	for (auto It = ChargeSources.CreateIterator(); It; ++It)
	{
		if (!It.Key().IsValid())
		{
			It.RemoveCurrent();
		}
	}
	if (bWasCharging && ChargeSources.Num() == 0)
	{
		OnChargingChanged.Broadcast(false, 0.f);
	}
}

void UShellEnergyComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	const float Dt = FMath::Min(DeltaTime, 0.1f);
	if (Dt <= 0.f)
	{
		return;
	}
	PruneChargeSources();

	const bool bHasCharge = IsCharging();
	const float RampSpeed = ChargeRampTime > KINDA_SMALL_NUMBER ? 1.f / ChargeRampTime : 1000.f;
	ChargeBlend = FMath::FInterpConstantTo(ChargeBlend, bHasCharge ? 1.f : 0.f, Dt, RampSpeed);

	float AppliedRate = 0.f;
	if (!bDepleted)
	{
		const float Drain = GetTotalDrainPercent() * FMath::Lerp(1.f, DrainWhileCharging, ChargeBlend);
		const float Charge = GetChargeRatePercent() * ChargeBlend;
		const float NetRate = Charge - Drain;

		const float OldEnergy = Energy;
		const float PercentToEnergy = MaxEnergy * 0.01f;
		Energy = FMath::Clamp(Energy + NetRate * PercentToEnergy * Dt, 0.f, MaxEnergy);
		// What the player sees is the balance actually applied (0 once the core is full).
		AppliedRate = (Energy - OldEnergy) / (PercentToEnergy * Dt);

		if (bHasCharge && Energy >= MaxEnergy - KINDA_SMALL_NUMBER && !bChargeCompleteNotified)
		{
			bChargeCompleteNotified = true;
			OnChargeComplete.Broadcast();
		}
		if (Energy < MaxEnergy * 0.995f)
		{
			bChargeCompleteNotified = false;
		}
		if (Energy <= 0.f && OldEnergy > 0.f)
		{
			Deplete();
		}
	}

	DisplayedRate = FMath::FInterpTo(DisplayedRate, AppliedRate, Dt, RateSmoothing);
	if (FMath::Abs(Energy - LastBroadcastEnergy) > 0.05f)
	{
		LastBroadcastEnergy = Energy;
		OnEnergyChanged.Broadcast(Energy, MaxEnergy);
	}
}

void UShellEnergyComponent::SetConsumerDrain(FName Consumer, float PercentPerSecond)
{
	if (PercentPerSecond <= 0.f)
	{
		ConsumerDrains.Remove(Consumer);
	}
	else
	{
		ConsumerDrains.Add(Consumer, PercentPerSecond);
	}
}

void UShellEnergyComponent::ClearConsumers()
{
	ConsumerDrains.Reset();
}

void UShellEnergyComponent::AddChargeSource(UObject* Source, float PercentPerSecond)
{
	if (!Source || PercentPerSecond <= 0.f)
	{
		return;
	}
	const bool bWasCharging = ChargeSources.Num() > 0;
	ChargeSources.Add(Source, PercentPerSecond);
	if (!bWasCharging && !bDepleted)
	{
		OnChargingChanged.Broadcast(true, GetChargeRatePercent());
	}
}

void UShellEnergyComponent::RemoveChargeSource(UObject* Source)
{
	if (ChargeSources.Remove(Source) > 0 && ChargeSources.Num() == 0 && !bDepleted)
	{
		OnChargingChanged.Broadcast(false, 0.f);
	}
}

bool UShellEnergyComponent::CanAffordEnergy(float Percent) const
{
	return !bDepleted && Energy - FMath::Max(0.f, Percent) * MaxEnergy * 0.01f > KINDA_SMALL_NUMBER;
}

bool UShellEnergyComponent::TryConsumeEnergy(float Percent, FName Consumer)
{
	if (Percent <= 0.f)
	{
		return !bDepleted;
	}
	if (!CanAffordEnergy(Percent))
	{
		return false;
	}
	Energy -= Percent * MaxEnergy * 0.01f;
	LastBroadcastEnergy = Energy;
	OnEnergyChanged.Broadcast(Energy, MaxEnergy);
	UE_LOG(LogShellEnergy, Verbose, TEXT("%s spent %.2f%% (core %.1f%%)"), *Consumer.ToString(), Percent, GetEnergyFraction() * 100.f);
	return true;
}

float UShellEnergyComponent::ApplyEnergyDamage(float Percent, FVector HitLocation, AActor* DamageCauser)
{
	if (bDepleted || bInvulnerable || Percent <= 0.f)
	{
		return 0.f;
	}
	const float OldEnergy = Energy;
	Energy = FMath::Max(0.f, Energy - Percent * MaxEnergy * 0.01f);
	const float LostPercent = (OldEnergy - Energy) / (MaxEnergy * 0.01f);

	OnEnergyDamaged.Broadcast(LostPercent, GetEnergyFraction(), HitLocation, DamageCauser);
	LastBroadcastEnergy = Energy;
	OnEnergyChanged.Broadcast(Energy, MaxEnergy);

	if (Energy <= 0.f)
	{
		Deplete();
	}
	return LostPercent;
}

void UShellEnergyComponent::Deplete()
{
	if (bDepleted)
	{
		return;
	}
	bDepleted = true;
	Energy = 0.f;
	ChargeBlend = 0.f;
	ConsumerDrains.Reset();
	OnSubmarineEnergyDepleted.Broadcast();
}

void UShellEnergyComponent::RestoreEnergy(float Fraction)
{
	bDepleted = false;
	bChargeCompleteNotified = false;
	ChargeBlend = 0.f;
	DisplayedRate = 0.f;
	ConsumerDrains.Reset();
	Energy = MaxEnergy * FMath::Clamp(Fraction, 0.f, 1.f);
	LastBroadcastEnergy = Energy;
	OnEnergyRestored.Broadcast(GetEnergyFraction());
	OnEnergyChanged.Broadcast(Energy, MaxEnergy);
	if (ChargeSources.Num() > 0)
	{
		OnChargingChanged.Broadcast(true, GetChargeRatePercent());
	}
}

EShellEnergyFlow UShellEnergyComponent::GetFlow() const
{
	if (bDepleted || FMath::Abs(DisplayedRate) < NeutralThreshold)
	{
		return EShellEnergyFlow::Neutral;
	}
	return DisplayedRate > 0.f ? EShellEnergyFlow::Charge : EShellEnergyFlow::Drain;
}

float UShellEnergyComponent::GetChargeRatePercent() const
{
	float Best = 0.f;
	for (const TPair<TWeakObjectPtr<UObject>, float>& Pair : ChargeSources)
	{
		if (Pair.Key.IsValid())
		{
			Best = FMath::Max(Best, Pair.Value);
		}
	}
	return Best;
}

float UShellEnergyComponent::GetTotalDrainPercent() const
{
	float Sum = 0.f;
	for (const TPair<FName, float>& Pair : ConsumerDrains)
	{
		Sum += Pair.Value;
	}
	return Sum;
}
