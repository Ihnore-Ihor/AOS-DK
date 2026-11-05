#include "AOS_EnemyDaemon.h"

#include "AOS_DK/Core/UI/AOSDraculaPalette.h"
#include "AOS_DK/Enemies/UI/EnemyHealthBarWidget.h"
#include "AOS_DK/Enemies/Spawning/AOS_EnemySpawner.h"
#include "AOS_DK/Submarine/Energy/ShellEnergyComponent.h"
#include "AOS_DK/Submarine/ShellPawn.h"

#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SphereComponent.h"
#include "Components/SplineComponent.h"
#include "Components/WidgetComponent.h"
#include "Engine/DamageEvents.h"
#include "Engine/World.h"
#include "GameFramework/DamageType.h"
#include "GameFramework/PlayerController.h"
#include "Camera/PlayerCameraManager.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "ProceduralMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	constexpr int32 NumTendrils = 4;

	float WrapDistance(float Distance, float Length)
	{
		if (Length <= KINDA_SMALL_NUMBER)
		{
			return 0.f;
		}
		const float Wrapped = FMath::Fmod(Distance, Length);
		return Wrapped < 0.f ? Wrapped + Length : Wrapped;
	}
}

AAOS_EnemyDaemon::AAOS_EnemyDaemon()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;

	Collision = CreateDefaultSubobject<USphereComponent>(TEXT("Collision"));
	RootComponent = Collision;
	Collision->InitSphereRadius(62.f);
	Collision->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Collision->SetCollisionObjectType(ECC_WorldDynamic);
	Collision->SetCollisionResponseToAllChannels(ECR_Ignore);
	Collision->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
	Collision->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);   // micro-torpedo sweeps + other daemons
	Collision->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);     // aim trace / crosshair lock
	Collision->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
	Collision->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Overlap);  // never pushes the Shell
	Collision->SetGenerateOverlapEvents(false);
	Collision->SetCanEverAffectNavigation(false);

	// Hit volumes sized to what the player sees (set from CoreRadius / TendrilLength in BuildModel).
	auto SetupHitVolume = [](UShapeComponent* Shape)
	{
		Shape->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
		Shape->SetCollisionObjectType(ECC_WorldDynamic);
		Shape->SetCollisionResponseToAllChannels(ECR_Ignore);
		Shape->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block); // micro-torpedo sweeps
		Shape->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);   // aim trace / crosshair lock
		Shape->SetGenerateOverlapEvents(false);
		Shape->SetCanEverAffectNavigation(false);
	};
	HitVolume = CreateDefaultSubobject<USphereComponent>(TEXT("HitVolume"));
	HitVolume->SetupAttachment(Collision);
	HitVolume->InitSphereRadius(105.f);
	SetupHitVolume(HitVolume);

	TailHitVolume = CreateDefaultSubobject<UCapsuleComponent>(TEXT("TailHitVolume"));
	TailHitVolume->SetupAttachment(Collision);
	TailHitVolume->SetRelativeRotation(FRotator(90.f, 0.f, 0.f)); // capsule axis (Z) -> -X tail
	TailHitVolume->InitCapsuleSize(40.f, 160.f);
	SetupHitVolume(TailHitVolume);

	// Torpedo proximity fuse reacts to this tag.
	Tags.AddUnique(TEXT("AOS.FuseTarget"));

	VisualRoot = CreateDefaultSubobject<USceneComponent>(TEXT("VisualRoot"));
	VisualRoot->SetupAttachment(Collision);

	auto MakeMesh = [this](const TCHAR* Name) -> UProceduralMeshComponent*
	{
		UProceduralMeshComponent* Mesh = CreateDefaultSubobject<UProceduralMeshComponent>(Name);
		Mesh->SetupAttachment(VisualRoot);
		Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Mesh->SetCanEverAffectNavigation(false);
		Mesh->bUseAsyncCooking = false;
		return Mesh;
	};
	CoreMesh = MakeMesh(TEXT("CoreMesh"));
	EyeMesh = MakeMesh(TEXT("EyeMesh"));
	HaloOuter = MakeMesh(TEXT("HaloOuter"));
	HaloInner = MakeMesh(TEXT("HaloInner"));
	for (int32 i = 0; i < NumTendrils; ++i)
	{
		UProceduralMeshComponent* Tendril = MakeMesh(*FString::Printf(TEXT("Tendril%d"), i));
		Tendril->SetRelativeLocation(FVector(-22.f, 0.f, 0.f));
		Tendril->SetRelativeRotation(FRotator(0.f, 0.f, 45.f + 90.f * float(i)));
		TendrilMeshes.Add(Tendril);
	}

	CoreLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("CoreLight"));
	CoreLight->SetupAttachment(Collision);
	CoreLight->SetIntensityUnits(ELightUnits::Candelas);
	CoreLight->SetIntensity(30.f);
	CoreLight->SetAttenuationRadius(700.f);
	CoreLight->SetCastShadows(false);

	ChargeFX = CreateDefaultSubobject<UNiagaraComponent>(TEXT("ChargeFX"));
	ChargeFX->SetupAttachment(VisualRoot);
	ChargeFX->SetAutoActivate(false);

	HealthBar = CreateDefaultSubobject<UWidgetComponent>(TEXT("HealthBar"));
	HealthBar->SetupAttachment(Collision);
	HealthBar->SetRelativeLocation(FVector(0.f, 0.f, 125.f));
	HealthBar->SetWidgetSpace(EWidgetSpace::Screen);
	HealthBar->SetDrawSize(FVector2D(180.0, 46.0));
	HealthBar->SetPivot(FVector2D(0.5, 1.0));
	HealthBar->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	HealthBar->SetGenerateOverlapEvents(false);
	HealthBar->SetCastShadow(false);
	HealthBar->SetWidgetClass(UEnemyHealthBarWidget::StaticClass());
	HealthBarWidgetClass = UEnemyHealthBarWidget::StaticClass();

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> HullFinder(TEXT("/Game/AOS_DK_Game/Enemies/Daemon/Materials/M_EnemyDaemon_Hull.M_EnemyDaemon_Hull"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> GlowFinder(TEXT("/Game/AOS_DK_Game/Enemies/Daemon/Materials/M_EnemyDaemon_Glow.M_EnemyDaemon_Glow"));
	HullMaterial = HullFinder.Succeeded() ? HullFinder.Object : nullptr;
	GlowMaterial = GlowFinder.Succeeded() ? GlowFinder.Object : nullptr;

	DamageTypeClass = UDamageType::StaticClass();

	IdleColor   = AOSDracula::Purple();
	AlertColor  = AOSDracula::Orange();
	ChargeColor = AOSDracula::Pink();
	StrikeColor = AOSDracula::Red();
	DisplayColor = IdleColor;
}

FString AAOS_EnemyDaemon::GetProcessName() const
{
	return FString::Printf(TEXT("daemon[%d]"), ProcessId);
}

void AAOS_EnemyDaemon::InitializeFromSpawner(AAOS_EnemySpawner* InSpawner, USplineComponent* InRoute, float InStartDistance, EDaemonAttackMode InMode, int32 InSerial)
{
	OwnerSpawner = InSpawner;
	ActiveRoute = InRoute;
	RouteDistance = InStartDistance;
	bHasSpawnerStart = InRoute != nullptr;
	AttackMode = InMode;
	ProcessId = 4100 + InSerial * 7 + (InMode == EDaemonAttackMode::Pulse ? 3 : 0);
}

// ------------------------------------------------------------------------------------------- model
void AAOS_EnemyDaemon::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	BuildModel();
}

