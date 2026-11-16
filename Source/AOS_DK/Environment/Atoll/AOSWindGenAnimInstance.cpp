#include "AOS_DK/Environment/Atoll/AOSWindGenAnimInstance.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimNodeBase.h"
#include "Animation/AnimationPoseData.h"
#include "BoneContainer.h"

FAnimInstanceProxy* UAOSWindGenAnimInstance::CreateAnimInstanceProxy()
{
	return new FAOSWindGenAnimProxy(this);
}

void UAOSWindGenAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
	delete static_cast<FAOSWindGenAnimProxy*>(InProxy);
}

void UAOSWindGenAnimInstance::NativeInitializeAnimation()
{
	Super::NativeInitializeAnimation();
	if (!SpinAnim) { SpinAnim = LoadObject<UAnimSequence>(nullptr, DefaultSpinPath); }
	if (!HuntAnim) { HuntAnim = LoadObject<UAnimSequence>(nullptr, DefaultHuntPath); }
	if (!FurlAnim) { FurlAnim = LoadObject<UAnimSequence>(nullptr, DefaultFurlPath); }
	SpinRate = TargetSpinRate;
	FurlAlpha = TargetFurlAlpha;
}

void UAOSWindGenAnimInstance::SetDrive(float InTargetSpinRate, float InTargetFurlAlpha)
{
	TargetSpinRate = FMath::Max(0.f, InTargetSpinRate);
	TargetFurlAlpha = FMath::Clamp(InTargetFurlAlpha, 0.f, 1.f);
}

void UAOSWindGenAnimInstance::SetInitialPhases(float InSpinTimeSec, float InHuntTimeSec)
{
	SpinTime = FMath::Max(0.f, InSpinTimeSec);
	HuntTime = FMath::Max(0.f, InHuntTimeSec);
}

void UAOSWindGenAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);

	SpinRate = FMath::FInterpTo(SpinRate, TargetSpinRate, DeltaSeconds, SpinRateInterpSpeed);
	FurlAlpha += (TargetFurlAlpha - FurlAlpha) * (1.f - FMath::Exp(-DeltaSeconds / FMath::Max(FurlTimeConstant, 0.01f)));
	FurlAlpha = FMath::Clamp(FurlAlpha, 0.f, 1.f);

	const float SpinLen = SpinAnim ? FMath::Max(SpinAnim->GetPlayLength(), 0.01f) : 3.f;
	const float HuntLen = HuntAnim ? FMath::Max(HuntAnim->GetPlayLength(), 0.01f) : 8.f;

	// the hub keeps turning while furling, at SpinRate * (1 - FurlAlpha)
	const float Advance = DeltaSeconds * SpinRate * (1.f - FurlAlpha);
	SpinTime += Advance;
	while (SpinTime >= SpinLen) { SpinTime -= SpinLen; SpinLoops += 1.f; }
	HuntTime = FMath::Fmod(HuntTime + DeltaSeconds * HuntRate, HuntLen);
}

void FAOSWindGenAnimProxy::PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds)
{
	FAnimInstanceProxy::PreUpdate(InAnimInstance, DeltaSeconds);
	if (const UAOSWindGenAnimInstance* Wind = Cast<UAOSWindGenAnimInstance>(InAnimInstance))
	{
		SpinAnim = Wind->SpinAnim;
		HuntAnim = Wind->HuntAnim;
		FurlAnim = Wind->FurlAnim;
		SpinTime = Wind->SpinTime;
		HuntTime = Wind->HuntTime;
		FurlAlpha = Wind->FurlAlpha;
		Bones = Wind->BoneNames;
	}
}

bool FAOSWindGenAnimProxy::Evaluate(FPoseContext& Output)
{
	FCompactPose& Pose = Output.Pose;
	Pose.ResetToRefPose();
	const FBoneContainer& BC = Pose.GetBoneContainer();
	if (Pose.GetNumBones() == 0)
	{
		return true;
	}

	auto Find = [&BC](const FName& Name) -> FCompactPoseBoneIndex
	{
		const int32 MeshIndex = BC.GetPoseBoneIndexForBoneName(Name);
		return MeshIndex == INDEX_NONE ? FCompactPoseBoneIndex(INDEX_NONE) : BC.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIndex));
	};

	// Sample one take at an explicit time into a scratch pose (full bone set; 9 bones, cheap).
	auto Sample = [](const UAnimSequence* Seq, float Time, FPoseContext& Scratch) -> bool
	{
		if (!Seq)
		{
			return false;
		}
		Scratch.ResetToRefPose();
		FAnimationPoseData Data(Scratch.Pose, Scratch.Curve, Scratch.CustomAttributes);
		const float Len = Seq->GetPlayLength();
		const FAnimExtractContext Context(static_cast<double>(FMath::Clamp(Time, 0.f, Len)), false);
		Seq->GetAnimationPose(Data, Context);
		return true;
	};

	auto Blend = [](const FTransform& A, const FTransform& B, float W) -> FTransform
	{
		const double Alpha = FMath::Clamp(W, 0.f, 1.f);
		return FTransform(FQuat::Slerp(A.GetRotation(), B.GetRotation(), Alpha).GetNormalized(),
			FMath::Lerp(A.GetTranslation(), B.GetTranslation(), Alpha), FMath::Lerp(A.GetScale3D(), B.GetScale3D(), Alpha));
	};

	const float SpinLen = SpinAnim ? FMath::Max(SpinAnim->GetPlayLength(), 0.01f) : 1.f;
	const float HuntLen = HuntAnim ? FMath::Max(HuntAnim->GetPlayLength(), 0.01f) : 1.f;
	const float FurlLen = FurlAnim ? FurlAnim->GetPlayLength() : 0.f;

	FPoseContext Spin(Output.AnimInstanceProxy);
	FPoseContext Hunt(Output.AnimInstanceProxy);
	FPoseContext Furl(Output.AnimInstanceProxy);
	const bool bSpin = Sample(SpinAnim, FMath::Fmod(SpinTime, SpinLen), Spin);
	const bool bHunt = Sample(HuntAnim, FMath::Fmod(HuntTime, HuntLen), Hunt);
	const bool bFurl = Sample(FurlAnim, FurlAlpha * FurlLen, Furl);

	// WG_Rotor_Hub: Spin take only (layered blend branch filter, depth 0, local space)
	const FCompactPoseBoneIndex Hub = Find(Bones.RotorHub);
	if (Hub.IsValid() && bSpin)
	{
		Pose[Hub] = Spin.Pose[Hub];
	}

	// Nacelle yaw + tail vane: Hunt (or bind) -> Furl by FurlAlpha
	for (const FName& Name : { Bones.NacelleYaw, Bones.TailVane })
	{
		const FCompactPoseBoneIndex I = Find(Name);
		if (!I.IsValid())
		{
			continue;
		}
		const FTransform Base = bHunt ? Hunt.Pose[I] : Pose[I];
		Pose[I] = bFurl ? Blend(Base, Furl.Pose[I], FurlAlpha) : Base;
	}

	// Blades: Spin take (bind pitch 8 deg) -> Furl (pitch 8 -> 88 deg) by FurlAlpha
	for (const FName& Name : { Bones.Blade0, Bones.Blade1, Bones.Blade2 })
	{
		const FCompactPoseBoneIndex I = Find(Name);
		if (!I.IsValid())
		{
			continue;
		}
		const FTransform Base = bSpin ? Spin.Pose[I] : Pose[I];
		Pose[I] = bFurl ? Blend(Base, Furl.Pose[I], FurlAlpha) : Base;
	}
	return true;
}
