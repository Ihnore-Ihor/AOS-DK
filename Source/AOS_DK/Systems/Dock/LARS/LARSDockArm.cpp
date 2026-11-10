#include "LARSDockArm.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "AOS_DK/Systems/Dock/ShellDock.h"
#include "AOS_DK/Player/PlayerController/AdminPlayerController.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/SkeletalMeshSocket.h"
#include "Engine/StaticMesh.h"
#include "AnimationRuntime.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraFunctionLibrary.h"
#include "UObject/ConstructorHelpers.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/PlayerController.h"
#include "TimerManager.h"

namespace
{
	float SmootherStep(float X)
	{
		X = FMath::Clamp(X, 0.f, 1.f);
		return X * X * X * (X * (X * 6.f - 15.f) + 10.f);
	}

	/** Steel blocks the on-foot character (Pawn); structural parts also stop a free-flying Shell (PhysicsBody). */
	void ConfigureArmCollision(UPrimitiveComponent* C, bool bBlockShell)
	{
		C->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		C->SetCollisionObjectType(ECC_WorldDynamic);
		C->SetCollisionResponseToAllChannels(ECR_Ignore);
		C->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
		if (bBlockShell)
		{
			C->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Block);
		}
		C->SetCanEverAffectNavigation(false);
		C->CanCharacterStepUpOn = ECB_No;
		C->SetHiddenInGame(true);
	}
}

