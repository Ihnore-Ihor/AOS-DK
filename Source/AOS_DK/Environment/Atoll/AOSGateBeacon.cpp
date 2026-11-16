#include "AOS_DK/Environment/Atoll/AOSGateBeacon.h"

#include "AOS_DK/Environment/Sky/AOSEnvironmentState.h"
#include "Components/SceneComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include <initializer_list>
#include "GameFramework/RotatingMovementComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AAOSGateBeacon::AAOSGateBeacon()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));

	// Housing: engine Cylinder 0.6 x 0.6 x 0.3 (60 x 60 x 30 cm), sits on the mast-top stub.
	BaseMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BaseMesh"));
	BaseMesh->SetupAttachment(Root);
	BaseMesh->SetMobility(EComponentMobility::Movable);
	if (CylinderMesh.Succeeded()) { BaseMesh->SetStaticMesh(CylinderMesh.Object); }
	BaseMesh->SetRelativeLocation(FVector(0.f, 0.f, 15.f));
	BaseMesh->SetRelativeScale3D(FVector(0.6f, 0.6f, 0.3f));
	BaseMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	BaseMesh->SetCastShadow(false);

	// Rotating pivot (yaw) on top of the housing.
	YawPivot = CreateDefaultSubobject<USceneComponent>(TEXT("YawPivot"));
	YawPivot->SetupAttachment(Root);
	YawPivot->SetMobility(EComponentMobility::Movable);
	YawPivot->SetRelativeLocation(FVector(0.f, 0.f, 30.f));

	// Lens head: engine Cylinder 0.45 x 0.45 x 0.5 (45 x 45 x 50 cm), carries the tilt.
	LensHead = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("LensHead"));
	LensHead->SetupAttachment(YawPivot);
	LensHead->SetMobility(EComponentMobility::Movable);
	if (CylinderMesh.Succeeded()) { LensHead->SetStaticMesh(CylinderMesh.Object); }
	LensHead->SetRelativeLocation(FVector(0.f, 0.f, 25.f));
	LensHead->SetRelativeScale3D(FVector(0.45f, 0.45f, 0.5f));
	LensHead->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	LensHead->SetCastShadow(false);

	// Back-to-back spots (+X and -X of the lens head; the head yaws, so the beams sweep).
	// Scale compensation: the spots are children of the scaled LensHead, so the light uses unit relative scale via inverse scale.
	const FVector InvScale(1.f / 0.45f, 1.f / 0.45f, 1.f / 0.5f);

	SpotFront = CreateDefaultSubobject<USpotLightComponent>(TEXT("SpotFront"));
	SpotFront->SetupAttachment(LensHead);
	SpotFront->SetMobility(EComponentMobility::Movable);
	SpotFront->SetRelativeLocation(FVector(55.f, 0.f, 0.f)); // just outside the lens wall (parent-local units: cylinder radius 50, scaled 0.45)
	SpotFront->SetRelativeRotation(FRotator(0.f, 0.f, 0.f));
	SpotFront->SetRelativeScale3D(InvScale);

	SpotBack = CreateDefaultSubobject<USpotLightComponent>(TEXT("SpotBack"));
	SpotBack->SetupAttachment(LensHead);
	SpotBack->SetMobility(EComponentMobility::Movable);
	SpotBack->SetRelativeLocation(FVector(-55.f, 0.f, 0.f));
	SpotBack->SetRelativeRotation(FRotator(0.f, 180.f, 0.f));
	SpotBack->SetRelativeScale3D(InvScale);

	Rotation = CreateDefaultSubobject<URotatingMovementComponent>(TEXT("Rotation"));
	Rotation->SetUpdatedComponent(YawPivot);
	Rotation->bRotationInLocalSpace = true;
	Rotation->PivotTranslation = FVector::ZeroVector;
	Rotation->RotationRate = FRotator(0.f, IdleYawRateDegPerSec, 0.f);

	// Flash loop (4 s): 0.2 -> 1.0 at 0.12 s -> 0.25 at 0.45 s -> 0.2 at 4.0 s (seamless: first == last value).
	const FKeyHandle K0 = FlashCurve.AddKey(0.f, 0.2f);
	const FKeyHandle K1 = FlashCurve.AddKey(0.12f, 1.f);
	const FKeyHandle K2 = FlashCurve.AddKey(0.45f, 0.25f);
	const FKeyHandle K3 = FlashCurve.AddKey(4.f, 0.2f);
	for (const FKeyHandle& H : { K0, K1, K2, K3 })
	{
		FlashCurve.SetKeyInterpMode(H, RCIM_Cubic);
		FlashCurve.SetKeyTangentMode(H, RCTM_Auto);
	}
	FlashCurve.AutoSetTangents();

	ApplyStaticSettings();
}

