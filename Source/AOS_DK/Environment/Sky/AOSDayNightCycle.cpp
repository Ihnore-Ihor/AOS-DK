#include "AOS_DK/Environment/Sky/AOSDayNightCycle.h"

#include "AOS_DK/Environment/Ocean/AOSOceanDepthController.h"
#include "AOS_DK/Environment/Sky/AOSEnvironmentState.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PostProcessComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"

namespace
{
	/** Applies Fn to the given world when it is a game world, otherwise to every PIE / game world. */
	template <typename FnType>
	void ForEachGameWorld(UWorld* Hint, FnType Fn)
	{
		if (Hint && Hint->IsGameWorld())
		{
			Fn(Hint);
			return;
		}
		if (GEngine)
		{
			for (const FWorldContext& Context : GEngine->GetWorldContexts())
			{
				if (Context.World() && Context.World()->IsGameWorld())
				{
					Fn(Context.World());
				}
			}
		}
	}

	template <typename FnType>
	void ForEachCycle(UWorld* Hint, FnType Fn)
	{
		ForEachGameWorld(Hint, [&Fn](UWorld* World)
		{
			for (TActorIterator<AAOSDayNightCycle> It(World); It; ++It)
			{
				Fn(*It);
			}
		});
	}

	FAutoConsoleCommandWithWorldAndArgs GCmdTimeOfDay(TEXT("aos.env.TimeOfDay"),
		TEXT("aos.env.TimeOfDay <hour 0-24>: jump the day/night clock."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (Args.Num() < 1) { return; }
			const float Hour = FCString::Atof(*Args[0]);
			ForEachCycle(World, [Hour](AAOSDayNightCycle* C) { C->SetTimeOfDay(Hour); });
		}));

	FAutoConsoleCommandWithWorldAndArgs GCmdDayLength(TEXT("aos.env.DayLengthMin"),
		TEXT("aos.env.DayLengthMin <minutes per 24 h>."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (Args.Num() < 1) { return; }
			const float Minutes = FMath::Max(FCString::Atof(*Args[0]), 0.05f);
			ForEachCycle(World, [Minutes](AAOSDayNightCycle* C) { C->DayLengthMinutes = Minutes; });
		}));

	FAutoConsoleCommandWithWorldAndArgs GCmdPause(TEXT("aos.env.Pause"),
		TEXT("aos.env.Pause <0|1>: freeze / resume the day/night clock."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (Args.Num() < 1) { return; }
			const bool bPause = FCString::Atoi(*Args[0]) != 0;
			ForEachCycle(World, [bPause](AAOSDayNightCycle* C) { C->bPaused = bPause; });
		}));
}

AAOSDayNightCycle::AAOSDayNightCycle()
{
	PrimaryActorTick.bCanEverTick = true;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	NightExposure = CreateDefaultSubobject<UPostProcessComponent>(TEXT("NightExposure"));
	NightExposure->SetupAttachment(RootComponent);
	NightExposure->bUnbound = true;
	NightExposure->Priority = -100.f;   // below the water body's underwater PP (priority 0)
	NightExposure->BlendWeight = 0.f;   // driven by Step(); 0 in the editor and by day
	NightExposure->Settings.bOverride_AutoExposureMinBrightness = true;
	NightExposure->Settings.bOverride_AutoExposureMaxBrightness = true;
#if WITH_EDITORONLY_DATA
	bIsSpatiallyLoaded = false;
#endif
}

void AAOSDayNightCycle::BeginPlay()
{
	Super::BeginPlay();
	PrimaryActorTick.TickInterval = 0.f; // rotations every frame; the heavy Step() is throttled in Tick
	ResolveReferences();

	if (Moon)
	{
		if (UDirectionalLightComponent* MoonComp = Cast<UDirectionalLightComponent>(Moon->GetLightComponent()))
		{
			MoonComp->SetLightSourceAngle(MoonSourceAngleDeg);
			MoonComp->SetAtmosphereSunDiskColorScale(FLinearColor(MoonDiskColorScale, MoonDiskColorScale, MoonDiskColorScale, 1.f));
		}
	}

	if (bSolveAzimuthOffset && Sun)
	{
		float El, Az;
		SolveSun(15.f, El, Az);
		SunAzimuthOffsetDeg = FRotator::NormalizeAxis(Sun->GetActorRotation().Yaw - (Az + 180.f));
	}

	if (NightExposure)
	{
		NightExposure->Settings.AutoExposureMinBrightness = NightExposureEV;
		NightExposure->Settings.AutoExposureMaxBrightness = NightExposureEV;
	}

	TimeOfDayH = FMath::Fmod(StartTimeOfDay, 24.f);
	Step();
}

void AAOSDayNightCycle::ResolveReferences()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	for (TActorIterator<ADirectionalLight> It(World); It; ++It)
	{
		const UDirectionalLightComponent* Comp = Cast<UDirectionalLightComponent>(It->GetLightComponent());
		if (!Comp || !Comp->IsUsedAsAtmosphereSunLight()) { continue; }
		if (Comp->GetAtmosphereSunLightIndex() == 0) { if (!Sun) { Sun = *It; } }
		else if (Comp->GetAtmosphereSunLightIndex() == 1) { if (!Moon) { Moon = *It; } }
	}
	if (!OceanController)
	{
		for (TActorIterator<AAOSOceanDepthController> It(World); It; ++It) { OceanController = *It; break; }
	}
}