ALARSDockArm::ALARSDockArm()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;

	Mount = CreateDefaultSubobject<USceneComponent>(TEXT("Mount"));
	RootComponent = Mount;

	Pedestal = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pedestal"));
	Pedestal->SetupAttachment(Mount);
	Pedestal->SetCollisionProfileName(TEXT("BlockAll"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	if (CylinderMesh.Succeeded())
	{
		Pedestal->SetStaticMesh(CylinderMesh.Object);
	}

	ArmMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("ArmMesh"));
	ArmMesh->SetupAttachment(Mount);
	ArmMesh->SetCollisionProfileName(TEXT("NoCollision"));
	ArmMesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	ArmMesh->AnimClass = ULARSArmAnimInstance::StaticClass();
	// The Shell rides on a bone socket: the pose must update even when the arm is off-screen (pilot in the cockpit).
	ArmMesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	ArmMesh->bEnableUpdateRateOptimizations = false;
#if WITH_EDITOR
	ArmMesh->SetUpdateAnimationInEditor(true);   // editor preview of the holding pose
#endif
	// Pawn collision. Bone-space boxes from the Max build (Tools/max_build_SK_LARS_RoboticArm.py), the main joints are
	// world-aligned in bind so their bone frames equal the bind component frame; piston bones run +X along the cylinder.
	auto MakeBox = [this](const TCHAR* Name, const TCHAR* Bone, const FVector& RelLoc, const FVector& Extent, bool bBlockShell)
	{
		UBoxComponent* Box = CreateDefaultSubobject<UBoxComponent>(Name);
		Box->SetupAttachment(ArmMesh, FName(Bone));
		Box->SetRelativeLocation(RelLoc);
		Box->InitBoxExtent(Extent);
		ConfigureArmCollision(Box, bBlockShell);
		return Box;
	};
	TurretCollision    = MakeBox(TEXT("TurretCollision"),    TEXT("Base_Yaw_Bone"),       FVector(-54.f, 0.f, 68.f),    FVector(124.f, 98.f, 68.f), true);
	ClevisCollision    = MakeBox(TEXT("ClevisCollision"),    TEXT("Base_Yaw_Bone"),       FVector(50.f, 0.f, 187.5f),   FVector(70.f, 72.f, 72.5f), true);
	BoomCollision      = MakeBox(TEXT("BoomCollision"),      TEXT("Shoulder_Pitch_Bone"), FVector(342.5f, 0.f, 1.f),    FVector(307.5f, 54.f, 55.f), true);
	ForearmCollision   = MakeBox(TEXT("ForearmCollision"),   TEXT("Elbow_Pitch_Bone"),    FVector(248.5f, 0.f, 0.f),    FVector(286.5f, 45.f, 38.f), true);
	TailLeverCollision = MakeBox(TEXT("TailLeverCollision"), TEXT("Elbow_Pitch_Bone"),    FVector(-10.f, 0.f, 56.f),    FVector(40.f, 30.f, 56.f), true);
	// Gripper + jaws work around the hull: they block the character only, never the Shell they carry.
	GripperCollision   = MakeBox(TEXT("GripperCollision"),   TEXT("Wrist_Roll_Bone"),     FVector(20.f, 0.f, 0.f),      FVector(80.f, 150.f, 74.f), false);
	JawLCollision      = MakeBox(TEXT("JawLCollision"),      TEXT("Jaw_L_Bone"),          FVector(80.f, 7.f, 0.f),      FVector(100.f, 21.f, 70.f), false);
	JawRCollision      = MakeBox(TEXT("JawRCollision"),      TEXT("Jaw_R_Bone"),          FVector(80.f, -7.f, 0.f),     FVector(100.f, 21.f, 70.f), false);
	auto MakeCylinder = [this](const TCHAR* Name, const TCHAR* Bone, float Center, float Radius, float HalfHeight)
	{
		UCapsuleComponent* Cap = CreateDefaultSubobject<UCapsuleComponent>(Name);
		Cap->SetupAttachment(ArmMesh, FName(Bone));
		Cap->SetRelativeLocationAndRotation(FVector(Center, 0.f, 0.f), FRotator(90.f, 0.f, 0.f));   // capsule Z -> bone X
		Cap->InitCapsuleSize(Radius, HalfHeight);
		ConfigureArmCollision(Cap, true);
		return Cap;
	};
	ShoulderCylCollision = MakeCylinder(TEXT("ShoulderCylCollision"), TEXT("Shoulder_Cyl_Barrel_Bone"), 130.f, 22.f, 140.f);
	ElbowCylCollision    = MakeCylinder(TEXT("ElbowCylCollision"),    TEXT("Elbow_Cyl_Barrel_Bone"),    125.f, 20.f, 135.f);

	CollarCollision = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("CollarCollision"));
	CollarCollision->SetupAttachment(ArmMesh);
	CollarCollision->SetRelativeLocation(FVector(0.f, 0.f, 30.f));
	CollarCollision->SetRelativeScale3D(FVector(2.5f, 2.5f, 0.6f));   // Ø250 x 60 mounting collar
	ConfigureArmCollision(CollarCollision, true);
	CollarCollision->SetCastShadow(false);
	CollarCollision->SetVisibility(false);
	if (CylinderMesh.Succeeded())
	{
		CollarCollision->SetStaticMesh(CylinderMesh.Object);
	}

	LaunchCam = CreateDefaultSubobject<UCameraComponent>(TEXT("LaunchCam"));
	LaunchCam->SetupAttachment(Mount);
	LaunchCam->SetRelativeLocation(FVector(800.f, -1200.f, 870.f));
	LaunchCam->bConstrainAspectRatio = false;
	LaunchCam->FieldOfView = 70.f;

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> ArmAsset(TEXT("/Game/AOS_DK_Game/Environment/CustomHero/SK_LARS_RoboticArm.SK_LARS_RoboticArm"));
	if (ArmAsset.Succeeded())
	{
		ArmMesh->SetSkeletalMeshAsset(ArmAsset.Object);
	}
}

