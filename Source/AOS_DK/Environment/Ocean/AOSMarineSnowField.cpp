#include "AOSMarineSnowField.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "ProceduralMeshComponent.h"
#include "Scalability.h"
#include "WaterBodyActor.h"
#include "WaterBodyComponent.h"

namespace AOSSnowParams
{
	static const FName BoxSize(TEXT("BoxSize"));
	static const FName Drift(TEXT("Drift"));
	static const FName CamVel(TEXT("CamVel"));
	static const FName WaterZ(TEXT("WaterZ"));
	static const FName SunDir(TEXT("SunDir"));
	static const FName SunColor(TEXT("SunColor"));
	static const FName LightRange(TEXT("LightRange"));
	static const FName HLPos[2] = { FName(TEXT("HL0Pos")), FName(TEXT("HL1Pos")) };
	static const FName HLDir[2] = { FName(TEXT("HL0Dir")), FName(TEXT("HL1Dir")) };
	static const FName HLColor[2] = { FName(TEXT("HL0Color")), FName(TEXT("HL1Color")) };
}

AAOSMarineSnowField::AAOSMarineSnowField()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork; // after the camera manager

	Mesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("SnowMesh"));
	RootComponent = Mesh;
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->SetCanEverAffectNavigation(false);
	Mesh->CastShadow = false;
	Mesh->bCastDynamicShadow = false;
	Mesh->bAffectDistanceFieldLighting = false;
	Mesh->bAffectDynamicIndirectLighting = false;
	Mesh->bAffectIndirectLightingWhileHidden = false;
	Mesh->bVisibleInRayTracing = false;
	Mesh->bVisibleInReflectionCaptures = false;
	Mesh->bVisibleInRealTimeSkyCaptures = false;
	Mesh->bReceivesDecals = false;
	Mesh->bUseAsOccluder = false;
	Mesh->SetMobility(EComponentMobility::Movable);
	Mesh->SetVisibility(false);
}

void AAOSMarineSnowField::BeginPlay()
{
	Super::BeginPlay();
	ResolveReferences();

	// Scalability: Low 40 %, Medium 70 %, High/Epic 100 %.
	const int32 Fx = Scalability::GetQualityLevels().EffectsQuality;
	const float Scale = Fx <= 0 ? 0.4f : (Fx == 1 ? 0.7f : 1.f);
	BuildMesh(FMath::Max(500, FMath::RoundToInt(ParticleCount * Scale)));

	if (SnowMaterial)
	{
		SnowMID = UMaterialInstanceDynamic::Create(SnowMaterial, this);
		Mesh->SetMaterial(0, SnowMID);
		SnowMID->SetScalarParameterValue(AOSSnowParams::BoxSize, BoxSize);
		SnowMID->SetVectorParameterValue(AOSSnowParams::Drift, FLinearColor(DriftVelocity.X, DriftVelocity.Y, DriftVelocity.Z, 0.f));
	}
}

void AAOSMarineSnowField::BuildMesh(int32 Count)
{
	FRandomStream Rng(RandomSeed);

	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UV0;
	TArray<FLinearColor> Colors;
	TArray<FProcMeshTangent> Tangents;
	Vertices.Reserve(Count * 4);
	Normals.Reserve(Count * 4);
	UV0.Reserve(Count * 4);
	Colors.Reserve(Count * 4);
	Triangles.Reserve(Count * 6);

	static const FVector2D Corners[4] = { {0.f, 0.f}, {1.f, 0.f}, {1.f, 1.f}, {0.f, 1.f} };
	for (int32 i = 0; i < Count; ++i)
	{
		// Seed position inside one Box period. All four corners share it; the material expands the quad.
		const FVector Seed(Rng.FRand() * BoxSize, Rng.FRand() * BoxSize, Rng.FRand() * BoxSize);
		// R: size, G: wobble phase, B: brightness, A: wobble amplitude (log-normal-ish size skew).
		const FLinearColor Data(FMath::Pow(Rng.FRand(), 2.2f), Rng.FRand(), Rng.FRand(), Rng.FRand());
		const int32 Base = Vertices.Num();
		for (const FVector2D& Corner : Corners)
		{
			Vertices.Add(Seed);
			Normals.Add(FVector::UpVector);
			UV0.Add(Corner);
			Colors.Add(Data);
		}
		Triangles.Append({ Base, Base + 2, Base + 1, Base, Base + 3, Base + 2 });
	}

	Mesh->ClearAllMeshSections();
	Mesh->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UV0, Colors, Tangents, /*bCreateCollision*/ false);
	Mesh->SetMeshSectionVisible(0, true);
}

void AAOSMarineSnowField::ResolveReferences()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (!WaterBody)
	{
		for (TActorIterator<AWaterBody> It(World); It; ++It)
		{
			const UWaterBodyComponent* Body = It->GetWaterBodyComponent();
			if (Body && Body->GetWaterBodyType() == EWaterBodyType::Ocean)
			{
				WaterBody = *It;
				break;
			}
		}
	}
	if (!Sun)
	{
		for (TActorIterator<ADirectionalLight> It(World); It; ++It) { Sun = *It; break; }
	}
}

