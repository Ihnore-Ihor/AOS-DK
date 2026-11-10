#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "LARSArmAnimInstance.generated.h"

/**
 * FK channels of SK_LARS_RoboticArm, in degrees, as deltas from the bind pose.
 * The main joints are world-aligned in the bind pose, so every channel maps 1:1 to a local Rotator channel.
 */
USTRUCT(BlueprintType)
struct AOS_DK_API FLARSArmJointPose
{
	GENERATED_BODY()

	/** Base_Yaw_Bone, local Z. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "LARS", meta = (Units = "deg"))
	float BaseYaw = 0.f;

	/** Shoulder_Pitch_Bone, local Y. + raises the boom. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "LARS", meta = (Units = "deg"))
	float ShoulderPitch = 0.f;

	/** Elbow_Pitch_Bone, local Y. - folds the forearm down. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "LARS", meta = (Units = "deg"))
	float ElbowPitch = 0.f;

	/** Wrist_Pitch_Bone, local Y. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "LARS", meta = (Units = "deg"))
	float WristPitch = 0.f;

	/** Wrist_Roll_Bone, local X (the end-effector axis). With the wrist pointing down it turns the payload about the vertical. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "LARS", meta = (Units = "deg"))
	float WristRoll = 0.f;

	/** Jaw_L / Jaw_R, local Z, opposite signs. 0 = bind (closed, 208 cm clear between the pads), + opens, - squeezes. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "LARS", meta = (Units = "deg"))
	float JawOpen = 0.f;
};

/** Bone names of the LARS rig (defaults match SK_LARS_RoboticArm_Skeleton). */
USTRUCT(BlueprintType)
struct AOS_DK_API FLARSArmBoneNames
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName BaseYaw = TEXT("Base_Yaw_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName Shoulder = TEXT("Shoulder_Pitch_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName Elbow = TEXT("Elbow_Pitch_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName WristPitch = TEXT("Wrist_Pitch_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName WristRoll = TEXT("Wrist_Roll_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName JawL = TEXT("Jaw_L_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName JawR = TEXT("Jaw_R_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName ShoulderCylBarrel = TEXT("Shoulder_Cyl_Barrel_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName ShoulderCylRod = TEXT("Shoulder_Cyl_Rod_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName ElbowCylBarrel = TEXT("Elbow_Cyl_Barrel_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "LARS") FName ElbowCylRod = TEXT("Elbow_Cyl_Rod_Bone");
};

/**
 * Native evaluation of the LARS arm: ref pose -> FK on the 6 driven joints -> coaxial Aim of the 4 piston bones
 * (barrel aims at its rod eye, rod aims at its barrel trunnion). The aim is solved in component space as the minimal
 * rotation that carries the bind-pose cylinder axis onto the current trunnion-to-eye line, so it keeps whatever
 * axis convention the piston bones were bound with.
 */
USTRUCT()
struct AOS_DK_API FLARSArmAnimInstanceProxy : public FAnimInstanceProxy
{
	GENERATED_BODY()

	FLARSArmAnimInstanceProxy() = default;
	explicit FLARSArmAnimInstanceProxy(UAnimInstance* InAnimInstance) : FAnimInstanceProxy(InAnimInstance) {}

	virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override;
	virtual bool Evaluate(FPoseContext& Output) override;

private:
	FLARSArmJointPose Pose;
	FLARSArmBoneNames Bones;
	float JawOpenSign = 1.f;
	bool bDrivePistons = true;
};

/**
 * ABP_LARS_RoboticArm parent class. The pose is fully procedural (no anim graph needed): set JointPose from the
 * game thread (ALARSDockArm does it every tick) and the proxy evaluates FK + piston Aim on the worker thread.
 */
UCLASS(Blueprintable, BlueprintType, meta = (DisplayName = "LARS Arm Anim Instance"))
class AOS_DK_API ULARSArmAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|LARS")
	void SetJointPose(const FLARSArmJointPose& InPose) { JointPose = InPose; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|LARS")
	FLARSArmJointPose GetJointPose() const { return JointPose; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|LARS")
	FLARSArmJointPose JointPose;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|LARS")
	FLARSArmBoneNames BoneNames;

	/** +1: Jaw_L opens with negative yaw, Jaw_R with positive yaw (UE flips the Max Y axis). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|LARS")
	float JawOpenSign = 1.f;

	/** Keep the 4 hydraulic cylinders coaxial (Aim pairs). Off = rigid FK only (debug). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|LARS")
	bool bDrivePistons = true;

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;
};
