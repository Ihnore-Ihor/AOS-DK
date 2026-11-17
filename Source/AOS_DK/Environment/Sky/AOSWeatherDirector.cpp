#include "AOS_DK/Environment/Sky/AOSWeatherDirector.h"

#include "AOS_DK/Environment/Ocean/AOSOceanDepthController.h"
#include "AOS_DK/Environment/Sky/AOSEnvironmentState.h"
#include "Components/VolumetricCloudComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Camera/PlayerCameraManager.h"

namespace
{
	const FName CloudCoverage(TEXT("Cloud_GlobalCoverage"));
	const FName CloudDensity(TEXT("Cloud_GlobalDensity"));
	const FName CloudStorm(TEXT("StormClouds"));
	constexpr float HoldForever = 1.0e9f;
	constexpr float Epsilon = 0.0001f; // cloud density is ~0.01 scale: a coarse threshold would stop the lerp short

	FAutoConsoleCommandWithWorldAndArgs GCmdStorm(TEXT("aos.env.Storm"),
		TEXT("aos.env.Storm <0|1|auto>: 1 = storm now (held), 0 = clear now (held), auto = random cycle."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* Hint)
		{
			if (Args.Num() < 1) { return; }
			const int32 Mode = Args[0].Equals(TEXT("auto"), ESearchCase::IgnoreCase) ? -1 : (FCString::Atoi(*Args[0]) != 0 ? 1 : 0);
			auto Apply = [Mode](UWorld* World)
			{
				for (TActorIterator<AAOSWeatherDirector> It(World); It; ++It) { It->ForceStorm(Mode); }
			};
			if (Hint && Hint->IsGameWorld()) { Apply(Hint); return; }
			if (GEngine)
			{
				for (const FWorldContext& Context : GEngine->GetWorldContexts())
				{
					if (Context.World() && Context.World()->IsGameWorld()) { Apply(Context.World()); }
				}
			}
		}));
}

AAOSWeatherDirector::AAOSWeatherDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
#if WITH_EDITORONLY_DATA
	bIsSpatiallyLoaded = false;
#endif
}

float AAOSWeatherDirector::RandRange(const FVector2D& Range)
{
	return Random.FRandRange(static_cast<float>(Range.X), static_cast<float>(Range.Y));
}

void AAOSWeatherDirector::BeginPlay()
{
	Super::BeginPlay();
	Random.Initialize(Seed != 0 ? Seed : static_cast<int32>(FPlatformTime::Cycles() & 0x7fffffff));
	GustOffset = Random.FRandRange(0.f, 100.f);
	ResolveReferences();
	EnterClear();
	Publish();
}

void AAOSWeatherDirector::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (VolumetricCloud && OriginalCloudMaterial)
	{
		if (UVolumetricCloudComponent* Cloud = VolumetricCloud->FindComponentByClass<UVolumetricCloudComponent>())
		{
			Cloud->SetMaterial(OriginalCloudMaterial);
		}
	}
	if (RainComponent)
	{
		RainComponent->DestroyComponent();
		RainComponent = nullptr;
	}
	Super::EndPlay(EndPlayReason);
}

void AAOSWeatherDirector::ResolveReferences()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (!VolumetricCloud) { for (TActorIterator<AVolumetricCloud> It(World); It; ++It) { VolumetricCloud = *It; break; } }
	if (!OceanController) { for (TActorIterator<AAOSOceanDepthController> It(World); It; ++It) { OceanController = *It; break; } }

	// Runtime MID: the engine cloud MI asset is never edited.
	if (VolumetricCloud)
	{
		if (UVolumetricCloudComponent* Cloud = VolumetricCloud->FindComponentByClass<UVolumetricCloudComponent>())
		{
			OriginalCloudMaterial = Cloud->GetMaterial();
			if (OriginalCloudMaterial)
			{
				OriginalCloudMaterial->GetScalarParameterValue(FHashedMaterialParameterInfo(CloudCoverage), BaseCoverage);
				OriginalCloudMaterial->GetScalarParameterValue(FHashedMaterialParameterInfo(CloudDensity), BaseDensity);
				OriginalCloudMaterial->GetScalarParameterValue(FHashedMaterialParameterInfo(CloudStorm), BaseStorm);
				CloudMID = UMaterialInstanceDynamic::Create(OriginalCloudMaterial, this);
				Cloud->SetMaterial(CloudMID);
			}
		}
	}
}