void AAOS_EnemyDaemon::BuildModel()
{
	const uint32 Seed = 1337u;
	const float R = CoreRadius;
	const float ModelScale = CoreRadius / 36.f;
	Collision->SetSphereRadius(R * 1.75f);
	CoreLight->SetAttenuationRadius(700.f * ModelScale);

	// Hit volumes follow the silhouette: outer halo (1.9 R + ring thickness) and the tendril bundle.
	HitVolume->SetSphereRadius(R * 1.9f + 8.f);
	const float TailRadius = FMath::Max(30.f, 0.8f * R);
	const float TailStart = 22.f * ModelScale;
	TailHitVolume->SetCapsuleSize(TailRadius, TendrilLength * 0.5f + TailRadius);
	TailHitVolume->SetRelativeLocation(FVector(-(TailStart + TendrilLength * 0.5f), 0.f, 0.f));

	FDaemonMeshData Plates, InnerCore;
	AOSDaemonGeometry::BuildPlatedCore(Plates, R, 1, 0.86f, 34.f, Seed);
	AOSDaemonGeometry::BuildFacetedSphere(InnerCore, R * 0.93f, 1);
	CoreMesh->ClearAllMeshSections();
	Plates.CreateSection(CoreMesh, 0);
	InnerCore.CreateSection(CoreMesh, 1);
	CoreMesh->SetMaterial(0, HullMaterial);
	CoreMesh->SetMaterial(1, GlowMaterial);

	FDaemonMeshData Lens;
	AOSDaemonGeometry::BuildLens(Lens, R * 0.97f, 30.f, 3, 18);
	EyeMesh->ClearAllMeshSections();
	Lens.CreateSection(EyeMesh, 0);
	EyeMesh->SetMaterial(0, GlowMaterial);

	FDaemonMeshData HullA, GlowA, HullB, GlowB;
	AOSDaemonGeometry::BuildSegmentedRing(HullA, GlowA, R * 1.9f, 5.f, 7.f, 6, 14.f, 6);
	AOSDaemonGeometry::BuildSegmentedRing(HullB, GlowB, R * 1.6f, 4.f, 5.f, 4, 22.f, 7);
	HaloOuter->ClearAllMeshSections();
	HullA.CreateSection(HaloOuter, 0);
	GlowA.CreateSection(HaloOuter, 1);
	HaloOuter->SetMaterial(0, HullMaterial);
	HaloOuter->SetMaterial(1, GlowMaterial);
	HaloInner->ClearAllMeshSections();
	HullB.CreateSection(HaloInner, 0);
	GlowB.CreateSection(HaloInner, 1);
	HaloInner->SetMaterial(0, HullMaterial);
	HaloInner->SetMaterial(1, GlowMaterial);

	TendrilData.SetNum(TendrilMeshes.Num());
	for (int32 i = 0; i < TendrilMeshes.Num(); ++i)
	{
		SpineScratch.Reset();
		RadiiScratch.Reset();
		for (int32 k = 0; k <= TendrilSegments; ++k)
		{
			const float S = float(k) / float(TendrilSegments);
			SpineScratch.Add(FVector(-S * TendrilLength, 0.f, S * 14.f * ModelScale));
			RadiiScratch.Add(FMath::Lerp(5.5f, 0.9f, S) * ModelScale);
		}
		TendrilMeshes[i]->SetRelativeLocation(FVector(-22.f * ModelScale, 0.f, 0.f));
		AOSDaemonGeometry::BuildTube(TendrilData[i], SpineScratch, RadiiScratch, TendrilSides);
		TendrilMeshes[i]->ClearAllMeshSections();
		TendrilData[i].CreateSection(TendrilMeshes[i], 0);
		TendrilMeshes[i]->SetMaterial(0, GlowMaterial);
	}

	TArray<UProceduralMeshComponent*> Meshes = { CoreMesh.Get(), EyeMesh.Get(), HaloOuter.Get(), HaloInner.Get() };
	for (UProceduralMeshComponent* Tendril : TendrilMeshes)
	{
		Meshes.Add(Tendril);
	}
	for (UProceduralMeshComponent* Mesh : Meshes)
	{
		Mesh->SetCastShadow(bCastShadows);
	}
	HaloInner->SetRelativeRotation(FRotator(62.f, 0.f, 0.f));
	LastCPDGlow = -1.f; // force CPD push
	PushCPD(IdleColor, IdleGlow, 0.f);
}

