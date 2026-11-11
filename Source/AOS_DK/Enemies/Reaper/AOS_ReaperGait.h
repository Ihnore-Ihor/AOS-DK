#pragma once

#include "CoreMinimal.h"
#include "AOS_ReaperTypes.h"

/** Gait table row (spec 3.6.1). */
struct FAOSGaitParams
{
	float Stride = 70.f;
	float StepHeight = 22.f;
	float StepDuration = 0.42f;
};

/**
 * Tripod gait scheduler (game thread). Legs are indexed L1 L2 L3 R1 R2 R3.
 * Group A = {L1, R2, L3}, group B = {R1, L2, R3}; a group lifts only while the other one is fully planted.
 */
class FAOS_ReaperGait
{
public:
	static constexpr int32 NumLegs = 6;

	static FAOSGaitParams GetParams(EAOSGaitMode Mode);
	static int32 GroupOf(int32 Leg) { return (Leg == 0 || Leg == 4 || Leg == 2) ? 0 : 1; }

	/** Ref-pose foot positions in component space (xy = home, z = foot-bone height above the floor). */
	void SetHomes(const FVector (&InHomesCS)[NumLegs]);

	void Reset() { bInitialised = false; }

	struct FInput
	{
		const UWorld* World = nullptr;
		const AActor* IgnoreActor = nullptr;
		FTransform MeshToWorld = FTransform::Identity;
		FVector Velocity = FVector::ZeroVector;
		EAOSGaitMode Mode = EAOSGaitMode::Walk;
		float DeltaTime = 0.f;
		bool bFrozen = false;
		bool bDebugDraw = false;
	};

	void Update(const FInput& In);

	/** Foot-bone origin targets in world space (planted or swinging). */
	FVector FootBoneWorld[NumLegs];
	/** Ground contact point under each foot target (world). */
	FVector GroundWorld[NumLegs];
	bool bLanded[NumLegs] = { false, false, false, false, false, false };
	bool bSwinging[NumLegs] = { false, false, false, false, false, false };

private:
	void TraceGround(const FInput& In, const FVector& Around, FVector& OutGround) const;

	FVector HomesCS[NumLegs];
	FVector Planted[NumLegs];
	FVector SwingFrom[NumLegs];
	FVector SwingTo[NumLegs];
	float SwingTime[NumLegs] = { 0, 0, 0, 0, 0, 0 };
	bool bInitialised = false;
	float FootHeight = 12.f;
};
