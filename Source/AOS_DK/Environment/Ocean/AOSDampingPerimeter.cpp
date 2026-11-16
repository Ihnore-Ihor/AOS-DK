#include "AOS_DK/Environment/Ocean/AOSDampingPerimeter.h"

#include "AOS_DK/Environment/Ocean/AOSAtollSettings.h"
#include "Camera/PlayerCameraManager.h"
#include "EngineUtils.h"
#include "Components/SceneComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialParameterCollection.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "WaterBodyActor.h"
#include "WaterBodyComponent.h"
#include "WaterWaves.h"

DEFINE_LOG_CATEGORY_STATIC(LogAOSAtoll, Log, All);

namespace AOSAtollParams
{
	static const FName AtollCenter(TEXT("AtollCenter"));
	static const FName Radii(TEXT("Radii"));
	static const FName GateFoam(TEXT("GateFoam"));
	static const FName PlayerPos(TEXT("PlayerPos"));
	static const FName CameraAzimuth(TEXT("User.CameraAzimuth"));
	static constexpr int32 NumGates = 3;

	static FName GateName(int32 Index)
	{
		return FName(*FString::Printf(TEXT("Gate%d"), Index));
	}

	static FLinearColor CenterValue(const UAOSAtollSettings& S, float WaterZ)
	{
		return FLinearColor(float(S.Center.X), float(S.Center.Y), WaterZ, 0.f);
	}

	static FLinearColor RadiiValue(const UAOSAtollSettings& S)
	{
		return FLinearColor(S.RCalm, S.RFull, S.RingFoamR, S.RingFoamWidth);
	}

	static FLinearColor GateFoamValue(const UAOSAtollSettings& S)
	{
		return FLinearColor(S.GateCurtainR, S.GateFoamWidth, 0.f, 0.f);
	}

	/** (cos, sin, half angle, strength); strength 0 disables an unused slot. */
	static FLinearColor GateValue(const UAOSAtollSettings& S, int32 Index)
	{
		if (!S.GateAzimuthsDeg.IsValidIndex(Index))
		{
			return FLinearColor(1.f, 0.f, S.GateHalfAngleRad, 0.f);
		}
		const float Rad = FMath::DegreesToRadians(S.GateAzimuthsDeg[Index]);
		return FLinearColor(FMath::Cos(Rad), FMath::Sin(Rad), S.GateHalfAngleRad, S.GateFoamStrength);
	}
}

AAOSDampingPerimeter::AAOSDampingPerimeter()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.1f; // 10 Hz: camera azimuth / player position
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	RootComponent = Root;

	RingCurtain = CreateDefaultSubobject<UNiagaraComponent>(TEXT("RingCurtain"));
	RingCurtain->SetupAttachment(Root);

	RingNearCurtain = CreateDefaultSubobject<UNiagaraComponent>(TEXT("RingNearCurtain"));
	RingNearCurtain->SetupAttachment(Root);
	RingNearCurtain->bAutoActivate = false;

	for (int32 i = 0; i < AOSAtollParams::NumGates; ++i)
	{
		UNiagaraComponent* Gate = CreateDefaultSubobject<UNiagaraComponent>(*FString::Printf(TEXT("GateCurtain%d"), i));
		Gate->SetupAttachment(Root);
		GateCurtains.Add(Gate);
	}
}

void AAOSDampingPerimeter::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	LayoutCurtains();
	PushMaskParameters();
#if WITH_EDITOR
	ValidateCollectionDefaults();
#endif
}

void AAOSDampingPerimeter::BeginPlay()
{
	Super::BeginPlay();
	LayoutCurtains();
	PushMaskParameters();
	UpdateViewDependent();
}

void AAOSDampingPerimeter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UpdateViewDependent();
}

void AAOSDampingPerimeter::PushMaskParameters()
{
	if (!AtollCollection || !GetWorld())
	{
		return;
	}
	const UAOSAtollSettings& S = *UAOSAtollSettings::Get();
	UKismetMaterialLibrary::SetVectorParameterValue(this, AtollCollection, AOSAtollParams::AtollCenter,
		AOSAtollParams::CenterValue(S, float(GetActorLocation().Z)));
	UKismetMaterialLibrary::SetVectorParameterValue(this, AtollCollection, AOSAtollParams::Radii, AOSAtollParams::RadiiValue(S));
	UKismetMaterialLibrary::SetVectorParameterValue(this, AtollCollection, AOSAtollParams::GateFoam, AOSAtollParams::GateFoamValue(S));
	for (int32 i = 0; i < AOSAtollParams::NumGates; ++i)
	{
		UKismetMaterialLibrary::SetVectorParameterValue(this, AtollCollection, AOSAtollParams::GateName(i), AOSAtollParams::GateValue(S, i));
	}
}