void AAOS_EnemyDaemon::PushCPD(const FLinearColor& Color, float Glow, float Flash)
{
	const FVector4 C(Color.R, Color.G, Color.B, 1.0);
	const bool bColor = !C.Equals(LastCPDColor, 0.002);
	const bool bGlow = FMath::Abs(Glow - LastCPDGlow) > 0.05f;
	const bool bFlash = FMath::Abs(Flash - LastCPDFlash) > 0.01f;
	if (!bColor && !bGlow && !bFlash)
	{
		return;
	}
	TArray<UProceduralMeshComponent*> Meshes = { CoreMesh.Get(), EyeMesh.Get(), HaloOuter.Get(), HaloInner.Get() };
	for (UProceduralMeshComponent* Tendril : TendrilMeshes)
	{
		Meshes.Add(Tendril);
	}
	for (UProceduralMeshComponent* Mesh : Meshes)
	{
		if (!Mesh)
		{
			continue;
		}
		const float MeshGlow = Mesh == EyeMesh.Get() ? Glow * 1.6f : Glow;
		if (bColor) { Mesh->SetCustomPrimitiveDataVector4(DaemonCPD::GlowColor, C); }
		if (bGlow)  { Mesh->SetCustomPrimitiveDataFloat(DaemonCPD::GlowIntensity, MeshGlow); }
		if (bFlash) { Mesh->SetCustomPrimitiveDataFloat(DaemonCPD::HitFlash, Flash); }
	}
	LastCPDColor = C;
	LastCPDGlow = Glow;
	LastCPDFlash = Flash;
}

// ------------------------------------------------------------------------------------------ lifecycle
void AAOS_EnemyDaemon::BeginPlay()
{
	Super::BeginPlay();
	Health = MaxHealth;
	if (ProcessId == 0)
	{
		ProcessId = 4000 + int32(GetUniqueID() % 900u);
	}
	Phase = float(ProcessId % 97) * 0.37f;
	OrbitSign = (ProcessId % 2 == 0) ? 1.f : -1.f;
	DisplayColor = IdleColor;
	DisplayGlow = IdleGlow;

	if (HealthBarWidgetClass)
	{
		HealthBar->SetWidgetClass(HealthBarWidgetClass);
	}
	HealthBar->SetWidgetSpace(bWorldSpaceHealthBar ? EWidgetSpace::World : EWidgetSpace::Screen);
	HealthBar->SetRelativeLocation(FVector(0.f, 0.f, HealthBarHeight));
	HealthBar->InitWidget();
	if (UEnemyHealthBarWidget* Bar = Cast<UEnemyHealthBarWidget>(HealthBar->GetUserWidgetObject()))
	{
		Bar->SetHealthFraction(1.f, true);
		Bar->SetLabel(GetProcessName());
	}

	BuildModel();
	ResolvePatrolRoute();
	SetState(EDaemonState::Patrol);
}

void AAOS_EnemyDaemon::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (State != EDaemonState::Dying)
	{
		OnDaemonDestroyed.Broadcast(this);
	}
	Super::EndPlay(EndPlayReason);
}

USplineComponent* AAOS_EnemyDaemon::BuildRuntimeRoute(const TArray<FVector>& WorldPoints)
{
	USplineComponent* Spline = NewObject<USplineComponent>(this, TEXT("RuntimePatrolRoute"), RF_Transient);
	Spline->SetUsingAbsoluteLocation(true);
	Spline->SetUsingAbsoluteRotation(true);
	Spline->SetUsingAbsoluteScale(true);
	Spline->SetMobility(EComponentMobility::Movable);
	Spline->RegisterComponent();
	Spline->SetWorldTransform(FTransform::Identity);
	Spline->SetSplinePoints(WorldPoints, ESplineCoordinateSpace::World, false);
	Spline->SetClosedLoop(true, true);
	return Spline;
}

void AAOS_EnemyDaemon::ResolvePatrolRoute()
{
	if (!ActiveRoute && PatrolRouteActor)
	{
		ActiveRoute = PatrolRouteActor->FindComponentByClass<USplineComponent>();
	}
	if (!ActiveRoute)
	{
		const FTransform Start = GetActorTransform();
		TArray<FVector> Points;
		if (PatrolPoints.Num() >= 2)
		{
			Points.Add(Start.GetLocation());
			for (const FVector& Local : PatrolPoints)
			{
				Points.Add(Start.TransformPosition(Local));
			}
		}
		else
		{
			// Deterministic default loop: circle with a gentle vertical wave.
			constexpr int32 Count = 8;
			for (int32 i = 0; i < Count; ++i)
			{
				const float A = 2.f * PI * float(i) / float(Count);
				Points.Add(Start.GetLocation() + FVector(FMath::Cos(A) * DefaultPatrolRadius, FMath::Sin(A) * DefaultPatrolRadius, FMath::Sin(2.f * A) * 150.f));
			}
		}
		ActiveRoute = BuildRuntimeRoute(Points);
	}
	if (ActiveRoute && !bHasSpawnerStart)
	{
		RouteDistance = ActiveRoute->GetDistanceAlongSplineAtLocation(GetActorLocation(), ESplineCoordinateSpace::World);
	}
}

