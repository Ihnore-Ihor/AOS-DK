#include "AOS_ReaperAnimInstance.h"
#include "AOS_DK/Enemies/Reaper/AOS_AIEnemyCharacter.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperIK.h"
#include "Animation/AnimNodeBase.h"
#include "Animation/AnimationAsset.h"
#include "AnimationRuntime.h"
#include "BoneContainer.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/SkeletalMeshSocket.h"
#include "Components/SkeletalMeshComponent.h"
#include "HAL/IConsoleManager.h"

static const TCHAR* const GLegNames[6] = { TEXT("L1"), TEXT("L2"), TEXT("L3"), TEXT("R1"), TEXT("R2"), TEXT("R3") };

static TAutoConsoleVariable<int32> CVarShowGait(TEXT("aos.ai.ShowGait"), 0, TEXT("1 = draw Reaper foot targets, tripod groups and planted feet."));

// ==================================================================================================
// Instance / proxy plumbing
// ==================================================================================================
FAnimInstanceProxy* UAOS_ReaperAnimInstance::CreateAnimInstanceProxy()
{
	return new FAOS_ReaperAnimProxy(this);
}

void UAOS_ReaperAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
	delete static_cast<FAOS_ReaperAnimProxy*>(InProxy);
}

void FAOS_ReaperAnimProxy::PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds)
{
	FAnimInstanceProxy::PreUpdate(InAnimInstance, DeltaSeconds);
	if (const UAOS_ReaperAnimInstance* Anim = Cast<UAOS_ReaperAnimInstance>(InAnimInstance))
	{
		Input = Anim->PoseInput;
		Bones = Anim->BoneNames;
		Calib = Anim->Calibration;
		JawOpenSign = Anim->JawOpenSign;
	}
}

// ==================================================================================================
// Game thread: calibration from the ref pose
// ==================================================================================================
void UAOS_ReaperAnimInstance::NativeInitializeAnimation()
{
	Super::NativeInitializeAnimation();
	Reaper = Cast<AAOS_AIEnemyCharacter>(TryGetPawnOwner());
	bCalibrated = false;
	Calibrate();
}

void UAOS_ReaperAnimInstance::Calibrate()
{
	USkeletalMeshComponent* Comp = GetSkelMeshComponent();
	const USkeletalMesh* Asset = Comp ? Comp->GetSkeletalMeshAsset() : nullptr;
	if (!Asset)
	{
		return;
	}
	const FReferenceSkeleton& Ref = Asset->GetRefSkeleton();
	auto RefCS = [&Ref](const FName& Bone, FTransform& Out) -> bool
	{
		const int32 Index = Ref.FindBoneIndex(Bone);
		if (Index == INDEX_NONE)
		{
			return false;
		}
		Out = FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, Index);
		return true;
	};

	FVector Homes[6];
	for (int32 Leg = 0; Leg < 6; ++Leg)
	{
		FTransform Femur, Tibia, Foot;
		const FString Prefix = FString::Printf(TEXT("Leg_%s_"), GLegNames[Leg]);
		if (RefCS(FName(*(Prefix + TEXT("Femur"))), Femur) && RefCS(FName(*(Prefix + TEXT("Tibia"))), Tibia) && RefCS(FName(*(Prefix + TEXT("Foot"))), Foot))
		{
			Homes[Leg] = Foot.GetLocation();
			MeasuredFemur[Leg] = static_cast<float>((Tibia.GetLocation() - Femur.GetLocation()).Size());
			MeasuredTibia[Leg] = static_cast<float>((Foot.GetLocation() - Tibia.GetLocation()).Size());
			const float DevF = FMath::Abs(MeasuredFemur[Leg] - Calibration.NominalFemur) / Calibration.NominalFemur;
			const float DevT = FMath::Abs(MeasuredTibia[Leg] - Calibration.NominalTibia) / Calibration.NominalTibia;
			UE_LOG(LogAOSAI, Log, TEXT("Reaper IK %s: femur %.1f cm, tibia %.1f cm (nominal %.0f / %.0f%s)"), GLegNames[Leg],
				MeasuredFemur[Leg], MeasuredTibia[Leg], Calibration.NominalFemur, Calibration.NominalTibia,
				(DevF > 0.15f || DevT > 0.15f) ? TEXT(", >15% off nominal: measured value is used") : TEXT(""));
		}
		else
		{
			Homes[Leg] = FVector((Leg % 3 == 0 ? 125.f : Leg % 3 == 1 ? 0.f : -125.f), (Leg < 3 ? -122.f : 122.f), 12.f);
			MeasuredFemur[Leg] = Calibration.NominalFemur;
			MeasuredTibia[Leg] = Calibration.NominalTibia;
			UE_LOG(LogAOSAI, Warning, TEXT("Reaper IK %s: leg bones missing, using nominal lengths"), GLegNames[Leg]);
		}
	}
	Gait.SetHomes(Homes);

	FTransform T;
	if (RefCS(BoneNames.MastYaw, T)) { RefMastCS = T.GetLocation(); }
	if (RefCS(BoneNames.ArmYaw, T)) { RefArmYawCS = T.GetLocation(); }

	FTransform Wrist;
	if (RefCS(BoneNames.ArmWrist, Wrist))
	{
		RefWristCS = Wrist.GetLocation();
		FVector AxisLocal = FVector::ForwardVector;
		FVector MountLocal = FVector::ZeroVector;
		if (const USkeletalMeshSocket* Socket = Asset->FindSocket(BoneNames.WeaponSocket))
		{
			AxisLocal = Socket->RelativeRotation.Quaternion().RotateVector(FVector::ForwardVector);
			MountLocal = Socket->RelativeLocation;
		}
		const float PikeTip = Reaper ? Reaper->GetPikeTipDistance() : 262.f;
		Calibration.PikeAxisWristLocal = AxisLocal.GetSafeNormal();
		Calibration.PikeTipFromWristLocal = MountLocal + Calibration.PikeAxisWristLocal * PikeTip;
	}
	FTransform Body;
	if (RefCS(BoneNames.Body, Body))
	{
		BodyZ = 0.f;
	}
	bCalibrated = true;
}