void AAOSDampingPerimeter::LayoutCurtains()
{
	const UAOSAtollSettings& S = *UAOSAtollSettings::Get();
	const double WaterZ = GetActorLocation().Z;
	const FVector Center(S.Center.X, S.Center.Y, WaterZ);

	if (RingCurtain)
	{
		RingCurtain->SetAsset(RingCurtainSystem);
		RingCurtain->SetWorldLocationAndRotation(Center + FVector(0.0, 0.0, RingZOffset), FRotator::ZeroRotator);
	}
	if (RingNearCurtain)
	{
		RingNearCurtain->SetAsset(RingNearSystem);
	}
	for (int32 i = 0; i < GateCurtains.Num(); ++i)
	{
		UNiagaraComponent* Gate = GateCurtains[i];
		if (!Gate)
		{
			continue;
		}
		const bool bUsed = S.GateAzimuthsDeg.IsValidIndex(i);
		Gate->SetAsset(bUsed ? GateCurtainSystem.Get() : nullptr);
		Gate->SetVisibility(bUsed);
		Gate->SetCullDistance(GateCullDistance);
		if (bUsed)
		{
			const float Azimuth = S.GateAzimuthsDeg[i];
			const float Rad = FMath::DegreesToRadians(Azimuth);
			const FVector Radial(FMath::Cos(Rad), FMath::Sin(Rad), 0.0);
			Gate->SetWorldLocationAndRotation(Center + Radial * S.GateCurtainR, FRotator(0.0, Azimuth, 0.0));
		}
	}
}

void AAOSDampingPerimeter::UpdateViewDependent()
{
	const APlayerCameraManager* Camera = UGameplayStatics::GetPlayerCameraManager(this, 0);
	if (!Camera)
	{
		return;
	}
	const UAOSAtollSettings& S = *UAOSAtollSettings::Get();
	const FVector Cam = Camera->GetCameraLocation();
	const FVector2D Rel(Cam.X - S.Center.X, Cam.Y - S.Center.Y);
	const double Dist = Rel.Size();
	const float AzimuthRad = float(FMath::Atan2(Rel.Y, Rel.X));

	if (AtollCollection)
	{
		UKismetMaterialLibrary::SetVectorParameterValue(this, AtollCollection, AOSAtollParams::PlayerPos,
			FLinearColor(float(Cam.X), float(Cam.Y), float(Cam.Z), 0.f));
	}
	if (RingCurtain)
	{
		RingCurtain->SetVariableFloat(AOSAtollParams::CameraAzimuth, FMath::RadiansToDegrees(AzimuthRad));
	}
	if (RingNearCurtain && RingNearSystem)
	{
		// Underwater bubble wall of the BC-R line, only where the camera can see it.
		const bool bNear = FMath::Abs(Dist - S.RingFoamR) <= RingNearActivationDistance;
		if (bNear)
		{
			const FVector Radial(FMath::Cos(AzimuthRad), FMath::Sin(AzimuthRad), 0.0);
			const FVector Center(S.Center.X, S.Center.Y, GetActorLocation().Z);
			RingNearCurtain->SetWorldLocationAndRotation(Center + Radial * S.RingFoamR,
				FRotator(0.0, FMath::RadiansToDegrees(AzimuthRad), 0.0));
			if (!RingNearCurtain->IsActive())
			{
				RingNearCurtain->Activate(true);
			}
		}
		else if (RingNearCurtain->IsActive())
		{
			RingNearCurtain->Deactivate();
		}
	}
}

