#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSWindGenerator.generated.h"

class UBoxComponent;
class UCapsuleComponent;
class UMaterialInstanceDynamic;
class UPointLightComponent;
class USceneComponent;
class USkeletalMeshComponent;
class UAOSWindGenAnimInstance;

/**
 * Animated Agro-Sector wind generator (Lab 6 / Task 3, DCC object SK_Agro_WindGen, Bible M-15).
 *
 * Reads Wind01 and NightFactor / StormAlpha from UAOSEnvironmentStateSubsystem at TickRate (10 Hz) and drives the anim instance:
 *   SpinRate  = (SpinBase + SpinPerWind * Wind01) * RateJitter   (gentle idle spin at calm -> fast spin as the wind rises)
 *   FurlAlpha -> smoothstep(FurlStartWind, FurlFullWind, Wind01)  (damped inside the anim instance, tau 1.5 s; the blades feather in a storm)
 * and switches the obstruction light on WG_Light_Obstr (SOCKET_Light_Obstr) when max(NightFactor, StormAlpha) rises above OnThreshold.
 * Each instance gets its own deterministic start phase and +-10 % rate jitter, so a field of turbines never turns in lock-step.
 */
UCLASS(ClassGroup = "AOS_DK", Blueprintable, meta = (DisplayName = "AOS Wind Generator"))
class AOS_DK_API AAOSWindGenerator : public AActor
{
	GENERATED_BODY()

public:
	AAOSWindGenerator();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") bool IsObstructionLightOn() const { return bLightOn; }
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetLightOnAlpha() const { return LightOnAlpha; }
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetLightIntensity() const;
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetTargetSpinRate() const { return TargetSpinRate; }
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetTargetFurlAlpha() const { return TargetFurlAlpha; }
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetRateJitter() const { return RateJitter; }
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") float GetWind01() const { return LastWind01; }

	/** The anim instance driving the turbine (null before the mesh is initialised). */
	UFUNCTION(BlueprintPure, Category = "AOS_DK|WindGen") UAOSWindGenAnimInstance* GetWindAnim() const;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|Components") TObjectPtr<USceneComponent> Root;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|Components") TObjectPtr<USkeletalMeshComponent> TurbineMesh;
	/** Tower collision: capsule R 22 H 450 (spec), centred at Z 450. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|Components") TObjectPtr<UCapsuleComponent> TowerCapsule;
	/** Base plate 200 x 200 x 30, as the UCX of SM_Agro_WindGen (the static mesh it replaces). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|Components") TObjectPtr<UBoxComponent> BaseCollision;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AOS_DK|WindGen|Components") TObjectPtr<UPointLightComponent> ObstructionLight;

	// ---- drive ----
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Drive") float SpinBase = 0.35f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Drive") float SpinPerWind = 2.4f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Drive", meta = (ClampMin = "0", ClampMax = "0.5")) float RateJitterFraction = 0.10f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Drive") float FurlStartWind = 0.80f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Drive") float FurlFullWind = 0.95f;
	/** Subsystem poll period, s (spec: 10 Hz). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Drive", meta = (ClampMin = "0.02", Units = "s")) float PollInterval = 0.1f;

	// ---- obstruction light ----
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Light") float OnThreshold = 0.30f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Light") float OffHysteresis = 0.05f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Light", meta = (ClampMin = "0.05", Units = "s")) float LightRampTime = 0.6f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Light") FLinearColor LightColor = FLinearColor(1.f, 0.08f, 0.05f);
	/** Candelas at full pulse (spec: Red 6). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Light") float LightIntensityMax = 6.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Light", meta = (Units = "cm")) float LightAttenuation = 1500.f;
	/** Pulse frequency, Hz (spec: 0.5). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Light") float PulseHz = 0.5f;
	/** Fraction of the emissive / light left on while the light is off. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Light") float OffFraction = 0.f;
	/** Material slot of the beacon lens on SK_Agro_WindGen and its emissive scalar (MI_Atoll_Beacon -> M_Atoll_Master). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Light") FName BeaconSlotName = TEXT("MS_Beacon");
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|WindGen|Light") FName EmissiveParam = TEXT("EmissiveIntensity");

private:
	void Poll();
	void ApplyLight(float DeltaSeconds);

	float PollAccum = 0.f;
	float LastWind01 = 0.f;
	float LastGate = 0.f;
	float RateJitter = 1.f;
	float TargetSpinRate = 0.35f;
	float TargetFurlAlpha = 0.f;
	float LightOnAlpha = 0.f;
	float PulseTime = 0.f;
	bool bLightOn = false;
	float BaseEmissive = 1.f;

	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> BeaconMID;
};