// ---------------------------------------------------------------------------------------------- FSM
void AAOS_EnemyDaemon::SetState(EDaemonState NewState)
{
	const EDaemonState OldState = State;
	State = NewState;
	StateTime = 0.f;

	if (NewState == EDaemonState::Telegraph)
	{
		ChargeFX->Activate(true);
	}
	else if (OldState == EDaemonState::Telegraph)
	{
		ChargeFX->Deactivate();
	}
	if (NewState == EDaemonState::Return && ActiveRoute)
	{
		ReturnDistance = ActiveRoute->GetDistanceAlongSplineAtLocation(GetActorLocation(), ESplineCoordinateSpace::World);
	}
	if (NewState == EDaemonState::Patrol)
	{
		bAnnouncedIntrusion = false;
	}
	if (OldState != NewState)
	{
		OnStateChanged.Broadcast(NewState, OldState);
		BP_OnStateChanged(NewState, OldState);
	}
}

AShellPawn* AAOS_EnemyDaemon::FindCandidateShell() const
{
	// Only a piloted Shell is a target (the walking Admin on the surface is ignored).
	AShellPawn* Shell = Cast<AShellPawn>(UGameplayStatics::GetPlayerPawn(this, 0));
	if (!Shell || Shell->IsSystemsHalted())
	{
		return nullptr;
	}
	const UShellEnergyComponent* Energy = Shell->GetEnergy();
	return (Energy && !Energy->IsDepleted()) ? Shell : nullptr;
}

bool AAOS_EnemyDaemon::HasLineOfSight(const AShellPawn* Shell) const
{
	if (!bRequireLineOfSight || !Shell)
	{
		return Shell != nullptr;
	}
	FCollisionQueryParams Params(SCENE_QUERY_STAT(DaemonSight), false, this);
	Params.AddIgnoredActor(Shell);
	FHitResult Hit;
	return !GetWorld()->LineTraceSingleByChannel(Hit, GetActorLocation(), Shell->GetActorLocation(), ECC_Visibility, Params)
		|| Cast<AAOS_EnemyDaemon>(Hit.GetActor()) != nullptr;
}

float AAOS_EnemyDaemon::DistanceToHull(const AShellPawn* Shell, FVector* OutClosest) const
{
	if (!Shell)
	{
		return TNumericLimits<float>::Max();
	}
	FVector Closest = Shell->GetActorLocation();
	float Distance = -1.f;
	if (const UPrimitiveComponent* Body = Cast<UPrimitiveComponent>(Shell->GetRootComponent()))
	{
		Distance = Body->GetClosestPointOnCollision(GetActorLocation(), Closest);
	}
	if (Distance < 0.f)
	{
		Closest = Shell->GetActorLocation();
		Distance = FMath::Max(0.f, float(FVector::Dist(GetActorLocation(), Closest)) - 300.f);
	}
	if (OutClosest)
	{
		*OutClosest = Closest;
	}
	return FMath::Max(0.f, Distance - Collision->GetScaledSphereRadius());
}

float AAOS_EnemyDaemon::DistanceFromRoute() const
{
	if (!ActiveRoute)
	{
		return 0.f;
	}
	const FVector OnRoute = ActiveRoute->FindLocationClosestToWorldLocation(GetActorLocation(), ESplineCoordinateSpace::World);
	return float(FVector::Dist(OnRoute, GetActorLocation()));
}

void AAOS_EnemyDaemon::EvaluateTarget()
{
	AShellPawn* Candidate = FindCandidateShell();
	const float Dist = Candidate ? float(FVector::Dist(Candidate->GetActorLocation(), GetActorLocation())) : TNumericLimits<float>::Max();

	switch (State)
	{
	case EDaemonState::Patrol:
	case EDaemonState::Return:
		if (Candidate && Dist <= AggroRadius && HasLineOfSight(Candidate))
		{
			Target = Candidate;
			SetState(EDaemonState::Engage);
			if (!bAnnouncedIntrusion)
			{
				bAnnouncedIntrusion = true;
				LogToShell(TEXT("intrusion detected - engaging shell"), 3);
			}
		}
		break;

	case EDaemonState::Engage:
	case EDaemonState::Telegraph:
	case EDaemonState::Recover:
		if (!Candidate || Candidate != Target.Get() || Dist > DisengageRadius || DistanceFromRoute() > LeashRadius)
		{
			Target.Reset();
			SetState(EDaemonState::Return);
		}
		break;

	default:
		break;
	}
}

void AAOS_EnemyDaemon::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const float Dt = FMath::Min(DeltaSeconds, 0.05f);
	if (Dt <= 0.f)
	{
		return;
	}
	if (State == EDaemonState::Dying)
	{
		TickDying(Dt);
		return;
	}

	StateTime += Dt;
	CooldownRemaining = FMath::Max(0.f, CooldownRemaining - Dt);
	DetectTimer -= Dt;
	if (DetectTimer <= 0.f && State != EDaemonState::Strike)
	{
		DetectTimer = 0.2f;
		EvaluateTarget();
	}

	PrevVelocity = Velocity;
	switch (State)
	{
	case EDaemonState::Patrol:    TickPatrol(Dt); break;
	case EDaemonState::Engage:    TickEngage(Dt); break;
	case EDaemonState::Telegraph: TickTelegraph(Dt); break;
	case EDaemonState::Strike:    TickStrike(Dt); break;
	case EDaemonState::Recover:   TickRecover(Dt); break;
	case EDaemonState::Return:    TickReturn(Dt); break;
	default: break;
	}

	UpdateVisuals(Dt);
	UpdateHealthBar(Dt);
}

