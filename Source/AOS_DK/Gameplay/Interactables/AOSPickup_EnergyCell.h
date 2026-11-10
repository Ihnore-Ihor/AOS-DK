#pragma once

#include "CoreMinimal.h"
#include "AOSPickupBase.h"
#include "AOSPickup_EnergyCell.generated.h"

/** Restores Shell-1 core energy (= hull integrity + power budget) via UShellEnergyComponent::AddEnergy. */
UCLASS(Blueprintable, meta = (DisplayName = "AOS Pickup Energy Cell"))
class AOS_DK_API AAOSPickup_EnergyCell : public AAOSPickupBase
{
	GENERATED_BODY()

public:
	AAOSPickup_EnergyCell();

	virtual bool CanApplyPickup(const AShellPawn* Shell) const override;
	virtual FText GetSalvageLabel() const override;

protected:
	virtual bool ApplyPickup(AShellPawn* Shell) override;

	/** Percent points of MaxEnergy restored. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup", meta = (ClampMin = "0", ClampMax = "100"))
	float EnergyAmount = 25.f;

	/** Keep the cell in the world when the core is already (almost) full. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup")
	bool bRequireMissingEnergy = true;
};