// ==================================================================================================
// Game thread update
// ==================================================================================================
void UAOS_ReaperAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);
	if (!Reaper)
	{
		Reaper = Cast<AAOS_AIEnemyCharacter>(TryGetPawnOwner());
	}
	if (!Reaper || !GetSkelMeshComponent())
	{
		return;
	}
	if (!bCalibrated)
	{
		Calibrate();
	}
	const float Dt = FMath::Min(DeltaSeconds, 0.1f);
	UpdateGait(Dt);
	UpdateBody(Dt);
	UpdateMast(Dt);
	UpdateArm(Dt);

	const float JawTarget = Reaper->GetJawOpenTarget();
	JawOpen = FMath::FInterpTo(JawOpen, JawTarget, Dt, 14.f);
	PoseInput.JawOpenDeg = JawOpen;
}

void UAOS_ReaperAnimInstance::UpdateGait(float Dt)
{
	const USkeletalMeshComponent* Comp = GetSkelMeshComponent();
	FAOS_ReaperGait::FInput In;
	In.World = GetWorld();
	In.IgnoreActor = Reaper;
	In.MeshToWorld = Comp->GetComponentTransform();
	In.Velocity = Reaper->GetVelocity();
	In.Mode = Reaper->GetGaitMode();
	In.DeltaTime = Dt;
	In.bFrozen = Reaper->IsDead();
	In.bDebugDraw = bDebugGait || CVarShowGait.GetValueOnGameThread() > 0;
	Gait.Update(In);

	const FTransform WorldToMesh = Comp->GetComponentTransform().Inverse();
	for (int32 Leg = 0; Leg < 6; ++Leg)
	{
		PoseInput.FootTargets[Leg] = WorldToMesh.TransformPosition(Gait.FootBoneWorld[Leg]);
		if (Gait.bLanded[Leg])
		{
			Reaper->NotifyFootPlanted(Leg, Gait.GroundWorld[Leg]);
		}
	}
	StepClock += Dt * (1.f / FMath::Max(FAOS_ReaperGait::GetParams(Reaper->GetGaitMode()).StepDuration * 2.f, 0.1f));
}