FVector AAOSDampingPerimeter::ProbeWaterWaves(const FVector& At, float Duration, int32 Steps) const
{
	static constexpr float DeepWater = 100000.f; // open ocean: no depth attenuation from the plugin
	for (TActorIterator<AWaterBody> It(GetWorld()); It; ++It)
	{
		const UWaterBodyComponent* Body = It->GetWaterBodyComponent();
		const UWaterWavesBase* Waves = Body ? Body->GetWaterWaves() : nullptr;
		if (!Waves || !Waves->GetWaterWaves())
		{
			continue;
		}
		// Same product the plugin applies in UWaterBodyComponent::GetWaveInfoAtPosition, with an explicit time.
		const float Attenuation = Waves->GetWaveAttenuationFactor(At, DeepWater, 2048.f);
		float MinHeight = TNumericLimits<float>::Max();
		float MaxHeight = TNumericLimits<float>::Lowest();
		const int32 Count = FMath::Max(Steps, 1);
		for (int32 i = 0; i <= Count; ++i)
		{
			FVector Normal;
			const float Height = Waves->GetWaveHeightAtPosition(At, DeepWater, Duration * float(i) / float(Count), Normal) * Attenuation;
			MinHeight = FMath::Min(MinHeight, Height);
			MaxHeight = FMath::Max(MaxHeight, Height);
		}
		return FVector(MinHeight, MaxHeight, Attenuation);
	}
	return FVector(0.0, 0.0, -1.0);
}

float AAOSDampingPerimeter::QueryWaterSurfaceZ(const FVector& At) const
{
	for (TActorIterator<AWaterBody> It(GetWorld()); It; ++It)
	{
		if (const UWaterBodyComponent* Body = It->GetWaterBodyComponent())
		{
			const TValueOrError<FWaterBodyQueryResult, EWaterBodyQueryError> Query = Body->TryQueryWaterInfoClosestToWorldLocation(
				At, EWaterBodyQueryFlags::ComputeLocation | EWaterBodyQueryFlags::IncludeWaves);
			if (Query.HasValue())
			{
				return float(Query.GetValue().GetWaterSurfaceLocation().Z);
			}
		}
	}
	return float(GetActorLocation().Z);
}

#if WITH_EDITOR
void AAOSDampingPerimeter::ValidateCollectionDefaults() const
{
	if (!AtollCollection || IsTemplate())
	{
		return;
	}
	const UAOSAtollSettings& S = *UAOSAtollSettings::Get();
	TArray<TPair<FName, FLinearColor>> Expected;
	Expected.Emplace(AOSAtollParams::AtollCenter, AOSAtollParams::CenterValue(S, float(GetActorLocation().Z)));
	Expected.Emplace(AOSAtollParams::Radii, AOSAtollParams::RadiiValue(S));
	Expected.Emplace(AOSAtollParams::GateFoam, AOSAtollParams::GateFoamValue(S));
	for (int32 i = 0; i < AOSAtollParams::NumGates; ++i)
	{
		Expected.Emplace(AOSAtollParams::GateName(i), AOSAtollParams::GateValue(S, i));
	}
	for (const TPair<FName, FLinearColor>& Pair : Expected)
	{
		const FCollectionVectorParameter* Param = AtollCollection->GetVectorParameterByName(Pair.Key);
		if (!Param)
		{
			UE_LOG(LogAOSAtoll, Warning, TEXT("%s: parameter %s is missing in %s."), *GetName(), *Pair.Key.ToString(), *AtollCollection->GetName());
			continue;
		}
		const FLinearColor Delta = Param->DefaultValue - Pair.Value;
		// Radii / centre are in cm (tolerance 1 cm); gate vectors are unit-scale.
		const bool bUnitScale = Pair.Key.ToString().StartsWith(TEXT("Gate")) && Pair.Key != AOSAtollParams::GateFoam;
		const float Tolerance = bUnitScale ? 1e-3f : 1.f;
		if (FMath::Max(FMath::Max(FMath::Abs(Delta.R), FMath::Abs(Delta.G)), FMath::Max(FMath::Abs(Delta.B), FMath::Abs(Delta.A))) > Tolerance)
		{
			UE_LOG(LogAOSAtoll, Warning, TEXT("%s: %s default %s in %s differs from UAOSAtollSettings %s (editor preview of the mask is off)."),
				*GetName(), *Pair.Key.ToString(), *Param->DefaultValue.ToString(), *AtollCollection->GetName(), *Pair.Value.ToString());
		}
	}
}
#endif
