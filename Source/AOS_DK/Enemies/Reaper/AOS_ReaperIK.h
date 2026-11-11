#pragma once

#include "CoreMinimal.h"

/** Analytic helpers for the procedural Reaper animation (header only, no UObject). */
namespace AOSReaperIK
{
	struct FTwoBoneResult
	{
		FVector Knee = FVector::ZeroVector;
		FVector End = FVector::ZeroVector;
		bool bReachable = true;
	};

	/**
	 * Law-of-cosines 2-bone IK. The knee is pushed towards KneeUp (projected orthogonal to the root->target line).
	 * Out-of-reach targets are clamped onto the reachable sphere (End is then not the requested Target).
	 */
	inline FTwoBoneResult SolveTwoBone(const FVector& Root, const FVector& Target, double LenA, double LenB, const FVector& KneeUp)
	{
		FTwoBoneResult R;
		FVector D = Target - Root;
		double Dist = D.Size();
		if (Dist < KINDA_SMALL_NUMBER)
		{
			D = FVector(0, 0, -1);
			Dist = 1.0;
		}
		const FVector Dir = D / Dist;
		const double MinReach = FMath::Abs(LenA - LenB) + 1.0;
		const double MaxReach = LenA + LenB - 0.5;
		const double Clamped = FMath::Clamp(Dist, MinReach, MaxReach);
		R.bReachable = FMath::IsNearlyEqual(Clamped, Dist, 0.01);

		const double CosA = FMath::Clamp((LenA * LenA + Clamped * Clamped - LenB * LenB) / (2.0 * LenA * Clamped), -1.0, 1.0);
		const double SinA = FMath::Sqrt(FMath::Max(0.0, 1.0 - CosA * CosA));
		FVector Perp = KneeUp - Dir * FVector::DotProduct(KneeUp, Dir);
		if (!Perp.Normalize())
		{
			Perp = FVector::CrossProduct(Dir, FVector::RightVector).GetSafeNormal();
		}
		R.Knee = Root + (Dir * CosA + Perp * SinA) * LenA;
		R.End = Root + Dir * Clamped;
		return R;
	}

	/** Smoothstep on [0,1]. */
	inline float Smooth01(float X)
	{
		X = FMath::Clamp(X, 0.f, 1.f);
		return X * X * (3.f - 2.f * X);
	}

	/** Rotation-rate limited approach of an angle (degrees). */
	inline float StepAngle(float Current, float Target, float MaxDelta)
	{
		return Current + FMath::Clamp(FMath::FindDeltaAngleDegrees(Current, Target), -MaxDelta, MaxDelta);
	}
}