void AAOSWeatherDirector::SetState(EAOSWeatherState NewState, float Duration)
{
	const EAOSWeatherState Old = State;
	State = NewState;
	StateTime = 0.f;
	StateDuration = Duration;
	if (NewState == EAOSWeatherState::Building) { BuildStartAlpha = StormAlpha; }
	if (NewState == EAOSWeatherState::Clearing) { ClearingStartAlpha = StormAlpha; }
	if (Old != NewState)
	{
		UE_LOG(LogTemp, Log, TEXT("AOS weather: %d -> %d (duration %.0fs, storm %.2f)"), int32(Old), int32(NewState), Duration, StormAlpha);
		BP_OnWeatherStateChanged(NewState, Old);
	}
}

void AAOSWeatherDirector::EnterClear()
{
	WindBaseTarget = Random.FRandRange(0.15f, 0.30f);
	float Duration = (ForcedMode == -1) ? (bFirstClear ? RandRange(FirstStormDelay) : RandRange(ClearDuration)) : HoldForever;
	bFirstClear = false;
	SetState(EAOSWeatherState::Clear, Duration);
}

void AAOSWeatherDirector::ForceStorm(int32 Mode)
{
	ForcedMode = FMath::Clamp(Mode, -1, 1);
	if (ForcedMode == 1)
	{
		Peak = 1.f;
		if (State == EAOSWeatherState::Raining) { StateDuration = HoldForever; }
		else if (State != EAOSWeatherState::Building) { SetState(EAOSWeatherState::Building, ForcedTransitionSeconds); }
	}
	else if (ForcedMode == 0)
	{
		if (StormAlpha > 0.001f) { SetState(EAOSWeatherState::Clearing, ForcedTransitionSeconds); }
		else { SetState(EAOSWeatherState::Clear, HoldForever); }
	}
	else
	{
		if (StormAlpha > 0.001f) { SetState(EAOSWeatherState::Clearing, RandRange(ClearingDuration)); }
		else { EnterClear(); }
	}
}

void AAOSWeatherDirector::StepFsm(float Dt)
{
	StateTime += Dt;
	const float U = StateDuration > 0.f ? FMath::Clamp(StateTime / StateDuration, 0.f, 1.f) : 1.f;

	switch (State)
	{
	case EAOSWeatherState::Clear:
		StormAlpha = 0.f;
		if (ForcedMode == -1 && StateTime >= StateDuration)
		{
			Peak = RandRange(PeakRange);
			SetState(EAOSWeatherState::Building, RandRange(BuildingDuration));
		}
		break;

	case EAOSWeatherState::Building:
		StormAlpha = FMath::Lerp(BuildStartAlpha, Peak, FMath::SmoothStep(0.f, 1.f, U));
		if (U >= 1.f)
		{
			SetState(EAOSWeatherState::Raining, ForcedMode == 1 ? HoldForever : RandRange(RainingDuration));
		}
		break;

	case EAOSWeatherState::Raining:
		StormAlpha = Peak;
		if (ForcedMode == -1 && StateTime >= StateDuration)
		{
			SetState(EAOSWeatherState::Clearing, RandRange(ClearingDuration));
		}
		break;

	case EAOSWeatherState::Clearing:
		StormAlpha = ClearingStartAlpha * (1.f - FMath::SmoothStep(0.f, 1.f, U));
		if (U >= 1.f)
		{
			StormAlpha = 0.f;
			EnterClear();
		}
		break;
	}

	// gust: Perlin noise at 0.15 Hz mapped to 0..1
	const float Gust = 0.5f + 0.5f * FMath::Clamp(FMath::PerlinNoise1D(ElapsedTime * 0.15f + GustOffset), -1.f, 1.f);

	WindBase = FMath::FInterpTo(WindBase, WindBaseTarget, Dt, 0.1f);
	Wind01 = FMath::Clamp(WindBase + 0.7f * StormAlpha + 0.1f * Gust, 0.f, 1.f);

	const bool bRaining = State == EAOSWeatherState::Raining || (State == EAOSWeatherState::Clearing && StormAlpha >= 0.35f);
	RainRate01 = bRaining ? FMath::Clamp(FMath::Pow(StormAlpha, 1.5f) * (1.f + 0.25f * Gust), 0.f, 1.f) : 0.f;

	// +1 / 25 s while it rains, -1 / 120 s while it dries
	if (RainRate01 > 0.1f) { Wetness += Dt / FMath::Max(WetRiseSeconds, 0.1f); }
	else { Wetness -= Dt / FMath::Max(DryFallSeconds, 0.1f); }
	Wetness = FMath::Clamp(Wetness, 0.f, 1.f);
}

