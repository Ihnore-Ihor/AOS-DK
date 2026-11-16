#include "AOS_DK/Environment/Atoll/AOSWindGenerator.h"

#include "AOS_DK/Environment/Atoll/AOSWindGenAnimInstance.h"
#include "AOS_DK/Environment/Sky/AOSEnvironmentState.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const FName ObstructionSocket(TEXT("SOCKET_Light_Obstr"));
}

AAOSWindGenerator::AAOSWindGenerator()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	TurbineMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("TurbineMesh"));
	TurbineMesh->SetupAttachment(Root);
	TurbineMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	TurbineMesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	TurbineMesh->AnimClass = UAOSWindGenAnimInstance::StaticClass();     // BP_AOS_WindGen swaps in ABP_WindGen (same parent class)
	// The nacelle yaws +-10 deg and the rotor spins: keep the pose fresh whenever the actor is visible, skip it when it is not.
	TurbineMesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
	TurbineMesh->bEnableUpdateRateOptimizations = false;
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MeshFinder(TEXT("/Game/AOS_DK_Game/Environment/Atoll/WindGen/SK_Agro_WindGen.SK_Agro_WindGen"));
	if (MeshFinder.Succeeded())
	{
		TurbineMesh->SetSkeletalMeshAsset(MeshFinder.Object);
	}

	TowerCapsule = CreateDefaultSubobject<UCapsuleComponent>(TEXT("TowerCapsule"));
	TowerCapsule->SetupAttachment(Root);
	TowerCapsule->InitCapsuleSize(22.f, 450.f);
	TowerCapsule->SetRelativeLocation(FVector(0.f, 0.f, 450.f));
	TowerCapsule->SetCollisionProfileName(TEXT("BlockAll"));
	TowerCapsule->SetCanEverAffectNavigation(true);

	BaseCollision = CreateDefaultSubobject<UBoxComponent>(TEXT("BaseCollision"));
	BaseCollision->SetupAttachment(Root);
	BaseCollision->SetBoxExtent(FVector(100.f, 100.f, 15.f));
	BaseCollision->SetRelativeLocation(FVector(0.f, 0.f, 15.f));
	BaseCollision->SetCollisionProfileName(TEXT("BlockAll"));

	ObstructionLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("ObstructionLight"));
	ObstructionLight->SetupAttachment(TurbineMesh, ObstructionSocket);
	ObstructionLight->SetRelativeLocation(FVector(0.f, 0.f, 6.f));
	ObstructionLight->SetCastShadows(false);
	ObstructionLight->SetIntensityUnits(ELightUnits::Candelas);
	ObstructionLight->SetLightColor(LightColor);
	ObstructionLight->SetAttenuationRadius(LightAttenuation);
	ObstructionLight->SetSourceRadius(4.f);
	ObstructionLight->SetIntensity(0.f);
	ObstructionLight->SetVisibility(false);
}

UAOSWindGenAnimInstance* AAOSWindGenerator::GetWindAnim() const
{
	return TurbineMesh ? Cast<UAOSWindGenAnimInstance>(TurbineMesh->GetAnimInstance()) : nullptr;
}

float AAOSWindGenerator::GetLightIntensity() const
{
	return ObstructionLight ? ObstructionLight->Intensity : 0.f;
}

void AAOSWindGenerator::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	if (ObstructionLight)
	{
		ObstructionLight->SetLightColor(LightColor);
		ObstructionLight->SetAttenuationRadius(LightAttenuation);
	}
}