// ==================================================================================================
// Rig geometry + IK
// ==================================================================================================
void ALARSDockArm::CacheRigGeometry()
{
	const USkeletalMesh* Mesh = ArmMesh ? ArmMesh->GetSkeletalMeshAsset() : nullptr;
	if (!Mesh)
	{
		return;
	}
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	const FLARSArmBoneNames Names;
	const int32 IShoulder = Ref.FindBoneIndex(Names.Shoulder);
	const int32 IElbow = Ref.FindBoneIndex(Names.Elbow);
	const int32 IWrist = Ref.FindBoneIndex(Names.WristPitch);
	const int32 IRoll = Ref.FindBoneIndex(Names.WristRoll);
	const USkeletalMeshSocket* Socket = Mesh->FindSocket(MountSocket);
	if (IShoulder == INDEX_NONE || IElbow == INDEX_NONE || IWrist == INDEX_NONE || IRoll == INDEX_NONE || !Socket)
	{
		UE_LOG(LogTemp, Warning, TEXT("LARSDockArm: rig bones / %s not found on %s"), *MountSocket.ToString(), *Mesh->GetName());
		return;
	}
	auto XZ = [](const FVector& V) { return FVector2D(V.X, V.Z); };
	const FVector2D S = XZ(FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, IShoulder).GetLocation());
	const FVector2D E = XZ(FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, IElbow).GetLocation());
	const FVector2D W = XZ(FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, IWrist).GetLocation());
	const FTransform RollCS = FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, IRoll);
	const FVector2D T = XZ(RollCS.TransformPosition(Socket->RelativeLocation));

	ShoulderPivot = S;
	BoomLength = (E - S).Size();
	ForearmLength = (W - E).Size();
	EffectorLength = (T - W).Size();
	BoomBindAngle = FMath::Atan2(E.Y - S.Y, E.X - S.X);
	ForearmBindAngle = FMath::Atan2(W.Y - E.Y, W.X - E.X);
	EffectorBindAngle = FMath::Atan2(T.Y - W.Y, T.X - W.X);
	bRigCached = true;
}

float ALARSDockArm::GetCollarWorldZ() const
{
	return ArmMesh ? float(ArmMesh->GetComponentLocation().Z) : float(GetActorLocation().Z) + PedestalHeight;
}

float ALARSDockArm::WristRollForHeading() const
{
	const float MeshYaw = ArmMesh ? float(ArmMesh->GetComponentRotation().Yaw) : float(GetActorRotation().Yaw);
	return FRotator::NormalizeAxis(BerthHeading - MeshYaw - BerthBaseYaw);
}

bool ALARSDockArm::SolveArmIK(const FLARSArmTarget& Target, FLARSArmJointPose& OutPose) const
{
	bool bClamped = false;
	const float Height = Target.WorldZ - GetCollarWorldZ();
	// Wrist pointing straight down: the wrist-pitch pivot sits EffectorLength above the socket.
	const FVector2D W(Target.Reach, Height + EffectorLength);
	const FVector2D D = W - ShoulderPivot;
	float Dist = D.Size();
	const float MinD = FMath::Abs(BoomLength - ForearmLength) + 1.f;
	const float MaxD = BoomLength + ForearmLength - 1.f;
	if (Dist < MinD || Dist > MaxD)
	{
		bClamped = true;
		Dist = FMath::Clamp(Dist, MinD, MaxD);
	}
	const float A = FMath::Atan2(D.Y, D.X);
	const float CosB = (BoomLength * BoomLength + Dist * Dist - ForearmLength * ForearmLength) / (2.f * BoomLength * Dist);
	const float BoomAbs = A + FMath::Acos(FMath::Clamp(CosB, -1.f, 1.f));   // elbow-up branch (boom above the forearm)
	const FVector2D E = ShoulderPivot + BoomLength * FVector2D(FMath::Cos(BoomAbs), FMath::Sin(BoomAbs));
	const FVector2D WReach = ShoulderPivot + Dist * FVector2D(FMath::Cos(A), FMath::Sin(A));
	const float ForeAbs = FMath::Atan2(WReach.Y - E.Y, WReach.X - E.X);

	float Shoulder = FMath::RadiansToDegrees(BoomAbs - BoomBindAngle);
	float Elbow = FRotator::NormalizeAxis(FMath::RadiansToDegrees(ForeAbs - ForearmBindAngle) - Shoulder);
	if (Shoulder < ShoulderLimits.X || Shoulder > ShoulderLimits.Y || Elbow < ElbowLimits.X || Elbow > ElbowLimits.Y)
	{
		bClamped = true;
		Shoulder = FMath::Clamp(Shoulder, ShoulderLimits.X, ShoulderLimits.Y);
		Elbow = FMath::Clamp(Elbow, ElbowLimits.X, ElbowLimits.Y);
	}
	const float Wrist = FRotator::NormalizeAxis(-90.f - FMath::RadiansToDegrees(EffectorBindAngle) - Shoulder - Elbow);

	OutPose.BaseYaw = BerthBaseYaw;
	OutPose.ShoulderPitch = Shoulder;
	OutPose.ElbowPitch = Elbow;
	OutPose.WristPitch = Wrist;
	OutPose.WristRoll = WristRollForHeading();
	OutPose.JawOpen = Target.JawOpen;
	return !bClamped;
}

