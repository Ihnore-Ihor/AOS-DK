#pragma once

#include "CoreMinimal.h"
#include "SubDroneTypes.generated.h"

AOS_DK_API DECLARE_LOG_CATEGORY_EXTERN(LogSubDrone, Log, All);

/**
 * Mobility layer shared by every Shell module-drone (Attacker, Defender, Pathfinder, ...).
 *  Formation - passive: flies with the Shell in the crescent formation, always in view.
 *  Deployed  - active: stepped out to its working position (R), ready for its primary action.
 *  Docking   - flying to its hull socket for a physical resupply.
 *  Docked    - attached to the hull socket (resupply in progress).
 * Formation <-> Deployed is a continuous blend (no hard snap), see ASubDroneBase::DeployBlend.
 */
UENUM(BlueprintType)
enum class ESubDroneMobilityState : uint8
{
	Formation UMETA(DisplayName = "Formation"),
	Deployed  UMETA(DisplayName = "Deployed"),
	Docking   UMETA(DisplayName = "Docking"),
	Docked    UMETA(DisplayName = "Docked")
};

/** Answer of a module drone to a manual reload request (IA_Sub_DroneReload, RMB). */
UENUM(BlueprintType)
enum class ESubDroneReloadResult : uint8
{
	Accepted     UMETA(DisplayName = "Accepted"),           // the next magazine is being loaded
	NotSupported UMETA(DisplayName = "Not supported"),      // the module has nothing to reload
	Busy         UMETA(DisplayName = "Busy"),               // a reload is already running
	Full         UMETA(DisplayName = "Ring full"),
	NoReserve    UMETA(DisplayName = "Reserve empty"),      // only the Shell (hull socket / dock) can rearm it
	Unavailable  UMETA(DisplayName = "Unavailable"),        // docking / being serviced: rearmed automatically
	NoPower      UMETA(DisplayName = "Insufficient power")  // the Shell core cannot pay the reload
};

/** Motion feel of one mobility mode. Distances in cm, times in seconds. */
USTRUCT(BlueprintType)
struct FSubDroneMotionProfile
{
	GENERATED_BODY()

	/** Spring half-life inside the comfort zone. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion", meta = (ClampMin = "0.02", Units = "s"))
	float ComfortHalfLife = 0.3f;

	/** Spring half-life at (and beyond) the leash radius. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion", meta = (ClampMin = "0.02", Units = "s"))
	float CatchUpHalfLife = 0.12f;

	/** Radius around the slot in which the drone may drift freely. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion", meta = (ClampMin = "0", Units = "cm"))
	float ComfortRadius = 40.f;

	/** Distance at which the spring reaches CatchUpHalfLife. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion", meta = (ClampMin = "1", Units = "cm"))
	float LeashRadius = 300.f;

	/** Half-life of the filtered Shell frame (how long sharp Shell turns are absorbed). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion", meta = (ClampMin = "0", Units = "s"))
	float HostFrameHalfLife = 0.2f;

	/** 0 = keep the horizon, 1 = follow the Shell roll completely. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion", meta = (ClampMin = "0", ClampMax = "1"))
	float HostRollInfluence = 0.25f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion", meta = (ClampMin = "0", Units = "s"))
	float OrientationHalfLife = 0.2f;

	/** Organic float folded into the spring goal (no extra transform updates). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion", meta = (ClampMin = "0", Units = "cm"))
	float BobAmplitude = 5.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motion", meta = (ClampMin = "0", Units = "Hz"))
	float BobFrequency = 0.3f;

	static FSubDroneMotionProfile Lerp(const FSubDroneMotionProfile& A, const FSubDroneMotionProfile& B, float Alpha)
	{
		FSubDroneMotionProfile R;
		R.ComfortHalfLife     = FMath::Lerp(A.ComfortHalfLife, B.ComfortHalfLife, Alpha);
		R.CatchUpHalfLife     = FMath::Lerp(A.CatchUpHalfLife, B.CatchUpHalfLife, Alpha);
		R.ComfortRadius       = FMath::Lerp(A.ComfortRadius, B.ComfortRadius, Alpha);
		R.LeashRadius         = FMath::Lerp(A.LeashRadius, B.LeashRadius, Alpha);
		R.HostFrameHalfLife   = FMath::Lerp(A.HostFrameHalfLife, B.HostFrameHalfLife, Alpha);
		R.HostRollInfluence   = FMath::Lerp(A.HostRollInfluence, B.HostRollInfluence, Alpha);
		R.OrientationHalfLife = FMath::Lerp(A.OrientationHalfLife, B.OrientationHalfLife, Alpha);
		R.BobAmplitude        = FMath::Lerp(A.BobAmplitude, B.BobAmplitude, Alpha);
		R.BobFrequency        = FMath::Lerp(A.BobFrequency, B.BobFrequency, Alpha);
		return R;
	}
};

/** Custom Primitive Data layout shared by the drone materials (no MIDs -> no draw-command invalidation). */
namespace SubDroneCPD
{
	inline constexpr int32 GlowIntensity  = 0;
	inline constexpr int32 PulsePhase     = 1;
	inline constexpr int32 PulseDirection = 2;
	inline constexpr int32 SpinAlpha      = 3;
	inline constexpr int32 AlertAlpha     = 4;
	inline constexpr int32 Heat           = 5;
	/** Torpedo materials (ring ISM + flying torpedo): induction charge 0..1. */
	inline constexpr int32 TorpedoCharge  = 0;
}