// ------------------------------------------------------------------------------------------ motion
float AAOS_EnemyDaemon::GetSurfaceCeilingZ() const
{
	float SurfaceZ = 0.f;
	if (const AShellPawn* Shell = Target.Get())
	{
		SurfaceZ = Shell->GetOceanSurfaceZ();
	}
	return SurfaceZ - SurfaceClearance;
}

void AAOS_EnemyDaemon::MoveSwept(const FVector& Delta)
{
	FHitResult Hit;
	AddActorWorldOffset(Delta, true, &Hit, ETeleportType::None);
	if (Hit.IsValidBlockingHit())
	{
		// Slide along walls (and kill the velocity into them).
		const FVector Remaining = FVector::VectorPlaneProject(Delta * (1.f - Hit.Time), Hit.Normal);
		Velocity = FVector::VectorPlaneProject(Velocity, Hit.Normal);
		AddActorWorldOffset(Remaining, true, nullptr, ETeleportType::None);
	}
	// Stay under the water surface.
	const float Ceiling = GetSurfaceCeilingZ();
	FVector Location = GetActorLocation();
	if (Location.Z > Ceiling)
	{
		Location.Z = FMath::FInterpTo(Location.Z, Ceiling, 0.016f, 10.f);
		SetActorLocation(Location, true);
		Velocity.Z = FMath::Min(Velocity.Z, 0.0);
	}
}

void AAOS_EnemyDaemon::Steer(const FVector& DesiredVelocity, float Responsiveness, float Dt, const FVector* FacePoint)
{
	// Water inertia: the velocity eases towards the wish (no instant turns or stops).
	Velocity = FMath::VInterpTo(Velocity, DesiredVelocity, Dt, Responsiveness);
	MoveSwept(Velocity * Dt);

	const FVector Facing = FacePoint ? (*FacePoint - GetActorLocation()) : Velocity;
	if (Facing.SizeSquared() > 25.0)
	{
		FRotator Desired = Facing.Rotation();
		// Bank into turns: roll from the lateral acceleration.
		const FVector Accel = (Velocity - PrevVelocity) / FMath::Max(Dt, 1e-3f);
		const float Lateral = float(FVector::DotProduct(Accel, GetActorRightVector()));
		Desired.Roll = FMath::Clamp(Lateral * 0.06f, -MaxBankAngle, MaxBankAngle);
		SetActorRotation(FMath::RInterpTo(GetActorRotation(), Desired, Dt, TurnSpeed));
	}
}

void AAOS_EnemyDaemon::TickPatrol(float Dt)
{
	ChargeAlpha = FMath::FInterpTo(ChargeAlpha, 0.f, Dt, 4.f);
	if (!ActiveRoute || ActiveRoute->GetSplineLength() < 10.f)
	{
		Steer(FVector::ZeroVector, WaterResponsiveness, Dt, nullptr);
		return;
	}
	const float Length = ActiveRoute->GetSplineLength();
	const FVector Location = GetActorLocation();

	// Carrot on the route; it waits for the daemon if it lags (no rubber-banding).
	const FVector Anchor = ActiveRoute->GetLocationAtDistanceAlongSpline(RouteDistance, ESplineCoordinateSpace::World);
	const float Lag = float(FVector::Dist(Anchor, Location));
	const float Progress = FMath::Clamp(1.5f - Lag / (PatrolLookAhead * 2.f), 0.15f, 1.f);
	RouteDistance = WrapDistance(RouteDistance + PatrolSpeed * Progress * Dt, Length);

	const FVector Carrot = ActiveRoute->GetLocationAtDistanceAlongSpline(WrapDistance(RouteDistance + PatrolLookAhead, Length), ESplineCoordinateSpace::World);
	const FVector ToCarrot = Carrot - Location;
	const float Speed = PatrolSpeed * FMath::Clamp(float(ToCarrot.Size()) / PatrolLookAhead, 0.3f, 1.25f);
	Steer(ToCarrot.GetSafeNormal() * Speed, WaterResponsiveness, Dt, nullptr);
}

void AAOS_EnemyDaemon::TickEngage(float Dt)
{
	ChargeAlpha = FMath::FInterpTo(ChargeAlpha, 0.f, Dt, 4.f);
	AShellPawn* Shell = Target.Get();
	if (!Shell)
	{
		SetState(EDaemonState::Return);
		return;
	}
	const FVector ShellLocation = Shell->GetActorLocation();
	const FVector FromShell = (GetActorLocation() - ShellLocation).GetSafeNormal();

	// Stand-off point, slowly orbiting the Shell (deterministic direction from the PID).
	const FVector OrbitDir = FromShell.RotateAngleAxis(OrbitSpeed * OrbitSign * 0.6f, FVector::UpVector);
	const float StandOff = AttackRange * 0.75f + 320.f;
	const FVector Goal = ShellLocation + OrbitDir * StandOff;
	const FVector ToGoal = Goal - GetActorLocation();
	const FVector Desired = ToGoal.GetClampedToMaxSize(EngageSpeed) * FMath::Clamp(float(ToGoal.Size()) / 250.f, 0.2f, 1.f);
	Steer(Desired, WaterResponsiveness * 1.3f, Dt, &ShellLocation);

	const float HullDistance = DistanceToHull(Shell);
	const float Facing = float(FVector::DotProduct(GetActorForwardVector(), -FromShell));
	if (CooldownRemaining <= 0.f && HullDistance <= AttackRange && Facing > 0.8f && HasLineOfSight(Shell))
	{
		SetState(EDaemonState::Telegraph);
	}
}

