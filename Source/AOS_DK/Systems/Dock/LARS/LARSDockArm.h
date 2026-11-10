#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LARSArmAnimInstance.h"
#include "LARSDockArm.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class USkeletalMeshComponent;
class UNiagaraSystem;
class UCameraComponent;
class UBoxComponent;
class UCapsuleComponent;
class UPrimitiveComponent;
class APlayerController;
class AShellPawn;
class AShellDock;

/** Launch-and-recovery state of the dock arm. */
UENUM(BlueprintType)
enum class ELARSArmPhase : uint8
{
	/** No Shell in the cradle and no sequence running (arm parked). */
	Stowed,
	/** Shell-1 clamped at SOCKET_Submarine_Mount, suspended above the waves. */
	Holding,
	/** Launch: lowering the Shell through the waterline. */
	Lowering,
	/** Launch: jaws opening (the hull is let go part-way through). */
	Releasing,
	/** Launch: gripper backs off up and in, clear of the hull; 6DOF is handed over at the end. */
	Retracting,
	/** Launch: arm returns to its parked pose above the water. */
	Stowing,
	/** Recovery: the Shell is guided to the capture point under the arm. */
	Aligning,
	/** Recovery: arm comes down with open jaws to just above the hull. */
	Approaching,
	/** Recovery: last centimetres onto the capture pad. */
	Engaging,
	/** Recovery: jaws close around the hull. */
	Clamping,
	/** Recovery: Shell lifted out of the water to the holding pose. */
	Lifting
};

/** Cartesian target of the gripper: SOCKET_Submarine_Mount position in the arm's yaw plane, wrist always pointing down. */
USTRUCT(BlueprintType)
struct AOS_DK_API FLARSArmTarget
{
	GENERATED_BODY()

	/** Horizontal distance from the turret yaw axis to the socket. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "LARS", meta = (Units = "cm"))
	float Reach = 1000.f;

	/** World Z of the socket (= Shell-1 centre). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "LARS", meta = (Units = "cm"))
	float WorldZ = 400.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "LARS", meta = (Units = "deg"))
	float JawOpen = 0.f;

	FLARSArmTarget() = default;
	FLARSArmTarget(float InReach, float InWorldZ, float InJaw) : Reach(InReach), WorldZ(InWorldZ), JawOpen(InJaw) {}
};

/** Live hydraulic cylinder readout (for tests / debug HUD). */
USTRUCT(BlueprintType)
struct AOS_DK_API FLARSPistonState
{
	GENERATED_BODY()

	/** Trunnion-to-eye length. */
	UPROPERTY(BlueprintReadOnly, Category = "LARS") float Length = 0.f;
	/** Barrel/rod telescope overlap (barrel body + rod - length); keep >= 30. */
	UPROPERTY(BlueprintReadOnly, Category = "LARS") float Overlap = 0.f;
	/** Angle between the barrel bone axis and the trunnion->eye line. */
	UPROPERTY(BlueprintReadOnly, Category = "LARS") float BarrelAxisErrorDeg = 0.f;
	/** Angle between the rod bone axis and the eye->trunnion line. */
	UPROPERTY(BlueprintReadOnly, Category = "LARS") float RodAxisErrorDeg = 0.f;
	/** Angle between the barrel and rod axes (0 = coaxial). */
	UPROPERTY(BlueprintReadOnly, Category = "LARS") float CoaxialErrorDeg = 0.f;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FLARSArmShellEvent, AShellPawn*, Shell);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FLARSArmPhaseEvent, ELARSArmPhase, NewPhase);

/**
 * SK_LARS_RoboticArm on the dock pedestal: holds Shell-1 above the waves at SOCKET_Submarine_Mount, lowers it into the
 * water on boarding (launch) and picks it back up on docking (recovery). Joint angles come from a planar 2-link IK with
 * the wrist kept pointing straight down; ULARSArmAnimInstance (ABP_LARS_RoboticArm) applies them + the piston Aims.
 */
