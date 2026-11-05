#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "TorpedoReloadPolicy.generated.h"

class ASubDrone_Attacker;

/**
 * Strategy that refills the drone's INTERNAL RESERVE (second ammo tier) from a PHYSICAL source.
 * The magnetic ring is fed from the reserve by the drone itself (manual reload / service).
 * Design rule: no policy may create torpedoes from nothing (the former timed regeneration was
 * removed) - every round comes from the Shell magazine. Swap the class in BP_SubDrone_Attacker ->
 * Reserve Supply Policy; the drone only knows ASubDrone_Attacker::AddToReserve and RequiresDocking().
 */
UCLASS(Abstract, EditInlineNew, DefaultToInstanced, CollapseCategories, Blueprintable)
class AOS_DK_API UTorpedoReloadPolicy : public UObject
{
	GENERATED_BODY()

public:
	/** Rounds to add to the internal reserve this frame. */
	virtual int32 TickReserveResupply(ASubDrone_Attacker& Drone, float DeltaSeconds) { return 0; }

	/** True: an exhausted reserve makes the drone request docking with the Shell. */
	virtual bool RequiresDocking() const { return false; }

	/** 0..1 progress to the next round (HUD). */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reload")
	virtual float GetProgress() const { return 0.f; }
};

/**
 * Default: the reserve is refilled only while the drone is serviced - docked on the Shell hull socket,
 * or the Shell itself is moored at a dock / service station (ASubDrone_Attacker::IsBeingServiced).
 */
UCLASS(meta = (DisplayName = "Dock Resupply (Shell)"))
class AOS_DK_API UTorpedoReloadPolicy_DockResupply : public UTorpedoReloadPolicy
{
	GENERATED_BODY()

public:
	virtual int32 TickReserveResupply(ASubDrone_Attacker& Drone, float DeltaSeconds) override;
	virtual bool RequiresDocking() const override { return true; }
	virtual float GetProgress() const override { return SecondsPerTorpedo > 0.f ? Accumulator / SecondsPerTorpedo : 1.f; }

	/** Transfer speed from the Shell magazine into the drone (224 rounds ~ 3.4 s). */
	UPROPERTY(EditAnywhere, Category = "Reload", meta = (ClampMin = "0.005", Units = "s"))
	float SecondsPerTorpedo = 0.015f;

private:
	float Accumulator = 0.f;
};

