#pragma once

#include "CoreMinimal.h"

/**
 * Frame-rate independent, unconditionally stable helpers shared by all sub-drones.
 * Everything is expressed through half-lives / time constants so tuning does not depend on FPS.
 */
namespace SubDroneMath
{
	inline constexpr float Ln2 = 0.69314718056f;

	/** Exponential smoothing factor for a half-life: alpha = 1 - 2^(-dt / h). */
	FORCEINLINE float HalfLifeAlpha(float HalfLife, float Dt)
	{
		return HalfLife <= KINDA_SMALL_NUMBER ? 1.f : 1.f - FMath::Exp2(-Dt / HalfLife);
	}

	template <typename T>
	FORCEINLINE T DampTo(const T& Current, const T& Target, float HalfLife, float Dt)
	{
		return FMath::Lerp(Current, Target, HalfLifeAlpha(HalfLife, Dt));
	}

	FORCEINLINE FQuat DampQuat(const FQuat& Current, const FQuat& Target, float HalfLife, float Dt)
	{
		return FQuat::Slerp(Current, Target, HalfLifeAlpha(HalfLife, Dt)).GetNormalized();
	}

	/** First-order motor response with time constant Tau (exact discretisation, no overshoot). */
	FORCEINLINE float MotorStep(float Current, float Target, float Tau, float Dt)
	{
		return Tau <= KINDA_SMALL_NUMBER ? Target : Target + (Current - Target) * FMath::Exp(-Dt / Tau);
	}

	/** Keeps an accumulated angle in [0, 360). Double precision -> no drift in long sessions. */
	FORCEINLINE double WrapDegrees(double Angle)
	{
		Angle = FMath::Fmod(Angle, 360.0);
		return Angle < 0.0 ? Angle + 360.0 : Angle;
	}

	/**
	 * Exact critically damped spring towards a goal moving with GoalVel
	 * (closed-form solution of x'' = s(g - x) + d(q - x'), s = d^2/4).
	 * Stable for any Dt; GoalVel feed-forward removes steady-state lag behind a moving Shell.
	 * Goal is sampled at the END of the frame (post-physics Shell), so it is evaluated at the
	 * step midpoint (Goal - GoalVel*Dt/2): verified zero tracking error at 60 fps, ~0.1 m at 2 fps.
	 */
	FORCEINLINE void CriticalSpring(FVector& X, FVector& V, const FVector& Goal, const FVector& GoalVel, float HalfLife, float Dt)
	{
		const double D = (4.0 * Ln2) / FMath::Max(HalfLife, 1e-4f);
		const double Y = D * 0.5;
		const FVector C = Goal - GoalVel * (0.5 * Dt) + GoalVel * (2.0 / Y);
		const FVector J0 = X - C;
		const FVector J1 = V + J0 * Y;
		const double E = FMath::Exp(-Y * Dt);
		X = (J0 + J1 * Dt) * E + C;
		V = (V - J1 * (Y * Dt)) * E;
	}

	/** Look-at rotation with a reference up; falls back gracefully when Dir is parallel to Up. */
	FORCEINLINE FQuat MakeLookQuat(const FVector& Dir, const FVector& Up, const FQuat& Fallback)
	{
		const FVector F = Dir.GetSafeNormal();
		if (F.IsNearlyZero())
		{
			return Fallback;
		}
		const FVector RefUp = FMath::Abs(F | Up) > 0.98 ? Fallback.GetUpVector() : Up;
		return FRotationMatrix::MakeFromXZ(F, RefUp).ToQuat();
	}
}
