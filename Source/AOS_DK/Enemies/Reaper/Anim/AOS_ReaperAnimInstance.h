#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperTypes.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperGait.h"
#include "AOS_ReaperAnimInstance.generated.h"

class AAOS_AIEnemyCharacter;

/** Bone / socket names of SKEL_OOMReaper (defaults match the authored rig, Tools/SK_OOMReaper_rig.json). */
USTRUCT(BlueprintType)
struct AOS_DK_API FAOS_ReaperBoneNames
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName Body = TEXT("Body_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName MastYaw = TEXT("Mast_Yaw_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName MastPitch = TEXT("Mast_Pitch_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName MastHead = TEXT("Mast_Head_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName ArmYaw = TEXT("Arm_Yaw_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName ArmShoulder = TEXT("Arm_Pitch1_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName ArmElbow = TEXT("Arm_Pitch2_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName ArmWrist = TEXT("Arm_Wrist_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName JawL = TEXT("Jaw_L_Bone");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName JawR = TEXT("Jaw_R_Bone");
	/** Weapon socket on the wrist bone (gives the pike axis and the mount point). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Reaper") FName WeaponSocket = TEXT("SOCKET_Weapon_Dorsal");
};

/** Constants measured once from the ref pose (game thread) and read by the proxy. */
struct FAOS_ReaperCalibration
{
	/** Pike tip offset from the wrist bone origin, in wrist-local space (at the ref pose). */
	FVector PikeTipFromWristLocal = FVector::ZeroVector;
	/** Pike axis (unit) in wrist-local space. */
	FVector PikeAxisWristLocal = FVector::ForwardVector;
	/** Nominal lengths used when a bone is missing. */
	float NominalFemur = 75.f;
	float NominalTibia = 140.f;
};

/**
 * Native evaluation of the Reaper pose (no authored clips, no AnimGraph logic):
 * ref pose -> body transform -> analytic 2-bone IK on 6 legs -> mast aim -> dorsal arm IK -> jaws.
 * The IK lengths are measured from the ref pose of every leg (the authored skeleton is the truth; the nominal 75 / 140 cm
 * are only the fallback), and every bone is rotated as the minimal component-space rotation that carries its bind-pose
 * segment onto the solved segment, so the proxy is independent of the bone axis convention (same idea as the LARS arm).
 */
USTRUCT()
struct AOS_DK_API FAOS_ReaperAnimProxy : public FAnimInstanceProxy
{
	GENERATED_BODY()

	FAOS_ReaperAnimProxy() = default;
	explicit FAOS_ReaperAnimProxy(UAnimInstance* InAnimInstance) : FAnimInstanceProxy(InAnimInstance) {}

	virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override;
	virtual bool Evaluate(FPoseContext& Output) override;

private:
	FAOS_ReaperPoseInput Input;
	FAOS_ReaperBoneNames Bones;
	FAOS_ReaperCalibration Calib;
	float JawOpenSign = 1.f;
	float CoxaYawLimitDeg = 45.f;
};

UCLASS(Blueprintable, BlueprintType, meta = (DisplayName = "AOS Reaper Anim Instance"))
class AOS_DK_API UAOS_ReaperAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	virtual void NativeInitializeAnimation() override;
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Reaper")
	FAOS_ReaperBoneNames BoneNames;

	/** Body lift above the authored stance, cm. The authored bind pose is deeply folded; this gives the legs room to lift. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Gait", meta = (ClampMin = "0", Units = "cm"))
	float BodyRaise = 25.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Gait", meta = (ClampMin = "0", Units = "cm"))
	float BobAmplitude = 3.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Gait", meta = (ClampMin = "0", ClampMax = "45", Units = "deg"))
	float MaxBodyTilt = 15.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Gait", meta = (ClampMin = "0", Units = "cm"))
	float DeathBodyDrop = 45.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Mast", meta = (ClampMin = "1", Units = "deg/s"))
	float MastRate = 120.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Mast", meta = (Units = "deg"))
	float MastMinPitch = -30.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Mast", meta = (Units = "deg"))
	float MastMaxPitch = 70.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Mast", meta = (Units = "deg"))
	float MastYawLimit = 150.f;

	/** +1: Jaw_L opens with negative yaw (UE flips the Max Y axis). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper")
	float JawOpenSign = 1.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Debug")
	bool bDebugGait = false;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper")
	float GetMeasuredFemurLength(int32 Leg) const { return Leg >= 0 && Leg < 6 ? MeasuredFemur[Leg] : 0.f; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper")
	float GetMeasuredTibiaLength(int32 Leg) const { return Leg >= 0 && Leg < 6 ? MeasuredTibia[Leg] : 0.f; }

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;

private:
	friend struct FAOS_ReaperAnimProxy;

	void Calibrate();
	void UpdateGait(float Dt);
	void UpdateBody(float Dt);
	void UpdateMast(float Dt);
	void UpdateArm(float Dt);

	FAOS_ReaperPoseInput PoseInput;
	FAOS_ReaperCalibration Calibration;
	FAOS_ReaperGait Gait;

	UPROPERTY(Transient)
	TObjectPtr<AAOS_AIEnemyCharacter> Reaper;

	bool bCalibrated = false;
	float MeasuredFemur[6] = { 0, 0, 0, 0, 0, 0 };
	float MeasuredTibia[6] = { 0, 0, 0, 0, 0, 0 };
	float BodyZ = 0.f;
	FQuat BodyRot = FQuat::Identity;
	float MastYaw = 0.f;
	float MastPitch = 0.f;
	float StepClock = 0.f;
	FVector ArmTipCS = FVector::ZeroVector;
	FVector ArmDirCS = FVector::ForwardVector;
	float ArmAlpha = 0.f;
	float JawOpen = 0.f;
	FVector RefMastCS = FVector::ZeroVector;
	FVector RefArmYawCS = FVector::ZeroVector;
	FVector RefWristCS = FVector::ZeroVector;
};