void AAOSWindGenerator::BeginPlay()
{
	Super::BeginPlay();

	// Deterministic per-instance randomness: the same turbine in the same spot always starts the same way.
	FRandomStream Stream(GetTypeHash(GetActorLocation().ToString()));
	RateJitter = 1.f + Stream.FRandRange(-RateJitterFraction, RateJitterFraction);
	const float SpinPhase = Stream.FRand();
	const float HuntPhase = Stream.FRand();
	PulseTime = Stream.FRand() / FMath::Max(PulseHz, 0.01f);

	if (UAOSWindGenAnimInstance* Anim = GetWindAnim())
	{
		const float SpinLen = Anim->SpinAnim ? Anim->SpinAnim->GetPlayLength() : 3.f;
		const float HuntLen = Anim->HuntAnim ? Anim->HuntAnim->GetPlayLength() : 8.f;
		Anim->SetInitialPhases(SpinPhase * SpinLen, HuntPhase * HuntLen);
	}

	if (TurbineMesh)
	{
		const int32 Slot = TurbineMesh->GetMaterialIndex(BeaconSlotName);
		if (Slot != INDEX_NONE && TurbineMesh->GetMaterial(Slot))
		{
			BeaconMID = TurbineMesh->CreateDynamicMaterialInstance(Slot, TurbineMesh->GetMaterial(Slot));
			if (BeaconMID)
			{
				BeaconMID->GetScalarParameterValue(FHashedMaterialParameterInfo(EmissiveParam), BaseEmissive);
			}
		}
	}

	Poll();
	if (UAOSWindGenAnimInstance* Anim = GetWindAnim())
	{
		Anim->SpinRate = TargetSpinRate;          // no run-up from zero at level start
		Anim->FurlAlpha = TargetFurlAlpha;
	}
	LightOnAlpha = bLightOn ? 1.f : 0.f;
	ApplyLight(0.f);
}

void AAOSWindGenerator::Poll()
{
	float Wind = LastWind01;
	float Gate = LastGate;
	if (const UWorld* World = GetWorld())
	{
		if (const UAOSEnvironmentStateSubsystem* Env = World->GetSubsystem<UAOSEnvironmentStateSubsystem>())
		{
			const FAOSEnvironmentState& S = Env->GetState();
			Wind = S.Wind01;
			Gate = FMath::Max(S.NightFactor, S.StormAlpha);
		}
	}
	LastWind01 = Wind;
	LastGate = Gate;

	TargetSpinRate = (SpinBase + SpinPerWind * Wind) * RateJitter;
	TargetFurlAlpha = FMath::SmoothStep(FurlStartWind, FurlFullWind, Wind);
	if (UAOSWindGenAnimInstance* Anim = GetWindAnim())
	{
		Anim->SetDrive(TargetSpinRate, TargetFurlAlpha);
	}

	// ON above OnThreshold, OFF again below OnThreshold - OffHysteresis
	if (!bLightOn && Gate > OnThreshold) { bLightOn = true; }
	else if (bLightOn && Gate < OnThreshold - OffHysteresis) { bLightOn = false; }
}

void AAOSWindGenerator::ApplyLight(float DeltaSeconds)
{
	const float Target = bLightOn ? 1.f : 0.f;
	LightOnAlpha = DeltaSeconds > 0.f ? FMath::FInterpConstantTo(LightOnAlpha, Target, DeltaSeconds, 1.f / FMath::Max(LightRampTime, 0.05f)) : Target;

	PulseTime += DeltaSeconds;
	const float Phase = 0.5f + 0.5f * FMath::Sin(2.f * PI * PulseHz * PulseTime);        // 0..1, 0.5 Hz
	const float Pulse = 0.15f + 0.85f * Phase * Phase;
	const float Level = FMath::Lerp(OffFraction, 1.f, LightOnAlpha) * (LightOnAlpha > 0.f ? Pulse : 1.f);

	if (ObstructionLight)
	{
		ObstructionLight->SetVisibility(LightOnAlpha > 0.001f);
		ObstructionLight->SetIntensity(LightIntensityMax * LightOnAlpha * Pulse);
	}
	if (BeaconMID)
	{
		BeaconMID->SetScalarParameterValue(EmissiveParam, BaseEmissive * FMath::Max(Level, 0.f));
	}
}

void AAOSWindGenerator::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	PollAccum += DeltaSeconds;
	if (PollAccum >= PollInterval)
	{
		PollAccum = 0.f;
		Poll();
	}
	ApplyLight(DeltaSeconds);
}