float AAOSMarineSnowField::GetWaterSurfaceZ(const FVector& At) const
{
	if (!WaterBody)
	{
		return 0.f;
	}
	if (const UWaterBodyComponent* Body = WaterBody->GetWaterBodyComponent())
	{
		FVector SurfaceLocation, SurfaceNormal, Velocity;
		float WaterDepth = 0.f;
		if (Body->GetWaterSurfaceInfoAtLocation(At, SurfaceLocation, SurfaceNormal, Velocity, WaterDepth, false))
		{
			return SurfaceLocation.Z;
		}
	}
	return WaterBody->GetActorLocation().Z;
}

void AAOSMarineSnowField::UpdateHeadlights(const AActor* ViewTarget)
{
	// Two brightest visible spot lights on the view target (the Shell's headlights).
	TArray<const USpotLightComponent*, TInlineAllocator<2>> Best;
	if (ViewTarget)
	{
		TInlineComponentArray<USpotLightComponent*> Spots(ViewTarget);
		Spots.Sort([](const USpotLightComponent& A, const USpotLightComponent& B) { return A.Intensity > B.Intensity; });
		for (const USpotLightComponent* Spot : Spots)
		{
			if (Spot->IsVisible() && Spot->Intensity > KINDA_SMALL_NUMBER)
			{
				Best.Add(Spot);
				if (Best.Num() == 2) { break; }
			}
		}
	}

	float Range = 1.f;
	for (int32 i = 0; i < 2; ++i)
	{
		if (Best.IsValidIndex(i))
		{
			const USpotLightComponent* Spot = Best[i];
			const FVector P = Spot->GetComponentLocation();
			const FVector D = Spot->GetForwardVector();
			const float CosInner = FMath::Cos(FMath::DegreesToRadians(FMath::Min(Spot->InnerConeAngle, Spot->OuterConeAngle - 0.5f)));
			const float CosOuter = FMath::Cos(FMath::DegreesToRadians(Spot->OuterConeAngle));
			const FLinearColor C = Spot->GetLightColor() * (Spot->Intensity * HeadlightScale);
			SnowMID->SetVectorParameterValue(AOSSnowParams::HLPos[i], FLinearColor(P.X, P.Y, P.Z, CosInner));
			SnowMID->SetVectorParameterValue(AOSSnowParams::HLDir[i], FLinearColor(D.X, D.Y, D.Z, CosOuter));
			SnowMID->SetVectorParameterValue(AOSSnowParams::HLColor[i], C);
			Range = FMath::Max(Range, Spot->AttenuationRadius);
		}
		else
		{
			SnowMID->SetVectorParameterValue(AOSSnowParams::HLColor[i], FLinearColor::Black);
		}
	}
	SnowMID->SetScalarParameterValue(AOSSnowParams::LightRange, Range);
}

void AAOSMarineSnowField::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	const APlayerCameraManager* Camera = UGameplayStatics::GetPlayerCameraManager(this, 0);
	if (!Camera || !SnowMID)
	{
		return;
	}
	const FVector Cam = Camera->GetCameraLocation();

	// Only below the waterline (wave-aware); above it the whole field is hidden (zero GPU cost).
	const float SurfaceZ = GetWaterSurfaceZ(Cam);
	const bool bUnderwater = Cam.Z < SurfaceZ - 20.f;
	if (bUnderwater != bVisibleUnderwater)
	{
		bVisibleUnderwater = bUnderwater;
		Mesh->SetVisibility(bUnderwater);
		bHasPrevCamera = false;
	}
	if (!bUnderwater)
	{
		return;
	}

	// Keep the bounds around the camera (particles themselves are world-fixed in the material).
	Mesh->SetWorldLocation(Cam - FVector(BoxSize * 0.5f), false, nullptr, ETeleportType::TeleportPhysics);

	// Camera velocity relative to the water -> motion streaks. Teleports (> 30 m/s) are ignored.
	if (bHasPrevCamera && DeltaSeconds > KINDA_SMALL_NUMBER)
	{
		FVector Velocity = (Cam - PrevCameraLocation) / DeltaSeconds;
		if (Velocity.SizeSquared() > FMath::Square(3000.f))
		{
			Velocity = FVector::ZeroVector;
		}
		SmoothedCameraVelocity = FMath::VInterpTo(SmoothedCameraVelocity, Velocity, DeltaSeconds, VelocitySmoothing);
	}
	PrevCameraLocation = Cam;
	bHasPrevCamera = true;

	const FVector RelVel = SmoothedCameraVelocity - DriftVelocity;
	SnowMID->SetVectorParameterValue(AOSSnowParams::CamVel, FLinearColor(RelVel.X, RelVel.Y, RelVel.Z, 0.f));
	SnowMID->SetScalarParameterValue(AOSSnowParams::WaterZ, SurfaceZ);

	if (const UDirectionalLightComponent* SunLight = Sun ? Cast<UDirectionalLightComponent>(Sun->GetLightComponent()) : nullptr)
	{
		const FVector D = SunLight->GetForwardVector(); // direction the light travels
		const float I = SunLight->IsVisible() ? SunLight->Intensity * SunScale : 0.f;
		SnowMID->SetVectorParameterValue(AOSSnowParams::SunDir, FLinearColor(D.X, D.Y, D.Z, 0.f));
		SnowMID->SetVectorParameterValue(AOSSnowParams::SunColor, SunLight->GetLightColor() * I);
	}

	UpdateHeadlights(Camera->GetViewTarget());
}
