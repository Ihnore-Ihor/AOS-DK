#include "AOS_DK/Environment/Sky/AOSEnvironmentState.h"

#include "Engine/World.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialParameterCollection.h"

namespace AOSEnvParams
{
	static const FName NightFactor(TEXT("NightFactor"));
	static const FName Wetness(TEXT("Wetness"));
	static const FName StormAlpha(TEXT("StormAlpha"));
	static const FName Wind01(TEXT("Wind01"));
	static const FName StarVisibility(TEXT("StarVisibility"));
	static constexpr float Epsilon = 0.002f;
}

bool UAOSEnvironmentStateSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return World && World->IsGameWorld(); // PIE / game only: never touches editor-world data
}

void UAOSEnvironmentStateSubsystem::Initialize(FSubsystemCollectionBase& InCollection)
{
	Super::Initialize(InCollection);
	Collection = LoadObject<UMaterialParameterCollection>(nullptr,
		TEXT("/Game/AOS_DK_Game/Environment/Water/MPC_AOS_Atoll.MPC_AOS_Atoll"));
	Recompose();
}

void UAOSEnvironmentStateSubsystem::PublishDayNight(float TimeOfDayH, float SunElevationDeg, float DayFactor, float NightFactor)
{
	State.TimeOfDayH = TimeOfDayH;
	State.SunElevationDeg = SunElevationDeg;
	State.DayFactor = FMath::Clamp(DayFactor, 0.f, 1.f);
	State.NightFactor = FMath::Clamp(NightFactor, 0.f, 1.f);
	Recompose();
}

void UAOSEnvironmentStateSubsystem::PublishWeather(float StormAlpha, float RainRate01, float Wetness, float Wind01)
{
	State.StormAlpha = FMath::Clamp(StormAlpha, 0.f, 1.f);
	State.RainRate01 = FMath::Clamp(RainRate01, 0.f, 1.f);
	State.Wetness = FMath::Clamp(Wetness, 0.f, 1.f);
	State.Wind01 = FMath::Clamp(Wind01, 0.f, 1.f);
	Recompose();
}

void UAOSEnvironmentStateSubsystem::Recompose()
{
	const float Day = State.DayFactor;
	const float Storm = State.StormAlpha;

	State.SunScale = Day * (1.f - 0.75f * Storm);
	State.SkyScale = FMath::Lerp(0.12f, 1.f, Day) * (1.f - 0.40f * Storm);
	State.FogDensityScale = 1.f + 3.f * Storm;
	State.FogInscatterScale = FMath::Lerp(0.15f, 1.f, Day) * (1.f - 0.3f * Storm);
	// Stars follow the REAL night (State.NightFactor, not the storm-lamp boosted MPC value) and are covered by the overcast.
	State.StarVisibility = State.NightFactor * (1.f - FMath::SmoothStep(0.05f, 0.5f, Storm));

	bool bScalesChanged = false;
	auto Differs = [](float A, float B) { return FMath::Abs(A - B) > AOSEnvParams::Epsilon; };
	if (Differs(State.SunScale, RevSun) || Differs(State.SkyScale, RevSky)
		|| Differs(State.FogDensityScale, RevFogD) || Differs(State.FogInscatterScale, RevFogI))
	{
		RevSun = State.SunScale; RevSky = State.SkyScale;
		RevFogD = State.FogDensityScale; RevFogI = State.FogInscatterScale;
		++State.Revision;
		bScalesChanged = true;
	}

	const bool bWritten = WriteCollection();
	if (bScalesChanged || bWritten)
	{
		OnChanged.Broadcast(State);
	}
}

bool UAOSEnvironmentStateSubsystem::WriteCollection()
{
	// Storm gloom turns the Atoll lamps on: NightFactor = max(night, 0.5 * storm).
	const float Night = FMath::Max(State.NightFactor, 0.5f * State.StormAlpha);
	State.bStormLightsLamps = (0.5f * State.StormAlpha) > State.NightFactor;

	auto Differs = [](float A, float B) { return FMath::Abs(A - B) > AOSEnvParams::Epsilon; };
	const bool bNight = Differs(Night, WrittenNight);
	const bool bWet = Differs(State.Wetness, WrittenWetness);
	const bool bStorm = Differs(State.StormAlpha, WrittenStorm);
	const bool bWind = Differs(State.Wind01, WrittenWind);
	const bool bStars = Differs(State.StarVisibility, WrittenStars);
	if (!(bNight || bWet || bStorm || bWind || bStars))
	{
		return false;
	}
	if (Collection)
	{
		if (bNight) { UKismetMaterialLibrary::SetScalarParameterValue(this, Collection, AOSEnvParams::NightFactor, Night); }
		if (bWet)   { UKismetMaterialLibrary::SetScalarParameterValue(this, Collection, AOSEnvParams::Wetness, State.Wetness); }
		if (bStorm) { UKismetMaterialLibrary::SetScalarParameterValue(this, Collection, AOSEnvParams::StormAlpha, State.StormAlpha); }
		if (bWind)  { UKismetMaterialLibrary::SetScalarParameterValue(this, Collection, AOSEnvParams::Wind01, State.Wind01); }
		if (bStars) { UKismetMaterialLibrary::SetScalarParameterValue(this, Collection, AOSEnvParams::StarVisibility, State.StarVisibility); }
	}
	if (bNight) { WrittenNight = Night; }
	if (bWet)   { WrittenWetness = State.Wetness; }
	if (bStorm) { WrittenStorm = State.StormAlpha; }
	if (bWind)  { WrittenWind = State.Wind01; }
	if (bStars) { WrittenStars = State.StarVisibility; }
	return true;
}