FTransform ALARSDockArm::GetShellTransformAt(const FLARSArmTarget& Target) const
{
	const float YawRad = FMath::DegreesToRadians(BerthBaseYaw);
	const FTransform MeshXf = ArmMesh ? ArmMesh->GetComponentTransform() : GetActorTransform();
	FVector Loc = MeshXf.TransformPositionNoScale(FVector(Target.Reach * FMath::Cos(YawRad), Target.Reach * FMath::Sin(YawRad), 0.f));
	Loc.Z = Target.WorldZ;
	return FTransform(FRotator(0.f, BerthHeading, 0.f), Loc);
}

// ==================================================================================================
// Lifecycle
// ==================================================================================================
void ALARSDockArm::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	if (Pedestal)
	{
		Pedestal->SetRelativeLocation(FVector(0.f, 0.f, PedestalHeight * 0.5f));
		Pedestal->SetRelativeScale3D(FVector(3.f, 3.f, FMath::Max(PedestalHeight, 1.f) / 100.f));
		Pedestal->SetVisibility(PedestalHeight > 0.5f);
	}
	if (ArmMesh)
	{
		ArmMesh->SetRelativeLocation(FVector(0.f, 0.f, PedestalHeight));
	}
	if (LaunchCam)
	{
		LaunchCam->SetFieldOfView(CinematicFOV);
	}
	// Editor preview: show the holding pose.
	CacheRigGeometry();
	CurrentTarget = HoldTarget();
	bLastSolveClamped = !SolveArmIK(CurrentTarget, CurrentPose);
	PushPose();
}

void ALARSDockArm::BeginPlay()
{
	Super::BeginPlay();
	if (ArmMesh)
	{
		ArmMesh->PrimaryComponentTick.AddPrerequisite(this, PrimaryActorTick);
	}
	CacheRigGeometry();

	if (!Shell)
	{
		Shell = Cast<AShellPawn>(UGameplayStatics::GetActorOfClass(this, AShellPawn::StaticClass()));
	}
	if (bStartHoldingShell && Shell)
	{
		SnapToHold(Shell);
	}
	else
	{
		SetPhase(ELARSArmPhase::Stowed);
		ApplyTarget(StowTarget());
		ForceEvaluate();
	}
}

void ALARSDockArm::SetPhase(ELARSArmPhase NewPhase)
{
	if (Phase != NewPhase)
	{
		Phase = NewPhase;
		OnPhaseChanged.Broadcast(NewPhase);
	}
}

void ALARSDockArm::PushPose()
{
	if (ULARSArmAnimInstance* Anim = ArmMesh ? Cast<ULARSArmAnimInstance>(ArmMesh->GetAnimInstance()) : nullptr)
	{
		Anim->JointPose = CurrentPose;
	}
}

void ALARSDockArm::ApplyTarget(const FLARSArmTarget& Target)
{
	CurrentTarget = Target;
	bLastSolveClamped = !SolveArmIK(Target, CurrentPose);
	PushPose();
}

void ALARSDockArm::ForceEvaluate()
{
	if (ArmMesh && ArmMesh->GetAnimInstance())
	{
		ArmMesh->TickAnimation(0.f, false);
		ArmMesh->RefreshBoneTransforms();
	}
}

float ALARSDockArm::MoveTime(const FLARSArmTarget& A, const FLARSArmTarget& B, float Speed) const
{
	const float Dist = FVector2D(B.Reach - A.Reach, B.WorldZ - A.WorldZ).Size();
	return FMath::Max(MinMoveTime, Dist / FMath::Max(Speed, 1.f));
}