UCLASS(Blueprintable, meta = (DisplayName = "AOS LARS Dock Arm"))
class AOS_DK_API ALARSDockArm : public AActor
{
	GENERATED_BODY()

public:
	ALARSDockArm();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	// --- Sequences ---------------------------------------------------------------------------------
	/** Boarding: lower the clamped Shell into the water, release, retract, hand 6DOF + HUD to the pilot. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|LARS")
	bool BeginLaunch();

	/** Docking: align the Shell under the arm, capture, lift it into the holding pose, then notify the dock. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|LARS")
	bool BeginRecovery(AShellPawn* InShell, AShellDock* RequestingDock);

	/**
	 * Boarding: blends PC's view to LaunchCam (the external cinematic camera on the pier). The dock possesses the
	 * Shell once the blend is done, without letting the possess steal the view. False = cinematics off.
	 */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|LARS")
	bool BeginCinematic(APlayerController* PC, float& OutBlendTime);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	bool IsCinematicActive() const { return bCinematicActive; }

	/** Instantly clamps the Shell in the holding pose (level start, Kernel Panic recovery). Cancels any sequence. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|LARS")
	void SnapToHold(AShellPawn* InShell);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	ELARSArmPhase GetPhase() const { return Phase; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	bool IsHoldingShell() const { return Phase == ELARSArmPhase::Holding && HeldShell.IsValid(); }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	bool IsBusy() const { return Phase != ELARSArmPhase::Holding && Phase != ELARSArmPhase::Stowed; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	bool CanRecover() const { return Phase == ELARSArmPhase::Stowed; }

	/** World transform the Shell has while clamped in the holding pose. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	FTransform GetHoldTransform() const { return GetShellTransformAt(HoldTarget()); }

	/** World transform the Shell must reach to be captured (= released) at depth. */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	FTransform GetCaptureTransform() const { return GetShellTransformAt(CaptureTarget()); }

