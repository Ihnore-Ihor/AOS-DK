#include "AOS_ReaperGait.h"
#include "AOS_ReaperIK.h"
#include "Engine/World.h"
#include "DrawDebugHelpers.h"

FAOSGaitParams FAOS_ReaperGait::GetParams(EAOSGaitMode Mode)
{
	switch (Mode)
	{
	case EAOSGaitMode::Investigate: return { 95.f, 24.f, 0.32f };
	case EAOSGaitMode::Scuttle:     return { 140.f, 30.f, 0.22f };
	case EAOSGaitMode::Skitter:     return { 120.f, 18.f, 0.11f };
	case EAOSGaitMode::Brine:       return { 40.f, 45.f, 0.60f };
	case EAOSGaitMode::Walk:
	default:                        return { 70.f, 22.f, 0.42f };
	}
}

void FAOS_ReaperGait::SetHomes(const FVector (&InHomesCS)[NumLegs])
{
	float SumZ = 0.f;
	for (int32 i = 0; i < NumLegs; ++i)
	{
		HomesCS[i] = InHomesCS[i];
		SumZ += InHomesCS[i].Z;
		FootBoneWorld[i] = Planted[i] = SwingFrom[i] = SwingTo[i] = GroundWorld[i] = FVector::ZeroVector;
	}
	FootHeight = SumZ / NumLegs;
	bInitialised = false;
}

void FAOS_ReaperGait::TraceGround(const FInput& In, const FVector& Around, FVector& OutGround) const
{
	OutGround = FVector(Around.X, Around.Y, In.MeshToWorld.GetLocation().Z);
	if (!In.World)
	{
		return;
	}
	// Trace as a Pawn: the enclosing ocean volume (WorldStatic = Block, Pawn = Overlap) must not count as ground. An object-type trace
	// started inside that box returned the start point itself, which left every foot pad ~150 cm above the floor.
	FCollisionQueryParams Params(SCENE_QUERY_STAT(ReaperFoot), false, In.IgnoreActor);
	Params.bFindInitialOverlaps = false;
	FHitResult Hit;
	if (In.World->LineTraceSingleByChannel(Hit, Around + FVector(0, 0, 150.f), Around - FVector(0, 0, 150.f), ECC_Pawn, Params) && !Hit.bStartPenetrating)
	{
		OutGround = Hit.ImpactPoint;
	}
}

void FAOS_ReaperGait::Update(const FInput& In)
{
	const FAOSGaitParams P = GetParams(In.Mode);
	const FVector Vxy(In.Velocity.X, In.Velocity.Y, 0.f);

	FVector Targets[NumLegs];
	for (int32 i = 0; i < NumLegs; ++i)
	{
		const FVector HomeW = In.MeshToWorld.TransformPosition(FVector(HomesCS[i].X, HomesCS[i].Y, 0.f));
		TraceGround(In, HomeW + Vxy * (P.StepDuration * 0.5f), GroundWorld[i]);
		Targets[i] = GroundWorld[i];
		bLanded[i] = false;
	}

	if (!bInitialised)
	{
		for (int32 i = 0; i < NumLegs; ++i)
		{
			Planted[i] = Targets[i];
			bSwinging[i] = false;
		}
		bInitialised = true;
	}

	if (!In.bFrozen)
	{
		const bool bAnySwing[2] = {
			bSwinging[0] || bSwinging[4] || bSwinging[2],
			bSwinging[3] || bSwinging[1] || bSwinging[5] };

		// Pending-step error per group (planted foot vs. its lead target, in the horizontal plane).
		float Err[2] = { 0.f, 0.f };
		for (int32 i = 0; i < NumLegs; ++i)
		{
			if (!bSwinging[i])
			{
				Err[GroupOf(i)] = FMath::Max(Err[GroupOf(i)], FVector::Dist2D(Planted[i], Targets[i]));
			}
		}
		const float Threshold = 0.5f * P.Stride;
		int32 Start = INDEX_NONE;
		if (!bAnySwing[0] && !bAnySwing[1])
		{
			if (Err[0] > Threshold || Err[1] > Threshold)
			{
				Start = Err[0] >= Err[1] ? 0 : 1;
			}
		}
		if (Start != INDEX_NONE)
		{
			for (int32 i = 0; i < NumLegs; ++i)
			{
				if (GroupOf(i) == Start)
				{
					bSwinging[i] = true;
					SwingTime[i] = 0.f;
					SwingFrom[i] = Planted[i];
					SwingTo[i] = Targets[i];
				}
			}
		}

		for (int32 i = 0; i < NumLegs; ++i)
		{
			if (!bSwinging[i])
			{
				continue;
			}
			SwingTime[i] += In.DeltaTime;
			SwingTo[i] = Targets[i];
			if (SwingTime[i] >= P.StepDuration)
			{
				bSwinging[i] = false;
				Planted[i] = SwingTo[i];
				bLanded[i] = true;
			}
		}
	}

	for (int32 i = 0; i < NumLegs; ++i)
	{
		FVector Ground = Planted[i];
		if (bSwinging[i])
		{
			const float S = AOSReaperIK::Smooth01(SwingTime[i] / FMath::Max(P.StepDuration, 0.01f));
			Ground = FMath::Lerp(SwingFrom[i], SwingTo[i], S) + FVector(0, 0, P.StepHeight * FMath::Sin(PI * S));
		}
		FootBoneWorld[i] = Ground + FVector(0, 0, FootHeight);
#if ENABLE_DRAW_DEBUG
		if (In.bDebugDraw && In.World)
		{
			DrawDebugSphere(In.World, Targets[i], 8.f, 8, GroupOf(i) == 0 ? FColor::Cyan : FColor::Orange, false, -1.f);
			DrawDebugSphere(In.World, Ground, 6.f, 8, bSwinging[i] ? FColor::Yellow : FColor::Green, false, -1.f);
		}
#endif
	}
}