void ALARSDockArm::StartSegment(const FLARSArmTarget& To, float Duration, bool bJawOnly)
{
	Segment.From = CurrentTarget;
	Segment.To = To;
	Segment.Duration = FMath::Max(Duration, 0.05f);
	Segment.Elapsed = 0.f;
	Segment.bJawOnly = bJawOnly;
	bSegmentActive = true;
}

// ==================================================================================================
// Shell coupling
// ==================================================================================================
void ALARSDockArm::AttachShell(AShellPawn* InShell)
{
	if (!InShell || !ArmMesh)
	{
		return;
	}
	InShell->EnterLARSCradle();
	InShell->AttachToComponent(ArmMesh, FAttachmentTransformRules(EAttachmentRule::SnapToTarget, EAttachmentRule::SnapToTarget, EAttachmentRule::KeepWorld, false), MountSocket);
	HeldShell = InShell;
	Shell = InShell;
}

void ALARSDockArm::ReleaseShell()
{
	bReleasedThisCycle = true;
	if (AShellPawn* S = HeldShell.Get())
	{
		S->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
		S->LeaveLARSCradle();
		S->PushTerminalLog(TEXT("lars"), TEXT("jaws open - hull released"), EAOSHudLogSeverity::Info);
	}
	HeldShell.Reset();
}

void ALARSDockArm::SnapToHold(AShellPawn* InShell)
{
	StopCinematic();
	bSegmentActive = false;
	ActiveShell.Reset();
	RecoveryDock.Reset();
	if (HeldShell.IsValid() && HeldShell.Get() != InShell)
	{
		ReleaseShell();
	}
	ApplyTarget(HoldTarget());
	ForceEvaluate();
	SetPhase(ELARSArmPhase::Holding);
	AttachShell(InShell);
	if (bLastSolveClamped)
	{
		UE_LOG(LogTemp, Warning, TEXT("LARSDockArm: holding pose is outside the joint envelope (reach %.0f, z %.0f)"), BerthReach, HoldWorldZ);
	}
}

// ==================================================================================================
// Sequences
// ==================================================================================================
bool ALARSDockArm::BeginLaunch()
{
	AShellPawn* S = HeldShell.Get();
	if (Phase != ELARSArmPhase::Holding || !S)
	{
		return false;
	}
	ActiveShell = S;
	bReleasedThisCycle = false;
	bControlGranted = false;
	S->SetBlockControls(true);
	if (AAdminPlayerController* PC = Cast<AAdminPlayerController>(S->GetController()))
	{
		PC->SetInteractLocked(true);
	}
	S->PushTerminalLog(TEXT("lars"), TEXT("launch: lowering through the splash zone"), EAOSHudLogSeverity::System);
	const FLARSArmTarget Release(BerthReach, ReleaseWorldZ, JawClampAngle);
	SetPhase(ELARSArmPhase::Lowering);
	StartSegment(Release, MoveTime(CurrentTarget, Release, LowerSpeed));
	return true;
}

bool ALARSDockArm::BeginRecovery(AShellPawn* InShell, AShellDock* RequestingDock)
{
	if (!InShell || !CanRecover())
	{
		return false;
	}
	ActiveShell = InShell;
	RecoveryDock = RequestingDock;
	InShell->EnterLARSCradle();   // kinematic + controls locked from here on
	if (AAdminPlayerController* PC = Cast<AAdminPlayerController>(InShell->GetController()))
	{
		PC->SetInteractLocked(true);
	}
	InShell->PushTerminalLog(TEXT("lars"), TEXT("recovery: aligning to the capture point"), EAOSHudLogSeverity::System);
	float Blend = 0.f;
	if (BeginCinematic(Cast<APlayerController>(InShell->GetController()), Blend))
	{
		InShell->SetCockpitHUDVisible(false);   // the camera leaves the cockpit
	}

	AlignFrom = InShell->GetActorTransform();
	AlignFrom.SetScale3D(FVector::OneVector);
	AlignTo = GetCaptureTransform();
	const float Dist = FVector::Dist(AlignFrom.GetLocation(), AlignTo.GetLocation());
	const float Angle = FMath::RadiansToDegrees(AlignFrom.GetRotation().AngularDistance(AlignTo.GetRotation()));
	AlignDuration = FMath::Clamp(FMath::Max(Dist / AlignSpeed, Angle / 45.f), 1.5f, 10.f);
	AlignElapsed = 0.f;
	bSegmentActive = false;
	SetPhase(ELARSArmPhase::Aligning);
	return true;
}