	/** Planar IK: joint angles that put SOCKET_Submarine_Mount at Target with the wrist pointing down. False = clamped. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|LARS")
	bool SolveArmIK(const FLARSArmTarget& Target, FLARSArmJointPose& OutPose) const;

	/** [0] shoulder, [1] elbow cylinder, measured on the evaluated bones. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|LARS")
	TArray<FLARSPistonState> GetPistonStates() const;

	/** Distance between the jaw claw lips (bigger = more open). */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	float GetJawGap() const;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	FLARSArmJointPose GetCurrentJointPose() const { return CurrentPose; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	bool WasLastSolveClamped() const { return bLastSolveClamped; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	AShellPawn* GetHeldShell() const { return HeldShell.Get(); }

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|LARS")
	FLARSArmShellEvent OnShellLaunched;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|LARS")
	FLARSArmShellEvent OnShellRecovered;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|LARS")
	FLARSArmPhaseEvent OnPhaseChanged;

	USkeletalMeshComponent* GetArmMesh() const { return ArmMesh; }

protected:
	//~ Components
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS")
	TObjectPtr<USceneComponent> Mount;

	/** Plinth bolted to the pier deck under the collar. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS")
	TObjectPtr<UStaticMeshComponent> Pedestal;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS")
	TObjectPtr<USkeletalMeshComponent> ArmMesh;

	/** External cinematic camera (placed on the pier by Tools/setup_lars_dock_sequence.py); tracks the arm + Shell. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Camera")
	TObjectPtr<UCameraComponent> LaunchCam;

	//~ Pawn collision: simplified blocking shapes on the bones (the mesh itself has no Physics Asset bodies).
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UStaticMeshComponent> CollarCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UBoxComponent> TurretCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UBoxComponent> ClevisCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UBoxComponent> BoomCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UBoxComponent> ForearmCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UBoxComponent> TailLeverCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UBoxComponent> GripperCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UBoxComponent> JawLCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UBoxComponent> JawRCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UCapsuleComponent> ShoulderCylCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Collision")
	TObjectPtr<UCapsuleComponent> ElbowCylCollision;

	//~ Cinematic camera
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Camera")
	bool bUseCinematicCamera = true;

	/** On-foot / cockpit view -> LaunchCam. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Camera", meta = (ClampMin = "0.1", Units = "s"))
	float CinematicBlendInTime = 1.5f;

	/** LaunchCam -> cockpit, starting the moment the jaws are open and the retract begins. HUD + 6DOF at its end. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Camera", meta = (ClampMin = "0.1", Units = "s"))
	float CockpitBlendTime = 1.4f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Camera", meta = (ClampMin = "10", ClampMax = "120", Units = "deg"))
	float CinematicFOV = 70.f;

	/** LaunchCam aims at lerp(elbow joint, Shell, weight): the whole arm + payload stay framed. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Camera", meta = (ClampMin = "0", ClampMax = "1"))
	float CameraFocusShellWeight = 0.6f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Camera", meta = (ClampMin = "0"))
	float CameraTrackSpeed = 1.5f;

	//~ References
	/** Shell-1 (auto-resolved when empty). */
	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "AOS_DK|LARS")
	TObjectPtr<AShellPawn> Shell;

	/** Clamp the Shell in the holding pose at BeginPlay. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS")
	bool bStartHoldingShell = true;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS")
	FName MountSocket = TEXT("SOCKET_Submarine_Mount");

	/** Height of the collar above the actor origin (the plinth). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "cm"))
	float PedestalHeight = 30.f;

	//~ Berth layout (world)
	/** Turret yaw axis -> Shell centre, horizontal. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "cm"))
	float BerthReach = 1020.f;

	/** Shell-1 heading while in the cradle (world yaw); the wrist roll turns the hull to it. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "deg"))
	float BerthHeading = -90.f;

	/** Base_Yaw of the turret during the sequences. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "deg"))
	float BerthBaseYaw = 0.f;

	/** Shell centre while held: hull keel (-80) and fins stay clear of the analytic wave crest (A sum 320). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "cm"))
	float HoldWorldZ = 420.f;

	/** Shell centre at release / capture: hull, sail and mast fully below the waterline and the pier slab. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "cm"))
	float ReleaseWorldZ = -300.f;

	/** After the release the gripper backs off by this much reach (- = toward the turret) ... */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "cm"))
	float RetractReachDelta = -80.f;

	/** ... and rises by this much above the release point. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "cm"))
	float RetractRise = 300.f;

	/** Parked pose while the Shell is out (above the water). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "cm"))
	float StowReachDelta = -60.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "cm"))
	float StowWorldZ = 460.f;

	/** Recovery: the open jaws stop this far above the capture point before the final slow engage. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Layout", meta = (Units = "cm"))
	float PreCaptureRise = 40.f;

	//~ Jaws
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Jaws", meta = (Units = "deg"))
	float JawOpenAngle = 30.f;

	/** Clamped on the hull: squeeze past the bind pose (the hull is 150 wide at the pads, the bind clearance 208). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Jaws", meta = (Units = "deg"))
	float JawClampAngle = -9.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Jaws", meta = (Units = "deg"))
	float JawStowAngle = 10.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Jaws", meta = (ClampMin = "0.1", Units = "s"))
	float JawTime = 1.2f;

	/** The hull is let go once the jaws have opened this fraction of the way. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Jaws", meta = (ClampMin = "0", ClampMax = "1"))
	float ReleaseAtJawFraction = 0.35f;

	//~ Motion
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Motion", meta = (ClampMin = "1", Units = "cm/s"))
	float LowerSpeed = 140.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Motion", meta = (ClampMin = "1", Units = "cm/s"))
	float LiftSpeed = 140.f;

	/** Unloaded gripper moves (retract, stow, approach). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Motion", meta = (ClampMin = "1", Units = "cm/s"))
	float MoveSpeed = 200.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Motion", meta = (ClampMin = "0.1", Units = "s"))
	float EngageTime = 0.9f;

	/** Recovery: speed of the Shell's guided alignment to the capture point. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Motion", meta = (ClampMin = "1", Units = "cm/s"))
	float AlignSpeed = 250.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Motion", meta = (ClampMin = "0.1", Units = "s"))
	float MinMoveTime = 1.2f;

	//~ Joint limits (stroke-safe envelope, see AOS_LARS_RoboticArm_Rig_EN.md)
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Limits", meta = (Units = "deg"))
	FVector2D ShoulderLimits = FVector2D(-12.f, 60.f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Limits", meta = (Units = "deg"))
	FVector2D ElbowLimits = FVector2D(-105.f, 18.f);

	/** Barrel body / rod lengths from the trunnion / eye (for the overlap readout): shoulder, elbow. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|Limits")
	FVector4 PistonBodyLengths = FVector4(220.f, 195.f, 211.f, 205.f);

	//~ FX
	/** Optional splash when the hull crosses the waterline (launch and recovery). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|FX")
	TObjectPtr<UNiagaraSystem> SplashFX;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS|FX", meta = (Units = "cm"))
	float WaterSurfaceZ = 40.f;

private:
	struct FSegment
	{
		FLARSArmTarget From;
		FLARSArmTarget To;
		float Duration = 1.f;
		float Elapsed = 0.f;
		bool bJawOnly = false;
	};

	void CacheRigGeometry();
	FLARSArmTarget HoldTarget() const { return FLARSArmTarget(BerthReach, HoldWorldZ, JawClampAngle); }
	FLARSArmTarget CaptureTarget() const { return FLARSArmTarget(BerthReach, ReleaseWorldZ, JawOpenAngle); }
	FLARSArmTarget RetractTarget() const { return FLARSArmTarget(BerthReach + RetractReachDelta, ReleaseWorldZ + RetractRise, JawOpenAngle); }
	FLARSArmTarget StowTarget() const { return FLARSArmTarget(BerthReach + StowReachDelta, StowWorldZ, JawStowAngle); }
	FLARSArmTarget PreCaptureTarget() const { return FLARSArmTarget(BerthReach, ReleaseWorldZ + PreCaptureRise, JawOpenAngle); }

	FTransform GetShellTransformAt(const FLARSArmTarget& Target) const;
	float GetCollarWorldZ() const;
	float WristRollForHeading() const;

	void SetPhase(ELARSArmPhase NewPhase);
	void StartSegment(const FLARSArmTarget& To, float Duration, bool bJawOnly = false);
	float MoveTime(const FLARSArmTarget& A, const FLARSArmTarget& B, float Speed) const;
	void ApplyTarget(const FLARSArmTarget& Target);
	void PushPose();
	void ForceEvaluate();
	void OnSegmentFinished();

	void BlendToCockpit(AShellPawn* S);
	void HandCockpitToPilot();
	void StopCinematic();
	FVector GetCameraFocus() const;
	void UpdateCinematicCamera(float DeltaSeconds, bool bSnap);

	void AttachShell(AShellPawn* InShell);
	void ReleaseShell();
	void TickSplash();

	ELARSArmPhase Phase = ELARSArmPhase::Stowed;
	FSegment Segment;
	bool bSegmentActive = false;
	FLARSArmTarget CurrentTarget;
	FLARSArmJointPose CurrentPose;
	bool bLastSolveClamped = false;
	bool bReleasedThisCycle = false;
	bool bControlGranted = false;
	bool bCinematicActive = false;
	bool bAwaitingCockpit = false;
	float CockpitBlendElapsed = 0.f;
	float LastDeltaSeconds = 0.f;
	TWeakObjectPtr<APlayerController> CinematicPC;
	FTimerHandle CameraTimer;

	TWeakObjectPtr<AShellPawn> HeldShell;      // clamped in the jaws
	TWeakObjectPtr<AShellPawn> ActiveShell;    // subject of the running sequence
	TWeakObjectPtr<AShellDock> RecoveryDock;

	// Shell alignment glide (recovery)
	FTransform AlignFrom;
	FTransform AlignTo;
	float AlignDuration = 1.f;
	float AlignElapsed = 0.f;

	float LastShellBottomZ = 0.f;
	bool bHasLastShellBottom = false;

	// Rig geometry in the arm's yaw plane (X = reach, Z = up, from the collar), cached from the reference skeleton
	FVector2D ShoulderPivot = FVector2D(50.f, 250.f);
	float BoomLength = 620.f;
	float ForearmLength = 520.f;
	float EffectorLength = 255.f;   // Wrist_Pitch -> Wrist_Roll -> SOCKET_Submarine_Mount
	float BoomBindAngle = 0.f;      // radians, absolute direction in bind
	float ForearmBindAngle = 0.f;
	float EffectorBindAngle = 0.f;
	bool bRigCached = false;
};
