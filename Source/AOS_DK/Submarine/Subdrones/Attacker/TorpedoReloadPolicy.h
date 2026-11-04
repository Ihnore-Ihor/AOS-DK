#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "TorpedoReloadPolicy.generated.h"

class ASubDrone_Attacker;

/**
 * Strategy that refills the drone's INTERNAL RESERVE (second ammo tier).
 * The magnetic ring itself is always refilled from the reserve by the drone (first tier).
 * Swap the policy class in BP_SubDrone_Attacker -> Reserve Supply Policy; the drone only
 * knows ASubDrone_Attacker::AddToReserve and RequiresDocking().
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

/** Default: the reserve is refilled only while the drone is physically docked on the Shell. */
UCLASS(meta = (DisplayName = "Dock Resupply (Shell)"))
class AOS_DK_API UTorpedoReloadPolicy_DockResupply : public UTorpedoReloadPolicy
{
	GENERATED_BODY()

public:
	virtual int32 TickReserveResupply(ASubDrone_Attacker& Drone, float DeltaSeconds) override;
	virtual bool RequiresDocking() const override { return true; }
	virtual float GetProgress() const override { return SecondsPerTorpedo > 0.f ? Accumulator / SecondsPerTorpedo : 1.f; }

	/** Transfer speed from the Shell magazine into the drone (54 rounds ~ 1.6 s). */
	UPROPERTY(EditAnywhere, Category = "Reload", meta = (ClampMin = "0.005", Units = "s"))
	float SecondsPerTorpedo = 0.03f;

private:
	float Accumulator = 0.f;
};

/** Alternative: the drone's generator slowly synthesises reserve rounds anywhere (never docks). */
UCLASS(meta = (DisplayName = "Timed Regeneration (generator)"))
class AOS_DK_API UTorpedoReloadPolicy_TimedRegen : public UTorpedoReloadPolicy
{
	GENERATED_BODY()

public:
	virtual int32 TickReserveResupply(ASubDrone_Attacker& Drone, float DeltaSeconds) override;
	virtual float GetProgress() const override { return SecondsPerTorpedo > 0.f ? Accumulator / SecondsPerTorpedo : 1.f; }

	UPROPERTY(EditAnywhere, Category = "Reload", meta = (ClampMin = "0.01", Units = "s"))
	float SecondsPerTorpedo = 0.8f;

	UPROPERTY(EditAnywhere, Category = "Reload", meta = (ClampMin = "0", Units = "s"))
	float DelayAfterLastShot = 1.0f;

private:
	float Accumulator = 0.f;
};
