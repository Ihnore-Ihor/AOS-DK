#pragma once

#include "CoreMinimal.h"
#include "UObject/ObjectMacros.h"
#include "AOS_ReaperTypes.generated.h"

class AMicroTorpedo;

DECLARE_LOG_CATEGORY_EXTERN(LogAOSAI, Log, All);

UENUM(BlueprintType)
enum class EAOSThreatLevel : uint8 { None, Suspicious, Hostile };

UENUM(BlueprintType)
enum class EAOSLocomotionMode : uint8 { Walk, Investigate, Scuttle, Combat };

UENUM(BlueprintType)
enum class EAOSReaperPhase : uint8
{
	Patrol, Survey, Investigate, Chase, Shadow, StrikeWindup, StrikeThrust, StrikeRecover, Evading, Dead
};

/** Gait table row (spec 3.6.1). */
UENUM(BlueprintType)
enum class EAOSGaitMode : uint8 { Walk, Investigate, Scuttle, Skitter, Brine };

/** What the dorsal arm is doing; drives the procedural arm IK. */
UENUM(BlueprintType)
enum class EAOSArmMode : uint8 { Stowed, Guard, Windup, Thrust, Recover };

/** Page map frame colour = alert state. */
UENUM(BlueprintType)
enum class EAOSPageAlert : uint8 { Patrol, Investigate, Combat, Critical, Brine };

/** Blackboard key names (spec 3.4), kept for the BT layer. */
namespace AOSReaperBB
{
	inline const FName SelfActor = TEXT("SelfActor");                   // Object
	inline const FName TargetActor = TEXT("TargetActor");               // Object (AShellPawn)
	inline const FName ThreatLevel = TEXT("ThreatLevel");               // Enum EAOSThreatLevel ("combat state")
	inline const FName bHasLineOfSight = TEXT("bHasLineOfSight");       // Bool
	inline const FName TargetDistance = TEXT("TargetDistance");         // Float, arm turret -> closest hull point (cm)
	inline const FName TargetGroundPoint = TEXT("TargetGroundPoint");   // Vector, Shell projected onto the NavMesh
	inline const FName bInStrikeEnvelope = TEXT("bInStrikeEnvelope");   // Bool
	inline const FName bTargetAboveReach = TEXT("bTargetAboveReach");   // Bool
	inline const FName LastKnownLocation = TEXT("LastKnownLocation");   // Vector
	inline const FName InvestigateLocation = TEXT("InvestigateLocation"); // Vector (on NavMesh)
	inline const FName PatrolLocation = TEXT("PatrolLocation");         // Vector
	inline const FName PatrolNodeIndex = TEXT("PatrolNodeIndex");       // Int
	inline const FName bIsEvading = TEXT("bIsEvading");                 // Bool
	inline const FName bInHazard = TEXT("bInHazard");                   // Bool
}

/** One aggregated torpedo salvo (see UAOS_CombatThreatSubsystem). */
struct FAOSTorpedoSalvo
{
	int32 SalvoId = 0;
	TWeakObjectPtr<AActor> Instigator;
	TWeakObjectPtr<AActor> AimActor;
	FVector FirstLaunchOrigin = FVector::ZeroVector;
	FVector AimPoint = FVector::ZeroVector;
	double OpenTime = 0.0;
	TArray<TWeakObjectPtr<AMicroTorpedo>> Torpedoes;
};

/** Everything the game thread hands to the native animation proxy (component space, cm / degrees). */
struct FAOS_ReaperPoseInput
{
	/** Leg order: L1 L2 L3 R1 R2 R3. Foot-bone origin targets in component space. */
	FVector FootTargets[6] = { FVector::ZeroVector, FVector::ZeroVector, FVector::ZeroVector, FVector::ZeroVector, FVector::ZeroVector, FVector::ZeroVector };
	/** Body delta about the ref body pivot (component space). */
	FVector BodyOffset = FVector::ZeroVector;
	FQuat BodyRotation = FQuat::Identity;

	/** Mast angles relative to the body (already rate limited and clamped on the game thread). */
	float MastYawDeg = 0.f;
	float MastPitchDeg = 0.f;

	/** Arm: pike tip target + pike axis (component space). */
	FVector ArmTipTarget = FVector::ZeroVector;
	FVector ArmAimDir = FVector::ForwardVector;
	float ArmAlpha = 0.f;

	float JawOpenDeg = 0.f;
};
