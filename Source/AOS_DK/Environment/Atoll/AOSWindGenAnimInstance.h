#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "AOSWindGenAnimInstance.generated.h"

class UAnimSequence;

/** Bone names of SK_Agro_WindGen_Skeleton (defaults match Tools/max_build_SK_WindGen.py). */
USTRUCT(BlueprintType)
struct AOS_DK_API FAOSWindGenBoneNames
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "WindGen") FName NacelleYaw = TEXT("WG_Nacelle_Yaw");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "WindGen") FName TailVane = TEXT("WG_TailVane");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "WindGen") FName RotorHub = TEXT("WG_Rotor_Hub");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "WindGen") FName Blade0 = TEXT("WG_Blade_0");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "WindGen") FName Blade1 = TEXT("WG_Blade_1");
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "WindGen") FName Blade2 = TEXT("WG_Blade_2");
};

/**
 * Native evaluation of the wind generator: samples the three imported UAnimSequence assets itself and blends them per bone,
 * so ABP_WindGen needs no AnimGraph nodes.
 *   Hunt  (loop)     -> base pose of WG_Nacelle_Yaw / WG_TailVane (yaw sweep, vane lag)
 *   Spin  (loop)     -> WG_Rotor_Hub at SpinTime (time advances by SpinRate * (1 - FurlAlpha))
 *   Furl  (one-shot) -> evaluated at FurlAlpha * length, blended by FurlAlpha onto WG_Nacelle_Yaw, WG_TailVane and the 3 blades
 * Equivalent to Hunt -> Layered Blend per Bone (Spin, hub) -> Blend (Sequence Evaluator Furl, ExplicitTime = FurlAlpha * 2.0).
 */
USTRUCT()
struct AOS_DK_API FAOSWindGenAnimProxy : public FAnimInstanceProxy
{
	GENERATED_BODY()

	FAOSWindGenAnimProxy() = default;
	explicit FAOSWindGenAnimProxy(UAnimInstance* InAnimInstance) : FAnimInstanceProxy(InAnimInstance) {}

	virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override;
	virtual bool Evaluate(FPoseContext& Output) override;

private:
	const UAnimSequence* SpinAnim = nullptr;
	const UAnimSequence* HuntAnim = nullptr;
	const UAnimSequence* FurlAnim = nullptr;
	float SpinTime = 0.f;
	float HuntTime = 0.f;
	float FurlAlpha = 0.f;
	FAOSWindGenBoneNames Bones;
};

/** ABP_WindGen parent class. The owning AAOSWindGenerator pushes SetDrive() at 10 Hz; phases and smoothing run every frame here. */
UCLASS(Blueprintable, BlueprintType, meta = (DisplayName = "AOS WindGen Anim Instance"))
class AOS_DK_API UAOSWindGenAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	virtual void NativeInitializeAnimation() override;
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;

	/** Targets from the generator: SpinRate is the Spin play rate (1 = 120 deg/s), FurlAlpha 0..1 (blades feathered, nacelle furled). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|WindGen")
	void SetDrive(float InTargetSpinRate, float InTargetFurlAlpha);

	/** Desynchronises instances: initial positions inside the Spin (3 s) and Hunt (8 s) loops. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|WindGen")
	void SetInitialPhases(float InSpinTimeSec, float InHuntTimeSec);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetSpinRate() const { return SpinRate; }
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetFurlAlpha() const { return FurlAlpha; }
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetSpinTime() const { return SpinTime; }
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetHuntTime() const { return HuntTime; }
	/** Total hub revolutions since BeginPlay (SpinTime wraps every loop); a test hook for "the rotor really turns". */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetSpinLoops() const { return SpinLoops; }

	// ---- imported takes (set on ABP_WindGen's class defaults; NativeInitializeAnimation falls back to the default asset paths) ----
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Anim") TObjectPtr<UAnimSequence> SpinAnim;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Anim") TObjectPtr<UAnimSequence> HuntAnim;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Anim") TObjectPtr<UAnimSequence> FurlAnim;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|Anim") FAOSWindGenBoneNames BoneNames;

	/** Hunt loop speed (1 = authored 8 s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Anim", meta = (ClampMin = "0")) float HuntRate = 1.f;

	/** Interp speed of SpinRate towards its target (1/s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Anim", meta = (ClampMin = "0.01")) float SpinRateInterpSpeed = 1.5f;

	/** Time constant of FurlAlpha towards its target, s (spec: 1.5). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Anim", meta = (ClampMin = "0.01", Units = "s")) float FurlTimeConstant = 1.5f;

	// ---- live state (read by the proxy) ----
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|State") float SpinRate = 0.35f;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|State") float FurlAlpha = 0.f;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|State") float TargetSpinRate = 0.35f;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|State") float TargetFurlAlpha = 0.f;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|State") float SpinTime = 0.f;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|State") float HuntTime = 0.f;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|State") float SpinLoops = 0.f;

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;

private:
	static constexpr const TCHAR* DefaultSpinPath = TEXT("/Game/AOS_DK_Game/Environment/Atoll/WindGen/A_WindGen_Spin.A_WindGen_Spin");
	static constexpr const TCHAR* DefaultHuntPath = TEXT("/Game/AOS_DK_Game/Environment/Atoll/WindGen/A_WindGen_Hunt.A_WindGen_Hunt");
	static constexpr const TCHAR* DefaultFurlPath = TEXT("/Game/AOS_DK_Game/Environment/Atoll/WindGen/A_WindGen_Furl.A_WindGen_Furl");
};