void AAOS_EnemyDaemon::TickTelegraph(float Dt)
{
	AShellPawn* Shell = Target.Get();
	if (!Shell)
	{
		SetState(EDaemonState::Return);
		return;
	}
	ChargeAlpha = FMath::Clamp(StateTime / FMath::Max(TelegraphTime, 0.05f), 0.f, 1.f);
	const FVector ShellLocation = Shell->GetActorLocation();
	const FVector ToShell = (ShellLocation - GetActorLocation()).GetSafeNormal();

	// Lunge: recoil (draws back like a spring); Pulse: holds still and swells.
	const FVector Desired = AttackMode == EDaemonAttackMode::Lunge ? -ToShell * RecoilSpeed * (1.f - 0.5f * ChargeAlpha) : FVector::ZeroVector;
	Steer(Desired, 3.f, Dt, &ShellLocation);

	if (StateTime < TelegraphTime)
	{
		return;
	}
	if (AttackMode == EDaemonAttackMode::Lunge)
	{
		// Lead the target a little (deterministic: current hull velocity).
		const FVector Predicted = ShellLocation + Shell->GetVelocity() * 0.25f;
		LungeDirection = (Predicted - GetActorLocation()).GetSafeNormal();
		Velocity = LungeDirection * LungeSpeed;
		bStrikeLanded = false;
		SetState(EDaemonState::Strike);
	}
	else
	{
		if (PulseFX)
		{
			UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, PulseFX, GetActorLocation(), GetActorRotation(), FVector(1.f), true, true, ENCPoolMethod::AutoRelease);
		}
		if (DistanceToHull(Shell) <= PulseRadius && HasLineOfSight(Shell))
		{
			StrikeShell(Shell);
		}
		SetState(EDaemonState::Recover);
	}
}

void AAOS_EnemyDaemon::TickStrike(float Dt)
{
	ChargeAlpha = 1.f;
	const float T = FMath::Clamp(StateTime / LungeMaxTime, 0.f, 1.f);
	Velocity = LungeDirection * LungeSpeed * (1.f - 0.35f * T);
	MoveSwept(Velocity * Dt);
	SetActorRotation(FMath::RInterpTo(GetActorRotation(), LungeDirection.Rotation(), Dt, 12.f));

	AShellPawn* Shell = Target.Get();
	if (Shell && !bStrikeLanded && DistanceToHull(Shell) <= StrikeContactPadding)
	{
		bStrikeLanded = true;
		StrikeShell(Shell);
		Velocity = -LungeDirection * LungeSpeed * 0.3f; // bounce off the hull
		SetState(EDaemonState::Recover);
		return;
	}
	if (StateTime >= LungeMaxTime)
	{
		SetState(EDaemonState::Recover);
	}
}

void AAOS_EnemyDaemon::TickRecover(float Dt)
{
	ChargeAlpha = FMath::FInterpTo(ChargeAlpha, 0.f, Dt, 3.f);
	AShellPawn* Shell = Target.Get();
	const FVector ShellLocation = Shell ? Shell->GetActorLocation() : GetActorLocation() + GetActorForwardVector() * 100.f;
	Steer(FVector::ZeroVector, WaterResponsiveness * 0.6f, Dt, Shell ? &ShellLocation : nullptr);
	if (StateTime >= RecoverTime)
	{
		CooldownRemaining = AttackCooldown;
		SetState(Shell ? EDaemonState::Engage : EDaemonState::Return);
	}
}

void AAOS_EnemyDaemon::TickReturn(float Dt)
{
	ChargeAlpha = FMath::FInterpTo(ChargeAlpha, 0.f, Dt, 4.f);
	if (!ActiveRoute)
	{
		SetState(EDaemonState::Patrol);
		return;
	}
	const FVector Goal = ActiveRoute->GetLocationAtDistanceAlongSpline(ReturnDistance, ESplineCoordinateSpace::World);
	const FVector ToGoal = Goal - GetActorLocation();
	const float Dist = float(ToGoal.Size());
	Steer(ToGoal.GetSafeNormal() * PatrolSpeed * 1.4f * FMath::Clamp(Dist / 300.f, 0.3f, 1.f), WaterResponsiveness, Dt, nullptr);
	if (Dist < 180.f)
	{
		RouteDistance = ReturnDistance;
		SetState(EDaemonState::Patrol);
	}
}

// ------------------------------------------------------------------------------------------ damage
void AAOS_EnemyDaemon::StrikeShell(AShellPawn* Shell)
{
	FVector Closest;
	DistanceToHull(Shell, &Closest);
	const FVector Direction = (Closest - GetActorLocation()).GetSafeNormal();

	FHitResult Hit(Shell, Cast<UPrimitiveComponent>(Shell->GetRootComponent()), Closest, -Direction);
	Hit.ImpactPoint = Closest;
	Hit.Location = Closest;
	Hit.ImpactNormal = -Direction;
	Hit.bBlockingHit = true;

	UGameplayStatics::ApplyPointDamage(Shell, AttackDamage, Direction, Hit, nullptr, this,
		DamageTypeClass ? DamageTypeClass : TSubclassOf<UDamageType>(UDamageType::StaticClass()));
	BP_OnStruckShell(Closest);
}