void UAOS_ReaperAnimInstance::UpdateBody(float Dt)
{
	const USkeletalMeshComponent* Comp = GetSkelMeshComponent();
	const FTransform WorldToMesh = Comp->GetComponentTransform().Inverse();

	// Least-squares plane through the ground contacts (component space).
	FVector P[6];
	FVector Mean = FVector::ZeroVector;
	for (int32 i = 0; i < 6; ++i)
	{
		P[i] = WorldToMesh.TransformPosition(Gait.GroundWorld[i]);
		Mean += P[i];
	}
	Mean /= 6.0;
	double Sxx = 0, Syy = 0, Sxz = 0, Syz = 0;
	for (int32 i = 0; i < 6; ++i)
	{
		const FVector D = P[i] - Mean;
		Sxx += D.X * D.X;
		Syy += D.Y * D.Y;
		Sxz += D.X * D.Z;
		Syz += D.Y * D.Z;
	}
	const double SlopeX = Sxx > 1.0 ? Sxz / Sxx : 0.0;
	const double SlopeY = Syy > 1.0 ? Syz / Syy : 0.0;
	FVector Normal = FVector(-SlopeX, -SlopeY, 1.0).GetSafeNormal();
	const double MaxTilt = FMath::DegreesToRadians(MaxBodyTilt);
	if (FMath::Acos(Normal.Z) > MaxTilt)
	{
		const FVector2D Lateral = FVector2D(Normal.X, Normal.Y).GetSafeNormal() * FMath::Sin(MaxTilt);
		Normal = FVector(Lateral.X, Lateral.Y, FMath::Cos(MaxTilt));
	}
	const FQuat TargetRot = FQuat::FindBetweenNormals(FVector::UpVector, Normal);
	BodyRot = FQuat::Slerp(BodyRot, TargetRot, FMath::Min(1.f, Dt * 6.f)).GetNormalized();

	const float DeathAlpha = Reaper->GetDeathAlpha();
	const float Bob = BobAmplitude * FMath::Sin(2.f * PI * StepClock) * (1.f - DeathAlpha);
	const float TargetZ = static_cast<float>(Mean.Z) + BodyRaise * (1.f - DeathAlpha) + Bob - DeathBodyDrop * DeathAlpha;
	BodyZ = FMath::FInterpTo(BodyZ, TargetZ, Dt, 8.f);

	PoseInput.BodyOffset = FVector(0, 0, BodyZ);
	PoseInput.BodyRotation = BodyRot;
}

void UAOS_ReaperAnimInstance::UpdateMast(float Dt)
{
	const USkeletalMeshComponent* Comp = GetSkelMeshComponent();
	const FTransform MeshXf = Comp->GetComponentTransform();
	float TargetYaw = Reaper->GetMastSweepYaw();
	float TargetPitch = Reaper->GetMastSweepPitch();

	FVector LookWorld;
	if (!Reaper->IsDead() && Reaper->GetMastLookPoint(LookWorld))
	{
		const FVector MastWorld = MeshXf.TransformPosition(RefMastCS + FVector(0, 0, BodyZ));
		const FVector DirLocal = BodyRot.UnrotateVector(MeshXf.InverseTransformVectorNoScale(LookWorld - MastWorld)).GetSafeNormal();
		const FRotator R = DirLocal.Rotation();
		TargetYaw += R.Yaw;
		TargetPitch += R.Pitch;
	}
	if (Reaper->IsDead())
	{
		TargetPitch = -60.f * Reaper->GetDeathAlpha();
	}
	TargetYaw = FMath::Clamp(FRotator::NormalizeAxis(TargetYaw), -MastYawLimit, MastYawLimit);
	TargetPitch = FMath::Clamp(TargetPitch, MastMinPitch, MastMaxPitch);
	const float MaxStep = MastRate * Dt;
	MastYaw = AOSReaperIK::StepAngle(MastYaw, TargetYaw, MaxStep);
	MastPitch = AOSReaperIK::StepAngle(MastPitch, TargetPitch, MaxStep);
	PoseInput.MastYawDeg = MastYaw;
	PoseInput.MastPitchDeg = MastPitch;
}

void UAOS_ReaperAnimInstance::UpdateArm(float Dt)
{
	const USkeletalMeshComponent* Comp = GetSkelMeshComponent();
	const FTransform MeshXf = Comp->GetComponentTransform();

	FVector TipWorld, DirWorld;
	float Speed = 0.f;
	const float TargetAlpha = Reaper->GetArmCommand(TipWorld, DirWorld, Speed);

	ArmAlpha = FMath::FInterpTo(ArmAlpha, TargetAlpha, Dt, 6.f);
	if (TargetAlpha > 0.f)
	{
		const FVector TipCS = MeshXf.InverseTransformPosition(TipWorld);
		const FVector DirCS = MeshXf.InverseTransformVectorNoScale(DirWorld).GetSafeNormal();
		if (ArmAlpha < 0.05f && TargetAlpha > 0.f)
		{
			ArmTipCS = TipCS;
			ArmDirCS = DirCS;
		}
		else
		{
			ArmTipCS = FMath::VInterpConstantTo(ArmTipCS, TipCS, Dt, Speed);
			ArmDirCS = FMath::VInterpNormalRotationTo(ArmDirCS, DirCS, Dt, 360.f).GetSafeNormal();
		}
	}
	PoseInput.ArmTipTarget = ArmTipCS;
	PoseInput.ArmAimDir = ArmDirCS;
	PoseInput.ArmAlpha = ArmAlpha;
}

