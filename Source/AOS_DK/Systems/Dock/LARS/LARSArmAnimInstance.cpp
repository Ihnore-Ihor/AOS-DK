#include "LARSArmAnimInstance.h"
#include "Animation/AnimNodeBase.h"
#include "BoneContainer.h"

FAnimInstanceProxy* ULARSArmAnimInstance::CreateAnimInstanceProxy()
{
	return new FLARSArmAnimInstanceProxy(this);
}

void ULARSArmAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
	delete static_cast<FLARSArmAnimInstanceProxy*>(InProxy);
}

void FLARSArmAnimInstanceProxy::PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds)
{
	FAnimInstanceProxy::PreUpdate(InAnimInstance, DeltaSeconds);
	if (const ULARSArmAnimInstance* Arm = Cast<ULARSArmAnimInstance>(InAnimInstance))
	{
		Pose = Arm->JointPose;
		Bones = Arm->BoneNames;
		JawOpenSign = Arm->JawOpenSign;
		bDrivePistons = Arm->bDrivePistons;
	}
}

bool FLARSArmAnimInstanceProxy::Evaluate(FPoseContext& Output)
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
	auto BuildComponentSpace = [&](TArray<FTransform>& OutCS)
	{
		OutCS.SetNum(NumBones);
		for (const FCompactPoseBoneIndex I : CPose.ForEachBoneIndex())
		{
			const FCompactPoseBoneIndex P = BC.GetParentBoneIndex(I);
			OutCS[I.GetInt()] = P.IsValid() ? CPose[I] * OutCS[P.GetInt()] : CPose[I];
		}
	};

	// Bind (ref) pose in component space: source of the cylinder axes.
	TArray<FTransform> RefCS;
	BuildComponentSpace(RefCS);

	// 1) FK: rotate the driven joints about their own (world-aligned in bind) axes.
	auto RotateLocal = [&](const FName& Bone, const FRotator& Delta)
	{
		const FCompactPoseBoneIndex I = Find(Bone);
		if (I.IsValid())
		{
			FTransform& T = CPose[I];
			T.SetRotation((T.GetRotation() * Delta.Quaternion()).GetNormalized());
		}
	};
	RotateLocal(Bones.BaseYaw, FRotator(0.f, Pose.BaseYaw, 0.f));
	RotateLocal(Bones.Shoulder, FRotator(Pose.ShoulderPitch, 0.f, 0.f));
	RotateLocal(Bones.Elbow, FRotator(Pose.ElbowPitch, 0.f, 0.f));
	RotateLocal(Bones.WristPitch, FRotator(Pose.WristPitch, 0.f, 0.f));
	RotateLocal(Bones.WristRoll, FRotator(0.f, 0.f, Pose.WristRoll));
	RotateLocal(Bones.JawL, FRotator(0.f, -JawOpenSign * Pose.JawOpen, 0.f));
	RotateLocal(Bones.JawR, FRotator(0.f, JawOpenSign * Pose.JawOpen, 0.f));

	if (!bDrivePistons)
	{
		return true;
	}

	// 2) Piston Aim pairs, after the FK solve.
	TArray<FTransform> CS;
	BuildComponentSpace(CS);

	auto AimBone = [&](const FCompactPoseBoneIndex I, const FVector& BindDir, const FVector& TargetDir)
	{
		const FQuat FKRot = CS[I.GetInt()].GetRotation();
		// The bind-pose cylinder axis, carried along by the bone's FK frame (its parent joint).
		const FVector Carried = FKRot.RotateVector(RefCS[I.GetInt()].GetRotation().UnrotateVector(BindDir));
		const FQuat NewCSRot = (FQuat::FindBetweenNormals(Carried, TargetDir) * FKRot).GetNormalized();
		const FCompactPoseBoneIndex P = BC.GetParentBoneIndex(I);
		const FQuat ParentRot = P.IsValid() ? CS[P.GetInt()].GetRotation() : FQuat::Identity;
		CPose[I].SetRotation((ParentRot.Inverse() * NewCSRot).GetNormalized());
		CS[I.GetInt()].SetRotation(NewCSRot);
	};
	auto AimPair = [&](const FName& BarrelName, const FName& RodName)
	{
		const FCompactPoseBoneIndex B = Find(BarrelName);
		const FCompactPoseBoneIndex R = Find(RodName);
		if (!B.IsValid() || !R.IsValid())
		{
			return;
		}
		const FVector BindDir = (RefCS[R.GetInt()].GetLocation() - RefCS[B.GetInt()].GetLocation()).GetSafeNormal();
		const FVector CurDir = (CS[R.GetInt()].GetLocation() - CS[B.GetInt()].GetLocation()).GetSafeNormal();
		if (BindDir.IsNearlyZero() || CurDir.IsNearlyZero())
		{
			return;
		}
		AimBone(B, BindDir, CurDir);    // barrel -> rod eye
		AimBone(R, -BindDir, -CurDir);  // rod -> barrel trunnion
	};
	AimPair(Bones.ShoulderCylBarrel, Bones.ShoulderCylRod);
	AimPair(Bones.ElbowCylBarrel, Bones.ElbowCylRod);
	return true;
}
