#pragma once

#include "CoreMinimal.h"
#include "AOSPickupBase.h"
#include "AOSPickup_TorpedoMagazine.generated.h"

class ASubDrone_Attacker;

/** Salvaged micro-torpedo canister: adds TorpedoCount rounds to the Attacker drone's internal reserve. */
UCLASS(Blueprintable, meta = (DisplayName = "AOS Pickup Torpedo Magazine"))
class AOS_DK_API AAOSPickup_TorpedoMagazine : public AAOSPickupBase
{
	GENERATED_BODY()

public:
	AAOSPickup_TorpedoMagazine();

	/** First Attacker module in the Shell's drone bay (nullptr if none is installed). */
	static ASubDrone_Attacker* FindAttacker(const AShellPawn* Shell);

	virtual bool CanApplyPickup(const AShellPawn* Shell) const override;
	virtual FText GetSalvageLabel() const override;

protected:
	virtual bool ApplyPickup(AShellPawn* Shell) override;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Pickup", meta = (ClampMin = "1"))
	int32 TorpedoCount = 32;

private:
	double LastRefusalLogTime = -100.0;
};