void AAOSDayNightCycle::SolveSun(float Hour, float& OutElevationDeg, float& OutAzimuthDeg) const
{
	const float Phi = FMath::DegreesToRadians(LatitudeDeg);
	const float Delta = FMath::DegreesToRadians(DeclinationDeg);
	const float H = FMath::DegreesToRadians(15.f * (Hour - 12.f));

	const float SinEl = FMath::Sin(Phi) * FMath::Sin(Delta) + FMath::Cos(Phi) * FMath::Cos(Delta) * FMath::Cos(H);
	OutElevationDeg = FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(SinEl, -1.f, 1.f)));
	const float Az = FMath::Atan2(-FMath::Sin(H), FMath::Tan(Delta) * FMath::Cos(Phi) - FMath::Sin(Phi) * FMath::Cos(H));
	OutAzimuthDeg = FMath::RadiansToDegrees(Az);
}

void AAOSDayNightCycle::SetTimeOfDay(float Hour)
{
	TimeOfDayH = FMath::Fmod(FMath::Fmod(Hour, 24.f) + 24.f, 24.f);
	Step();
}

void AAOSDayNightCycle::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bPaused)
	{
		TimeOfDayH = FMath::Fmod(TimeOfDayH + DeltaSeconds * 24.f / (FMath::Max(DayLengthMinutes, 0.05f) * 60.f), 24.f);
	}

	Accum += DeltaSeconds;
	if (Accum >= 1.f / FMath::Max(UpdateHz, 1.f))
	{
		Accum = 0.f;
		Step();
	}
	else
	{
		UpdateOrientation(); // smooth sun / moon motion between the throttled publishes
	}
}

float AAOSDayNightCycle::UpdateOrientation()
{
	float El, Az;
	SolveSun(TimeOfDayH, El, Az);
	SunElevationDeg = El;

	if (Sun)
	{
		Sun->SetActorRotation(FRotator(-El, Az + 180.f + SunAzimuthOffsetDeg, 0.f));
	}
	if (Moon)
	{
		// antipodal: elevation -El, azimuth + 180 of the sun's position
		Moon->SetActorRotation(FRotator(El, Az + SunAzimuthOffsetDeg, 0.f));
	}
	return El;
}

void AAOSDayNightCycle::ApplyForwardShadingPriority(bool bMoonLeads)
{
	const int32 Lead = bMoonLeads ? 1 : 0;
	if (Lead == ForwardLead)
	{
		return;
	}
	ForwardLead = Lead;
	if (Sun)
	{
		if (UDirectionalLightComponent* C = Cast<UDirectionalLightComponent>(Sun->GetLightComponent()))
		{
			C->SetForwardShadingPriority(bMoonLeads ? 0 : 1);
		}
	}
	if (Moon)
	{
		if (UDirectionalLightComponent* C = Cast<UDirectionalLightComponent>(Moon->GetLightComponent()))
		{
			C->SetForwardShadingPriority(bMoonLeads ? 1 : 0);
		}
	}
}

void AAOSDayNightCycle::Step()
{
	const float El = UpdateOrientation();

	UWorld* World = GetWorld();
	UAOSEnvironmentStateSubsystem* Env = World ? World->GetSubsystem<UAOSEnvironmentStateSubsystem>() : nullptr;

	if (Moon)
	{
		if (ULightComponent* MoonLight = Moon->GetLightComponent())
		{
			const float Surface = OceanController ? OceanController->GetSurfaceLightFactor() : 1.f;
			// Heavy overcast hides the moon completely (light + atmosphere disk): never a disk peeking through cloud gaps.
			const float StormAlpha = Env ? Env->GetState().StormAlpha : 0.f;
			const float StormFade = (MoonStormFadeEndAlpha > MoonStormFadeStartAlpha)
				? 1.f - FMath::SmoothStep(MoonStormFadeStartAlpha, MoonStormFadeEndAlpha, StormAlpha)
				: 1.f;
			const float Target = MoonIntensity * FMath::SmoothStep(0.f, 10.f, -El) * Surface * StormFade;
			const bool bZeroChanged = (Target <= KINDA_SMALL_NUMBER) != (LastMoonIntensity <= KINDA_SMALL_NUMBER);
			if (bZeroChanged || FMath::Abs(Target - LastMoonIntensity) > 0.002f * FMath::Max(MoonIntensity, 0.01f))
			{
				LastMoonIntensity = Target;
				MoonLight->SetIntensity(Target);
				MoonLight->SetVisibility(Target > KINDA_SMALL_NUMBER);
			}
		}
	}

	// Exactly one forward-shading directional light at any time: the brighter of the sun and the moon.
	if (Sun && Moon && Sun->GetLightComponent() && Moon->GetLightComponent())
	{
		const float SunI = Sun->GetLightComponent()->Intensity;
		const float MoonI = Moon->GetLightComponent()->Intensity;
		ApplyForwardShadingPriority(MoonI > SunI);
	}

	const float DayFactor = FMath::SmoothStep(-4.f, 6.f, El);
	const float NightFactor = 1.f - FMath::SmoothStep(-6.f, 4.f, El);

	if (NightExposure)
	{
		NightExposure->BlendWeight = bClampNightExposure ? NightFactor : 0.f;
	}
	if (Env)
	{
		Env->PublishDayNight(TimeOfDayH, El, DayFactor, NightFactor);
	}
}