// ==================================================================================================
// Worker thread: pose evaluation
// ==================================================================================================
bool FAOS_ReaperAnimProxy::Evaluate(FPoseContext& Output)
{
	FCompactPose& CPose = Output.Pose;
	CPose.ResetToRefPose();
	const FBoneContainer& BC = CPose.GetBoneContainer();
	const int32 NumBones = CPose.GetNumBones();
	if (NumBones == 0)
	{
		return true;
	}

	auto Find = [&BC](const FName& Name) -> FCompactPoseBoneIndex
	{
		const int32 MeshIndex = BC.GetPoseBoneIndexForBoneName(Name);
		return MeshIndex == INDEX_NONE ? FCompactPoseBoneIndex(INDEX_NONE) : BC.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIndex));
	};

	// Bind pose in component space.
	TArray<FTransform> RefCS;
	RefCS.SetNum(NumBones);
	for (const FCompactPoseBoneIndex I : CPose.ForEachBoneIndex())
	{
		const FCompactPoseBoneIndex P = BC.GetParentBoneIndex(I);
		RefCS[I.GetInt()] = P.IsValid() ? CPose[I] * RefCS[P.GetInt()] : CPose[I];
	}

	const FCompactPoseBoneIndex BodyIdx = Find(Bones.Body);
	if (!BodyIdx.IsValid())
	{
		return true;
	}

	const FQuat Qb = Input.BodyRotation.GetNormalized();
	const FVector B0 = RefCS[BodyIdx.GetInt()].GetLocation();
	auto ToBodyFrame = [&](const FVector& P) { return Qb.UnrotateVector(P - B0 - Input.BodyOffset) + B0; };

	TArray<FQuat> Override;
	TArray<uint8> HasOverride;
	Override.SetNumUninitialized(NumBones);
	HasOverride.SetNumZeroed(NumBones);
	// BodyFrameRot: rotation expressed in the (un-tilted) body frame; the body transform is applied on top.
	auto SetBodyFrameRot = [&](const FCompactPoseBoneIndex I, const FQuat& BodyFrameRot)
	{
		Override[I.GetInt()] = (Qb * BodyFrameRot).GetNormalized();
		HasOverride[I.GetInt()] = 1;
	};

	// ---------------------------------------------------------------- legs
	static const TCHAR* const Legs[6] = { TEXT("L1"), TEXT("L2"), TEXT("L3"), TEXT("R1"), TEXT("R2"), TEXT("R3") };
	const double CoxaLimit = FMath::DegreesToRadians(CoxaYawLimitDeg);
	for (int32 Leg = 0; Leg < 6; ++Leg)
	{
		const FString Prefix = FString::Printf(TEXT("Leg_%s_"), Legs[Leg]);
		const FCompactPoseBoneIndex C = Find(FName(*(Prefix + TEXT("Coxa"))));
		const FCompactPoseBoneIndex F = Find(FName(*(Prefix + TEXT("Femur"))));
		const FCompactPoseBoneIndex T = Find(FName(*(Prefix + TEXT("Tibia"))));
		const FCompactPoseBoneIndex Ft = Find(FName(*(Prefix + TEXT("Foot"))));
		if (!C.IsValid() || !F.IsValid() || !T.IsValid() || !Ft.IsValid())
		{
			continue;
		}
		const FTransform& rC = RefCS[C.GetInt()];
		const FTransform& rF = RefCS[F.GetInt()];
		const FTransform& rT = RefCS[T.GetInt()];
		const FTransform& rFt = RefCS[Ft.GetInt()];
		const FVector Pc = rC.GetLocation(), Pf = rF.GetLocation(), Pt = rT.GetLocation(), Pfoot = rFt.GetLocation();
		const double LenA = FMath::Max((Pt - Pf).Size(), 1.0);   // measured femur
		const double LenB = FMath::Max((Pfoot - Pt).Size(), 1.0); // measured tibia

		const FVector Target = ToBodyFrame(Input.FootTargets[Leg]);

		// Coxa yaw about the body up axis: swings the leg plane onto the foot.
		const double RefAng = FMath::Atan2(Pf.Y - Pc.Y, Pf.X - Pc.X);
		const double TgtAng = FMath::Atan2(Target.Y - Pc.Y, Target.X - Pc.X);
		const double Yaw = FMath::Clamp(FMath::FindDeltaAngleRadians(RefAng, TgtAng), -CoxaLimit, CoxaLimit);
		const FQuat Rz(FVector::UpVector, Yaw);

		const FVector Hip = Pc + Rz.RotateVector(Pf - Pc);
		const FVector U = Rz.RotateVector(FVector(FMath::Cos(RefAng), FMath::Sin(RefAng), 0.0));
		const FVector D = Target - Hip;
		const double H = FVector::DotProduct(FVector(D.X, D.Y, 0.0), U);
		const FVector InPlane = Hip + U * H + FVector(0.0, 0.0, D.Z);

		const AOSReaperIK::FTwoBoneResult Sol = AOSReaperIK::SolveTwoBone(Hip, InPlane, LenA, LenB, FVector::UpVector);
		const FVector FemurDir = (Sol.Knee - Hip).GetSafeNormal();
		const FVector TibiaDir = (Sol.End - Sol.Knee).GetSafeNormal();

		const FVector DirRefF = (Pt - Pf).GetSafeNormal();
		const FVector DirRefT = (Pfoot - Pt).GetSafeNormal();

		const FQuat Qf = FQuat::FindBetweenNormals(Rz.RotateVector(DirRefF), FemurDir) * Rz;
		const FQuat Qt = FQuat::FindBetweenNormals(Qf.RotateVector(DirRefT), TibiaDir) * Qf;
		const FVector FootDown = Qb.UnrotateVector(FVector(0, 0, -1));
		const FQuat Qfoot = FQuat::FindBetweenNormals(Qt.RotateVector(DirRefT), FootDown) * Qt;

		SetBodyFrameRot(C, Rz * rC.GetRotation());
		SetBodyFrameRot(F, Qf * rF.GetRotation());
		SetBodyFrameRot(T, Qt * rT.GetRotation());
		SetBodyFrameRot(Ft, Qfoot * rFt.GetRotation());
	}

	// ---------------------------------------------------------------- mast (yaw about body up, pitch about the yawed side axis)
	const FCompactPoseBoneIndex MY = Find(Bones.MastYaw);
	const FCompactPoseBoneIndex MP = Find(Bones.MastPitch);
	if (MY.IsValid())
	{
		SetBodyFrameRot(MY, FRotator(0.f, Input.MastYawDeg, 0.f).Quaternion() * RefCS[MY.GetInt()].GetRotation());
	}
	if (MP.IsValid())
	{
		SetBodyFrameRot(MP, FRotator(Input.MastPitchDeg, Input.MastYawDeg, 0.f).Quaternion() * RefCS[MP.GetInt()].GetRotation());
	}

	// ---------------------------------------------------------------- jaws
	const FCompactPoseBoneIndex JL = Find(Bones.JawL);
	const FCompactPoseBoneIndex JR = Find(Bones.JawR);
	if (JL.IsValid())
	{
		SetBodyFrameRot(JL, FRotator(0.f, -JawOpenSign * Input.JawOpenDeg, 0.f).Quaternion() * RefCS[JL.GetInt()].GetRotation());
	}
	if (JR.IsValid())
	{
		SetBodyFrameRot(JR, FRotator(0.f, JawOpenSign * Input.JawOpenDeg, 0.f).Quaternion() * RefCS[JR.GetInt()].GetRotation());
	}

	// ---------------------------------------------------------------- dorsal arm: turret yaw + 2-bone IK + pike alignment
	const FCompactPoseBoneIndex AY = Find(Bones.ArmYaw);
	const FCompactPoseBoneIndex AS = Find(Bones.ArmShoulder);
	const FCompactPoseBoneIndex AE = Find(Bones.ArmElbow);
	const FCompactPoseBoneIndex AW = Find(Bones.ArmWrist);
	if (Input.ArmAlpha > 0.001f && AY.IsValid() && AS.IsValid() && AE.IsValid() && AW.IsValid())
	{
		const FTransform& rY = RefCS[AY.GetInt()];
		const FTransform& rS = RefCS[AS.GetInt()];
		const FTransform& rE = RefCS[AE.GetInt()];
		const FTransform& rW = RefCS[AW.GetInt()];
		const FVector Ps = rS.GetLocation(), Pe = rE.GetLocation(), Pw = rW.GetLocation();
		const double LenU = FMath::Max((Pe - Ps).Size(), 1.0);
		const double LenF = FMath::Max((Pw - Pe).Size(), 1.0);

		const FVector Tip = ToBodyFrame(Input.ArmTipTarget);
		const FVector Aim = Qb.UnrotateVector(Input.ArmAimDir).GetSafeNormal();

		// Absolute wrist orientation: minimal rotation from the bind pike axis onto the aim line.
		const FVector PikeAxisRef = rW.GetRotation().RotateVector(Calib.PikeAxisWristLocal);
		const FQuat WristAbs = FQuat::FindBetweenNormals(PikeAxisRef, Aim) * rW.GetRotation();
		const FVector TipOffset = WristAbs.RotateVector(Calib.PikeTipFromWristLocal);
		const FVector WristTarget = Tip - TipOffset;

		const FVector Pivot = rY.GetLocation();
		const double RefAng = FMath::Atan2(Pe.Y - Pivot.Y, Pe.X - Pivot.X);
		const double TgtAng = FMath::Atan2(WristTarget.Y - Pivot.Y, WristTarget.X - Pivot.X);
		const FQuat Rz(FVector::UpVector, FMath::FindDeltaAngleRadians(RefAng, TgtAng));

		const FVector Shoulder = Pivot + Rz.RotateVector(Ps - Pivot);
		const AOSReaperIK::FTwoBoneResult Sol = AOSReaperIK::SolveTwoBone(Shoulder, WristTarget, LenU, LenF, FVector::UpVector);
		const FVector UpperDir = (Sol.Knee - Shoulder).GetSafeNormal();
		const FVector ForeDir = (Sol.End - Sol.Knee).GetSafeNormal();

		const FQuat Q1 = FQuat::FindBetweenNormals(Rz.RotateVector((Pe - Ps).GetSafeNormal()), UpperDir) * Rz;
		const FQuat Q2 = FQuat::FindBetweenNormals(Q1.RotateVector((Pw - Pe).GetSafeNormal()), ForeDir) * Q1;

		const float A = FMath::Clamp(Input.ArmAlpha, 0.f, 1.f);
		auto Blend = [A](const FQuat& Rigid, const FQuat& IK) { return FQuat::Slerp(Rigid, IK, A).GetNormalized(); };
		SetBodyFrameRot(AY, Blend(rY.GetRotation(), Rz * rY.GetRotation()));
		SetBodyFrameRot(AS, Blend(rS.GetRotation(), Q1 * rS.GetRotation()));
		SetBodyFrameRot(AE, Blend(rE.GetRotation(), Q2 * rE.GetRotation()));
		SetBodyFrameRot(AW, Blend(rW.GetRotation(), WristAbs));
	}

	// ---------------------------------------------------------------- resolve: component-space rotations -> local transforms
	TArray<FQuat> FinalRot;
	FinalRot.SetNum(NumBones);
	for (const FCompactPoseBoneIndex I : CPose.ForEachBoneIndex())
	{
		const int32 i = I.GetInt();
		const FCompactPoseBoneIndex P = BC.GetParentBoneIndex(I);
		const FQuat ParentRot = P.IsValid() ? FinalRot[P.GetInt()] : FQuat::Identity;

		if (I == BodyIdx)
		{
			const FTransform FinalBody(Qb * RefCS[i].GetRotation(), B0 + Input.BodyOffset);
			CPose[I] = P.IsValid() ? FinalBody * RefCS[P.GetInt()].Inverse() : FinalBody;
			FinalRot[i] = FinalBody.GetRotation();
		}
		else if (HasOverride[i])
		{
			CPose[I].SetRotation((ParentRot.Inverse() * Override[i]).GetNormalized());
			FinalRot[i] = Override[i];
		}
		else
		{
			FinalRot[i] = (ParentRot * CPose[I].GetRotation()).GetNormalized();
		}
	}
	return true;
}
