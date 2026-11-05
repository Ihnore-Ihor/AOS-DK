#include "AOS_EnemySpawner.h"

#include "Components/SplineComponent.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

AAOS_EnemySpawner::AAOS_EnemySpawner()
{
	PrimaryActorTick.bCanEverTick = false;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	RootComponent = SceneRoot;

	PatrolSpline = CreateDefaultSubobject<USplineComponent>(TEXT("PatrolSpline"));
	PatrolSpline->SetupAttachment(SceneRoot);
	PatrolSpline->SetClosedLoop(true, false);

	EnemyClass = AAOS_EnemyDaemon::StaticClass();
}

void AAOS_EnemySpawner::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	RebuildRoute();
}

void AAOS_EnemySpawner::RebuildRoute()
{
	TArray<FVector> Points;
	switch (RouteMode)
	{
	case EAOSPatrolRouteMode::GeneratedRing:
		for (int32 i = 0; i < RingPointCount; ++i)
		{
			const float A = 2.f * PI * float(i) / float(RingPointCount);
			Points.Add(FVector(FMath::Cos(A) * PatrolRadius, FMath::Sin(A) * PatrolRadius, FMath::Sin(2.f * A) * RingVerticalWave));
		}
		break;
	case EAOSPatrolRouteMode::PatrolPoints:
		Points = PatrolPoints;
		break;
	case EAOSPatrolRouteMode::Spline:
	default:
		if (PatrolSpline->GetNumberOfSplinePoints() >= 3)
		{
			PatrolSpline->SetClosedLoop(true, true);
			return; // hand-edited: keep the designer's points
		}
		// Seed an editable square so the designer has something to drag.
		Points = { FVector(600, 0, 0), FVector(0, 600, 0), FVector(-600, 0, 0), FVector(0, -600, 0) };
		break;
	}
	if (Points.Num() >= 2)
	{
		PatrolSpline->SetSplinePoints(Points, ESplineCoordinateSpace::Local, false);
		PatrolSpline->SetClosedLoop(true, true);
	}
}

void AAOS_EnemySpawner::BeginPlay()
{
	Super::BeginPlay();
	RebuildRoute();
	if (bSpawnOnBeginPlay && MaxActiveEnemies > 0)
	{
		FTimerDelegate Tick = FTimerDelegate::CreateUObject(this, &AAOS_EnemySpawner::TrySpawn);
		GetWorldTimerManager().SetTimer(SpawnTimer, Tick, SpawnInterval, true, FMath::Max(InitialDelay, 0.01f));
	}
}

void AAOS_EnemySpawner::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	GetWorldTimerManager().ClearTimer(SpawnTimer);
	for (AAOS_EnemyDaemon* Daemon : ActiveDaemons)
	{
		if (IsValid(Daemon))
		{
			Daemon->OnDaemonDestroyed.RemoveDynamic(this, &AAOS_EnemySpawner::HandleDaemonDestroyed);
		}
	}
	ActiveDaemons.Reset();
	Super::EndPlay(EndPlayReason);
}

void AAOS_EnemySpawner::SetSpawningEnabled(bool bEnabled)
{
	bSpawningEnabled = bEnabled;
}

int32 AAOS_EnemySpawner::GetActiveCount() const
{
	int32 Count = 0;
	for (const AAOS_EnemyDaemon* Daemon : ActiveDaemons)
	{
		Count += (IsValid(Daemon) && Daemon->IsAlive()) ? 1 : 0;
	}
	return Count;
}

bool AAOS_EnemySpawner::IsActivated() const
{
	if (ActivationRadius <= 0.f)
	{
		return true;
	}
	const APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	return Pawn && FVector::DistSquared(Pawn->GetActorLocation(), GetActorLocation()) <= FMath::Square(ActivationRadius);
}

void AAOS_EnemySpawner::TrySpawn()
{
	ActiveDaemons.RemoveAll([](const TObjectPtr<AAOS_EnemyDaemon>& Daemon) { return !IsValid(Daemon) || !Daemon->IsAlive(); });
	if (!bSpawningEnabled || !IsActivated() || ActiveDaemons.Num() >= MaxActiveEnemies)
	{
		return;
	}
	if (TotalSpawnBudget > 0 && SpawnSerial >= TotalSpawnBudget)
	{
		return;
	}
	SpawnDaemon();
}

AAOS_EnemyDaemon* AAOS_EnemySpawner::SpawnDaemon()
{
	UWorld* World = GetWorld();
	if (!World || !EnemyClass)
	{
		return nullptr;
	}
	// Deterministic placement: evenly spaced slots along the route, cycling with the serial.
	const float Length = PatrolSpline->GetSplineLength();
	const int32 Slots = FMath::Max(MaxActiveEnemies, 1);
	const float StartDistance = Length > 0.f ? Length * float(SpawnSerial % Slots) / float(Slots) : 0.f;
	const FVector Location = PatrolSpline->GetLocationAtDistanceAlongSpline(StartDistance, ESplineCoordinateSpace::World);
	const FRotator Rotation = PatrolSpline->GetDirectionAtDistanceAlongSpline(StartDistance, ESplineCoordinateSpace::World).Rotation();

	const EDaemonAttackMode Mode = (bAlternateAttackModes && (SpawnSerial % 2 == 1))
		? (DefaultAttackMode == EDaemonAttackMode::Lunge ? EDaemonAttackMode::Pulse : EDaemonAttackMode::Lunge)
		: DefaultAttackMode;

	AAOS_EnemyDaemon* Daemon = World->SpawnActorDeferred<AAOS_EnemyDaemon>(EnemyClass, FTransform(Rotation, Location), this, nullptr,
		ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn);
	if (!Daemon)
	{
		return nullptr;
	}
	Daemon->InitializeFromSpawner(this, PatrolSpline, StartDistance, Mode, SpawnSerial);
	Daemon->FinishSpawning(FTransform(Rotation, Location));

	++SpawnSerial;
	ActiveDaemons.Add(Daemon);
	Daemon->OnDaemonDestroyed.AddDynamic(this, &AAOS_EnemySpawner::HandleDaemonDestroyed);
	OnDaemonSpawned.Broadcast(this, Daemon);
	return Daemon;
}

void AAOS_EnemySpawner::HandleDaemonDestroyed(AAOS_EnemyDaemon* Daemon)
{
	ActiveDaemons.Remove(Daemon);
}