float AAOS_EnemyDaemon::TakeDamage(float DamageAmount, FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser)
{
	if (State == EDaemonState::Dying || DamageAmount <= 0.f)
	{
		return 0.f;
	}
	const float Damage = Super::TakeDamage(DamageAmount, DamageEvent, EventInstigator, DamageCauser);
	if (Damage <= 0.f)
	{
		return 0.f;
	}
	Health = FMath::Max(0.f, Health - Damage);
	HitFlash = 1.f;

	// Shot while patrolling: the daemon is provoked.
	if (State == EDaemonState::Patrol || State == EDaemonState::Return)
	{
		if (AShellPawn* Shell = FindCandidateShell())
		{
			Target = Shell;
			SetState(EDaemonState::Engage);
		}
	}
	if (UEnemyHealthBarWidget* Bar = Cast<UEnemyHealthBarWidget>(HealthBar->GetUserWidgetObject()))
	{
		Bar->SetHealthFraction(GetHealthFraction());
	}
	if (Health <= 0.f)
	{
		Die(DamageCauser);
	}
	return Damage;
}

void AAOS_EnemyDaemon::Die(AActor* Killer)
{
	if (State == EDaemonState::Dying)
	{
		return;
	}
	SetState(EDaemonState::Dying);
	Velocity = FVector::ZeroVector;
	SetActorEnableCollision(false);

	if (DeathFX)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, DeathFX, GetActorLocation(), GetActorRotation(), FVector(DeathFXScale), true, true, ENCPoolMethod::AutoRelease);
	}
	if (DeathSecondaryFX)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, DeathSecondaryFX, GetActorLocation(), GetActorRotation(), FVector(DeathFXScale * 1.6f), true, true, ENCPoolMethod::AutoRelease);
	}
	ChargeFX->Deactivate();
	VisualRoot->SetVisibility(false, true);
	HealthBar->SetVisibility(false);
	CoreLight->SetLightColor(AOSDracula::Pink());
	CoreLight->SetIntensity(CoreLightIntensity * 12.f);

	LogToShell(FString::Printf(TEXT("%s terminated (SIGKILL)"), *GetProcessName()), 2);
	OnDaemonDestroyed.Broadcast(this);
	SetLifeSpan(0.8f);
}

void AAOS_EnemyDaemon::TickDying(float Dt)
{
	DeathTime += Dt;
	CoreLight->SetIntensity(CoreLightIntensity * 12.f * FMath::Exp(-DeathTime * 7.f));
}

void AAOS_EnemyDaemon::LogToShell(const FString& Message, uint8 SeverityIndex) const
{
	if (AShellPawn* Shell = Cast<AShellPawn>(UGameplayStatics::GetPlayerPawn(this, 0)))
	{
		const EAOSHudLogSeverity Severity = SeverityIndex == 3 ? EAOSHudLogSeverity::Warning
			: (SeverityIndex == 2 ? EAOSHudLogSeverity::Charge : EAOSHudLogSeverity::Info);
		Shell->PushTerminalLog(GetProcessName(), Message, Severity);
	}
}

// ----------------------------------------------------------------------------------------- visuals
void AAOS_EnemyDaemon::UpdateVisuals(float Dt)
{
	AnimTime += Dt;
	HitFlash = FMath::Max(0.f, HitFlash - Dt / 0.15f);
	const float Speed01 = FMath::Clamp(float(Velocity.Size()) / FMath::Max(EngageSpeed, 1.f), 0.f, 1.5f);

	FLinearColor TargetColor = IdleColor;
	float TargetGlow = IdleGlow;
	switch (State)
	{
	case EDaemonState::Engage:
	case EDaemonState::Recover:
	case EDaemonState::Return:
		TargetColor = AlertColor;
		TargetGlow = IdleGlow * 1.5f;
		break;
	case EDaemonState::Telegraph:
		TargetColor = AOSDracula::Mix(AlertColor, ChargeColor, FMath::Min(1.f, ChargeAlpha * 1.6f));
		TargetColor = AOSDracula::Mix(TargetColor, StrikeColor, FMath::Max(0.f, ChargeAlpha - 0.6f) * 2.5f);
		TargetGlow = FMath::Lerp(IdleGlow * 1.5f, ChargeGlowMax, ChargeAlpha * ChargeAlpha);
		break;
	case EDaemonState::Strike:
		TargetColor = StrikeColor;
		TargetGlow = ChargeGlowMax;
		break;
	default:
		break;
	}
	const float ColorRate = State == EDaemonState::Telegraph || State == EDaemonState::Strike ? 18.f : 5.f;
	DisplayColor = AOSDracula::Mix(DisplayColor, TargetColor, 1.f - FMath::Exp(-ColorRate * Dt));
	DisplayGlow = FMath::FInterpTo(DisplayGlow, TargetGlow, Dt, ColorRate);
	PushCPD(DisplayColor, DisplayGlow, HitFlash);

	CoreLight->SetLightColor(DisplayColor);
	CoreLight->SetIntensity(CoreLightIntensity * FMath::Pow(FMath::Max(DisplayGlow, 0.1f) / FMath::Max(IdleGlow, 0.1f), 0.7f) * (1.f + 2.f * HitFlash));

	// Swim: bob + sway, telegraph shake and swell (all on the visual root - collision stays put).
	const float Bob = BobAmplitude * FMath::Sin(AnimTime * 2.f * PI * 0.35f + Phase);
	const float Sway = BobAmplitude * 0.5f * FMath::Sin(AnimTime * 2.f * PI * 0.21f + Phase * 1.7f);
	const float Shake = 2.5f * ChargeAlpha * FMath::Sin(AnimTime * 2.f * PI * 23.f + Phase);
	VisualRoot->SetRelativeLocation(FVector(Shake * 0.5f, Sway + Shake, Bob));
	VisualRoot->SetRelativeScale3D(FVector(1.f + 0.12f * ChargeAlpha * ChargeAlpha));

	// Gyroscopic halos: counter-rotating, spin up with the charge.
	const float Spin = HaloSpinSpeed * (1.f + 7.f * ChargeAlpha + 0.6f * Speed01);
	HaloAngleOuter = FMath::Fmod(HaloAngleOuter + Spin * Dt, 360.f);
	HaloAngleInner = FMath::Fmod(HaloAngleInner - Spin * 1.35f * Dt, 360.f);
	HaloOuter->SetRelativeRotation(FQuat(FVector::ForwardVector, FMath::DegreesToRadians(HaloAngleOuter)));
	HaloInner->SetRelativeRotation(FQuat(FRotator(62.f, 0.f, 0.f)) * FQuat(FVector::ForwardVector, FMath::DegreesToRadians(HaloAngleInner)));

	CoreSpin = FMath::Fmod(CoreSpin + (14.f + 60.f * ChargeAlpha) * Dt, 360.f);
	CoreMesh->SetRelativeRotation(FRotator(0.f, 0.f, CoreSpin));

	UpdateTendrils(Dt, Speed01);
}