void ALARSDockArm::OnSegmentFinished()
{
	AShellPawn* S = ActiveShell.Get();
	switch (Phase)
	{
	case ELARSArmPhase::Lowering:
		SetPhase(ELARSArmPhase::Releasing);
		StartSegment(CaptureTarget(), JawTime, true);
		break;

	case ELARSArmPhase::Releasing:
		if (!bReleasedThisCycle)
		{
			ReleaseShell();
		}
		SetPhase(ELARSArmPhase::Retracting);
		StartSegment(RetractTarget(), MoveTime(CurrentTarget, RetractTarget(), MoveSpeed));
		BlendToCockpit(S);   // jaws open, retract begins: LaunchCam -> cockpit
		break;

	case ELARSArmPhase::Retracting:
		HandCockpitToPilot();   // no-op when the cockpit blend already handed over
		SetPhase(ELARSArmPhase::Stowing);
		StartSegment(StowTarget(), MoveTime(CurrentTarget, StowTarget(), MoveSpeed));
		break;

	case ELARSArmPhase::Stowing:
		ActiveShell.Reset();
		SetPhase(ELARSArmPhase::Stowed);
		break;

	case ELARSArmPhase::Approaching:
		SetPhase(ELARSArmPhase::Engaging);
		StartSegment(CaptureTarget(), EngageTime);
		break;

	case ELARSArmPhase::Engaging:
		if (S)
		{
			AttachShell(S);
			S->PushTerminalLog(TEXT("lars"), TEXT("capture pad seated - closing jaws"), EAOSHudLogSeverity::Info);
		}
		SetPhase(ELARSArmPhase::Clamping);
		StartSegment(FLARSArmTarget(BerthReach, ReleaseWorldZ, JawClampAngle), JawTime, true);
		break;

	case ELARSArmPhase::Clamping:
		SetPhase(ELARSArmPhase::Lifting);
		if (S)
		{
			S->PushTerminalLog(TEXT("lars"), TEXT("hull clamped - lifting to the cradle"), EAOSHudLogSeverity::Info);
		}
		StartSegment(HoldTarget(), MoveTime(CurrentTarget, HoldTarget(), LiftSpeed));
		break;

	case ELARSArmPhase::Lifting:
	{
		SetPhase(ELARSArmPhase::Holding);
		AShellDock* Dock = RecoveryDock.Get();
		ActiveShell.Reset();
		RecoveryDock.Reset();
		bCinematicActive = false;   // the dock blends LaunchCam -> on-foot Admin from here
		if (S)
		{
			OnShellRecovered.Broadcast(S);
			if (Dock)
			{
				Dock->HandleLARSRecoveryComplete(S);
			}
		}
		break;
	}
	default:
		break;
	}
}