void AAOSWeatherDirector::UpdateClouds()
{
	if (!CloudMID)
	{
		return;
	}
	const float S = StormAlpha;
	// Overcast is complete well before the rain peaks, so rain never falls from an open sky.
	const float CloudBlend = FMath::SmoothStep(0.f, FMath::Max(CloudsFullAtStorm, 0.05f), S);
	const float Coverage = FMath::Lerp(BaseCoverage, StormCoverage, CloudBlend);
	const float Density = FMath::Lerp(BaseDensity, BaseDensity * StormDensityScale, CloudBlend);
	const float StormLayout = StormCloudsAtPeak * S;
	if (FMath::Abs(Coverage - LastCoverage) > Epsilon) { CloudMID->SetScalarParameterValue(CloudCoverage, Coverage); LastCoverage = Coverage; }
	if (FMath::Abs(Density - LastDensity) > Epsilon) { CloudMID->SetScalarParameterValue(CloudDensity, Density); LastDensity = Density; }
	if (FMath::Abs(StormLayout - LastStormClouds) > Epsilon) { CloudMID->SetScalarParameterValue(CloudStorm, StormLayout); LastStormClouds = StormLayout; }
}

bool AAOSWeatherDirector::GetViewLocation(FVector& OutLocation) const
{
	if (const APlayerCameraManager* Camera = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		OutLocation = Camera->GetCameraLocation();
		return true;
	}
	return false;
}

FVector AAOSWeatherDirector::SnapRainOrigin(const FVector& View, const FVector& Current) const
{
	const double LXY = FMath::Max(static_cast<double>(RainLatticeXY), 15000.0);
	const double LZ = FMath::Max(static_cast<double>(RainLatticeZ), 2000.0);
	const double MarginXY = 0.1 * LXY;
	const double MarginZ = 0.1 * LZ;
	FVector Out = Current;
	if (FMath::Abs(View.X - Current.X) > 0.5 * LXY + MarginXY) { Out.X = FMath::RoundToDouble(View.X / LXY) * LXY; }
	if (FMath::Abs(View.Y - Current.Y) > 0.5 * LXY + MarginXY) { Out.Y = FMath::RoundToDouble(View.Y / LXY) * LXY; }
	if (FMath::Abs(View.Z - Current.Z) > 0.5 * LZ + MarginZ)   { Out.Z = FMath::RoundToDouble(View.Z / LZ) * LZ; }
	return Out;
}

void AAOSWeatherDirector::UpdateRain()
{
	UWorld* World = GetWorld();
	if (!RainSystem || !World)
	{
		return;
	}
	const bool bUnderwater = OceanController && OceanController->IsCameraUnderwater();
	const bool bWanted = RainRate01 > 0.01f && !bUnderwater;

	FVector View = FVector::ZeroVector;
	const bool bHasView = GetViewLocation(View);

	if (!RainComponent && bWanted)
	{
		// Stateless Niagara particles are re-evaluated against the component transform every frame, so the component must never follow
		// the camera continuously (drops would be dragged along). It hops only by whole lattice periods (see RainLatticeXY/Z), which
		// leaves the wrapped rain field unchanged, and M_AOS_RainStreak / M_AOS_RainSplash do the per-frame wrap around the view.
		const FVector Origin = bHasView ? SnapRainOrigin(View, FVector(0.0, 0.0, 0.0)) : FVector::ZeroVector;
		RainComponent = UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, RainSystem, Origin,
			FRotator::ZeroRotator, FVector::OneVector, /*bAutoDestroy*/ false, /*bAutoActivate*/ false);
	}
	if (!RainComponent)
	{
		return;
	}
	if (bWanted)
	{
		if (bHasView)
		{
			const FVector Current = RainComponent->GetComponentLocation();
			const FVector Target = SnapRainOrigin(View, Current);
			if (!Target.Equals(Current, 1.0)) { RainComponent->SetWorldLocation(Target); }
		}
		RainComponent->SetVariableFloat(TEXT("User.RainRate"), 12000.f * RainRate01);
		RainComponent->SetVariableFloat(TEXT("User.WaterZ"), WaterSurfaceZ);
		if (!RainComponent->IsActive()) { RainComponent->Activate(true); }
	}
	else if (RainComponent->IsActive())
	{
		// Underwater: cut every live drop at once (a soft Deactivate would let the last 1.6 s of streaks finish under the surface).
		if (bUnderwater) { RainComponent->DeactivateImmediate(); }
		else { RainComponent->Deactivate(); }
	}
}

void AAOSWeatherDirector::Publish()
{
	if (UWorld* World = GetWorld())
	{
		if (UAOSEnvironmentStateSubsystem* Env = World->GetSubsystem<UAOSEnvironmentStateSubsystem>())
		{
			Env->PublishWeather(StormAlpha, RainRate01, Wetness, Wind01);
		}
	}
	UpdateClouds();
}

void AAOSWeatherDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	ElapsedTime += DeltaSeconds;
	StepFsm(DeltaSeconds);
	UpdateRain();

	PublishAccum += DeltaSeconds;
	if (PublishAccum >= 1.f / FMath::Max(PublishHz, 1.f))
	{
		PublishAccum = 0.f;
		Publish();
	}
}