void AAOS_EnemyDaemon::UpdateTendrils(float Dt, float Speed01)
{
	if (TendrilMeshes.Num() == 0 || TendrilData.Num() != TendrilMeshes.Num())
	{
		return;
	}
	// Skip re-meshing when nobody sees it.
	const APlayerCameraManager* Camera = UGameplayStatics::GetPlayerCameraManager(this, 0);
	if (Camera && FVector::DistSquared(Camera->GetCameraLocation(), GetActorLocation()) > FMath::Square(TendrilUpdateDistance))
	{
		return;
	}
	if (!TendrilMeshes[0]->WasRecentlyRendered(0.25f) && AnimTime > 0.5f)
	{
		return;
	}

	const float ModelScale = CoreRadius / 36.f;
	const float Amplitude = TendrilWaveAmplitude * (1.f + 0.6f * Speed01) + 10.f * ModelScale * ChargeAlpha;
	const float Omega = 2.f * PI * (TendrilWaveFrequency + 0.8f * Speed01 + 1.5f * ChargeAlpha);
	const float Spread = (12.f + 36.f * ChargeAlpha) * ModelScale;
	for (int32 i = 0; i < TendrilMeshes.Num(); ++i)
	{
		SpineScratch.Reset();
		RadiiScratch.Reset();
		const float TendrilPhase = Phase + float(i) * 1.618f;
		for (int32 k = 0; k <= TendrilSegments; ++k)
		{
			const float S = float(k) / float(TendrilSegments);
			const float A = Amplitude * FMath::Pow(S, 1.3f);
			const float Wave = Omega * AnimTime - 2.f * PI * 1.15f * S + TendrilPhase;
			SpineScratch.Add(FVector(-S * TendrilLength * (1.f - 0.15f * ChargeAlpha), A * FMath::Sin(Wave), Spread * S + 0.35f * A * FMath::Cos(Wave * 0.8f)));
			RadiiScratch.Add(FMath::Lerp(5.5f, 0.9f, S) * ModelScale * (1.f + 0.25f * ChargeAlpha));
		}
		AOSDaemonGeometry::UpdateTube(TendrilData[i], SpineScratch, RadiiScratch, TendrilSides);
		TendrilData[i].UpdateSection(TendrilMeshes[i], 0);
	}
}

void AAOS_EnemyDaemon::UpdateHealthBar(float Dt)
{
	UEnemyHealthBarWidget* Bar = Cast<UEnemyHealthBarWidget>(HealthBar->GetUserWidgetObject());
	if (!Bar)
	{
		return;
	}
	const APlayerCameraManager* Camera = UGameplayStatics::GetPlayerCameraManager(this, 0);
	const FVector CameraLocation = Camera ? Camera->GetCameraLocation() : GetActorLocation();
	const bool bEngaged = State == EDaemonState::Engage || State == EDaemonState::Telegraph || State == EDaemonState::Strike || State == EDaemonState::Recover;
	const bool bInRange = FVector::DistSquared(CameraLocation, GetActorLocation()) < FMath::Square(HealthBarVisibleDistance);

	// Only the Shell pilot sees daemon telemetry, and not through walls (cheap 5 Hz occlusion trace).
	const bool bPilot = FindCandidateShell() != nullptr;
	OcclusionTimer -= Dt;
	if (bHideHealthBarWhenOccluded && bInRange && bPilot && OcclusionTimer <= 0.f)
	{
		OcclusionTimer = 0.2f;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(DaemonBarOcclusion), false, this);
		Params.AddIgnoredActor(UGameplayStatics::GetPlayerPawn(this, 0));
		FHitResult Hit;
		bHealthBarOccluded = GetWorld()->LineTraceSingleByChannel(Hit, CameraLocation, GetActorLocation(), ECC_Visibility, Params)
			&& !Cast<AAOS_EnemyDaemon>(Hit.GetActor());
	}
	const bool bShow = bInRange && bPilot && !bHealthBarOccluded && (bAlwaysShowHealthBar || bEngaged || Health < MaxHealth);
	if (HealthBar->IsVisible() != bShow)
	{
		HealthBar->SetVisibility(bShow);
	}
	if (!bShow)
	{
		return;
	}
	if (bWorldSpaceHealthBar)
	{
		// Billboard: the widget plane faces +X of the component.
		HealthBar->SetWorldRotation((CameraLocation - HealthBar->GetComponentLocation()).Rotation());
	}
	Bar->SetThreat(bEngaged, State == EDaemonState::Telegraph ? ChargeAlpha : 0.f);
	Bar->AdvanceDisplay(Dt);
}