void ALARSDockArm::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	LastDeltaSeconds = DeltaSeconds;
	if (bAwaitingCockpit)
	{
		// Same clock as the camera manager's blend (GetViewTarget() already reports the pending target mid-blend).
		// The camera lands during this frame's camera update when less than half a frame of blend is left, so the
		// HUD is switched on in that very frame (measured in PIE: same frame as the view reaching FPCamera).
		CockpitBlendElapsed += DeltaSeconds;
		if (CockpitBlendElapsed + 0.5f * DeltaSeconds >= CockpitBlendTime)
		{
			HandCockpitToPilot();
		}
	}

	if (Phase == ELARSArmPhase::Aligning)
	{
		AShellPawn* S = ActiveShell.Get();
		if (!S)
		{
			SetPhase(ELARSArmPhase::Stowed);
			return;
		}
		AlignElapsed += DeltaSeconds;
		const float A = SmootherStep(AlignElapsed / AlignDuration);
		const FVector Loc = FMath::Lerp(AlignFrom.GetLocation(), AlignTo.GetLocation(), A);
		const FQuat Rot = FQuat::Slerp(AlignFrom.GetRotation(), AlignTo.GetRotation(), A);
		S->SetActorLocationAndRotation(Loc, Rot, false, nullptr, ETeleportType::TeleportPhysics);
		if (AlignElapsed >= AlignDuration)
		{
			SetPhase(ELARSArmPhase::Approaching);
			StartSegment(PreCaptureTarget(), MoveTime(CurrentTarget, PreCaptureTarget(), MoveSpeed));
		}
	}
	else if (bSegmentActive)
	{
		Segment.Elapsed += DeltaSeconds;
		const float Alpha = FMath::Clamp(Segment.Elapsed / Segment.Duration, 0.f, 1.f);
		const float E = SmootherStep(Alpha);
		FLARSArmTarget T;
		T.Reach = FMath::Lerp(Segment.From.Reach, Segment.To.Reach, E);
		T.WorldZ = FMath::Lerp(Segment.From.WorldZ, Segment.To.WorldZ, E);
		T.JawOpen = FMath::Lerp(Segment.From.JawOpen, Segment.To.JawOpen, E);
		ApplyTarget(T);

		if (Phase == ELARSArmPhase::Releasing && !bReleasedThisCycle && Alpha >= ReleaseAtJawFraction)
		{
			ReleaseShell();
		}
		if (Alpha >= 1.f)
		{
			bSegmentActive = false;
			OnSegmentFinished();
		}
	}
	if (bCinematicActive)
	{
		UpdateCinematicCamera(DeltaSeconds, false);
	}
	TickSplash();
}

// ==================================================================================================
// Cinematic camera
// ==================================================================================================
FVector ALARSDockArm::GetCameraFocus() const
{
	const FLARSArmBoneNames N;
	const FVector Elbow = ArmMesh ? ArmMesh->GetSocketLocation(N.Elbow) : GetActorLocation();
	const AShellPawn* S = HeldShell.IsValid() ? HeldShell.Get() : ActiveShell.Get();
	const FVector Payload = S ? S->GetActorLocation() : (ArmMesh ? ArmMesh->GetSocketLocation(MountSocket) : GetActorLocation());
	return FMath::Lerp(Elbow, Payload, CameraFocusShellWeight);
}

void ALARSDockArm::UpdateCinematicCamera(float DeltaSeconds, bool bSnap)
{
	if (!LaunchCam)
	{
		return;
	}
	const FRotator Desired = (GetCameraFocus() - LaunchCam->GetComponentLocation()).Rotation();
	const FRotator Current = LaunchCam->GetComponentRotation();
	LaunchCam->SetWorldRotation(bSnap ? Desired : FMath::RInterpTo(Current, Desired, DeltaSeconds, CameraTrackSpeed));
}

bool ALARSDockArm::BeginCinematic(APlayerController* PC, float& OutBlendTime)
{
	OutBlendTime = 0.f;
	if (!bUseCinematicCamera || !PC || !LaunchCam)
	{
		return false;
	}
	GetWorldTimerManager().ClearTimer(CameraTimer);
	bAwaitingCockpit = false;
	CinematicPC = PC;
	bCinematicActive = true;
	UpdateCinematicCamera(0.f, true);   // stable blend target from the first frame
	OutBlendTime = CinematicBlendInTime;
	PC->SetViewTargetWithBlend(this, CinematicBlendInTime, VTBlend_EaseInOut, 2.f);
	return true;
}