void AAOSGateBeacon::ApplyStaticSettings()
{
	for (USpotLightComponent* S : { SpotFront.Get(), SpotBack.Get() })
	{
		if (!S) { continue; }
		S->SetLightColor(LightColor);
		S->SetInnerConeAngle(InnerConeDeg);
		S->SetOuterConeAngle(OuterConeDeg);
		S->SetAttenuationRadius(AttenuationRadius);
		S->SetVolumetricScatteringIntensity(VolumetricScattering);
		S->SetCastShadows(false);
		S->SetIntensityUnits(ELightUnits::Candelas);
		S->SetIntensity(SpotIntensityMax * OffIntensityFraction * 0.2f); // pulse base (Flash 0.2) while off
	}
}

void AAOSGateBeacon::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	if (HousingMaterial && BaseMesh) { BaseMesh->SetMaterial(0, HousingMaterial); }
	if (LensMaterial && LensHead) { LensHead->SetMaterial(0, LensMaterial); }
	ApplyStaticSettings();
	if (Rotation) { Rotation->RotationRate = FRotator(0.f, IdleYawRateDegPerSec, 0.f); }
}

void AAOSGateBeacon::BeginPlay()
{
	Super::BeginPlay();
	ApplyStaticSettings();
	if (LensHead && LensHead->GetMaterial(0))
	{
		LensMID = LensHead->CreateDynamicMaterialInstance(0, LensHead->GetMaterial(0));
	}
	PulseTime = FMath::Fmod(FMath::Max(0.f, PhaseOffsetSec), PulsePeriod);
	PollEnvironment();
	OnAlpha = bBeaconOn ? 1.f : 0.f; // no ramp from nothing at level start
	PollAccum = 0.f;
	if (Rotation) { Rotation->RotationRate = FRotator(0.f, FMath::Lerp(IdleYawRateDegPerSec, OnYawRateDegPerSec, OnAlpha), 0.f); }
	ApplyLights(CurrentFlash);
}

void AAOSGateBeacon::PollEnvironment()
{
	float Gate = 0.f;
	if (const UWorld* World = GetWorld())
	{
		if (const UAOSEnvironmentStateSubsystem* Env = World->GetSubsystem<UAOSEnvironmentStateSubsystem>())
		{
			const FAOSEnvironmentState& S = Env->GetState();
			Gate = FMath::Max(S.NightFactor, S.StormAlpha);
		}
	}
	if (!bBeaconOn && Gate > OnThreshold) { bBeaconOn = true; }
	else if (bBeaconOn && Gate < OnThreshold - Hysteresis) { bBeaconOn = false; }
}

float AAOSGateBeacon::GetYawRateDegPerSec() const
{
	return Rotation ? Rotation->RotationRate.Yaw : 0.f;
}

float AAOSGateBeacon::GetSpotIntensity() const
{
	return SpotFront ? SpotFront->Intensity : 0.f;
}

void AAOSGateBeacon::ApplyLights(float Flash)
{
	// ON: Flash curve scales the full intensity. OFF: standby fraction, no pulse.
	const float OnIntensity = SpotIntensityMax * Flash;
	const float OffIntensity = SpotIntensityMax * OffIntensityFraction;
	const float Intensity = FMath::Lerp(OffIntensity, OnIntensity, OnAlpha);
	if (SpotFront) { SpotFront->SetIntensity(Intensity); }
	if (SpotBack) { SpotBack->SetIntensity(Intensity); }
	if (LensMID)
	{
		const float Emissive = LensEmissiveMax * FMath::Lerp(OffIntensityFraction, Flash, OnAlpha);
		LensMID->SetScalarParameterValue(LensEmissiveParam, Emissive);
	}
}

void AAOSGateBeacon::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	PollAccum += DeltaSeconds;
	if (PollAccum >= PollInterval)
	{
		PollAccum = FMath::Fmod(PollAccum, PollInterval);
		PollEnvironment();
	}

	OnAlpha = FMath::FInterpConstantTo(OnAlpha, bBeaconOn ? 1.f : 0.f, DeltaSeconds, 1.f / FMath::Max(RampTime, 0.05f));

	// 4 s loop clock only advances while (partly) on.
	if (OnAlpha > 0.f)
	{
		PulseTime = FMath::Fmod(PulseTime + DeltaSeconds, PulsePeriod);
	}

	const float Raw = FlashCurve.Eval(FMath::Fmod(PulseTime, 4.f));
	CurrentFlash = FMath::Clamp(Raw, 0.f, 1.f);
	CurrentTiltDeg = TiltAmplitudeDeg * FMath::Sin(2.f * UE_PI * PulseTime / PulsePeriod) * OnAlpha;

	if (Rotation) { Rotation->RotationRate = FRotator(0.f, FMath::Lerp(IdleYawRateDegPerSec, OnYawRateDegPerSec, OnAlpha), 0.f); }
	if (LensHead) { LensHead->SetRelativeRotation(FRotator(CurrentTiltDeg, 0.f, 0.f)); }
	ApplyLights(CurrentFlash);
}