void ALARSDockArm::BlendToCockpit(AShellPawn* S)
{
	APlayerController* PC = CinematicPC.Get();
	if (!bCinematicActive || !PC || !S || PC->GetPawn() != S)
	{
		HandCockpitToPilot();
		return;
	}
	PC->SetViewTargetWithBlend(S, CockpitBlendTime, VTBlend_EaseInOut, 2.f);
	// The camera manager subtracts this frame's delta from the blend as well: count it so the HUD comes up in the
	// very frame the view lands in the cockpit.
	CockpitBlendElapsed = LastDeltaSeconds;
	bAwaitingCockpit = true;
}

void ALARSDockArm::HandCockpitToPilot()
{
	bAwaitingCockpit = false;
	if (bControlGranted)
	{
		return;
	}
	bControlGranted = true;
	bCinematicActive = false;
	if (AShellPawn* S = ActiveShell.Get())
	{
		S->GrantPilotControl();   // 6DOF + cockpit HUD, same frame
		OnShellLaunched.Broadcast(S);
	}
}

void ALARSDockArm::StopCinematic()
{
	GetWorldTimerManager().ClearTimer(CameraTimer);
	bAwaitingCockpit = false;
	bCinematicActive = false;
	CinematicPC.Reset();
}

void ALARSDockArm::TickSplash()
{
	const AShellPawn* S = HeldShell.IsValid() ? HeldShell.Get() : ActiveShell.Get();
	if (!S || !SplashFX)
	{
		bHasLastShellBottom = false;
		return;
	}
	const float Bottom = float(S->GetActorLocation().Z) - 80.f;
	if (bHasLastShellBottom && (LastShellBottomZ - WaterSurfaceZ) * (Bottom - WaterSurfaceZ) < 0.f)
	{
		const FVector At(S->GetActorLocation().X, S->GetActorLocation().Y, WaterSurfaceZ);
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, SplashFX, At, FRotator::ZeroRotator);
	}
	LastShellBottomZ = Bottom;
	bHasLastShellBottom = true;
}

// ==================================================================================================
// Diagnostics
// ==================================================================================================
TArray<FLARSPistonState> ALARSDockArm::GetPistonStates() const
{
	TArray<FLARSPistonState> Out;
	if (!ArmMesh)
	{
		return Out;
	}
	const FLARSArmBoneNames N;
	const FName Pairs[2][2] = { { N.ShoulderCylBarrel, N.ShoulderCylRod }, { N.ElbowCylBarrel, N.ElbowCylRod } };
	const float Bodies[2][2] = { { float(PistonBodyLengths.X), float(PistonBodyLengths.Y) }, { float(PistonBodyLengths.Z), float(PistonBodyLengths.W) } };
	for (int32 i = 0; i < 2; ++i)
	{
		const FTransform B = ArmMesh->GetSocketTransform(Pairs[i][0], RTS_Component);
		const FTransform R = ArmMesh->GetSocketTransform(Pairs[i][1], RTS_Component);
		const FVector Dir = (R.GetLocation() - B.GetLocation());
		const FVector Axis = Dir.GetSafeNormal();
		const FVector BX = B.GetUnitAxis(EAxis::X);
		const FVector RX = R.GetUnitAxis(EAxis::X);
		FLARSPistonState St;
		St.Length = float(Dir.Size());
		St.Overlap = Bodies[i][0] + Bodies[i][1] - St.Length;
		St.BarrelAxisErrorDeg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(float(FVector::DotProduct(BX, Axis)), -1.f, 1.f)));
		St.RodAxisErrorDeg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(float(FVector::DotProduct(RX, -Axis)), -1.f, 1.f)));
		St.CoaxialErrorDeg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(float(FVector::DotProduct(BX, -RX)), -1.f, 1.f)));
		Out.Add(St);
	}
	return Out;
}

float ALARSDockArm::GetJawGap() const
{
	if (!ArmMesh)
	{
		return 0.f;
	}
	const FLARSArmBoneNames N;
	const FVector L = ArmMesh->GetSocketTransform(N.JawL, RTS_Component).TransformPosition(FVector(165.f, 0.f, 0.f));
	const FVector R = ArmMesh->GetSocketTransform(N.JawR, RTS_Component).TransformPosition(FVector(165.f, 0.f, 0.f));
	return float(FVector::Dist(L, R));
}
