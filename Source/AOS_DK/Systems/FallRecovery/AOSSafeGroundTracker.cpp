#include "AOSSafeGroundTracker.h"

#include "CollisionQueryParams.h"
#include "Components/CapsuleComponent.h"
#include "Engine/EngineTypes.h"
#include "Engine/HitResult.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

DEFINE_LOG_CATEGORY(LogAOSFallRecovery);

UAOSSafeGroundTracker::UAOSSafeGroundTracker()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	PrimaryComponentTick.TickInterval = PollInterval;
	Ring.SetNum(RingCapacity);
}

void UAOSSafeGroundTracker::BeginPlay()
{
	Super::BeginPlay();

	OwnerCharacter = Cast<ACharacter>(GetOwner());
	if (!OwnerCharacter)
	{
		UE_LOG(LogAOSFallRecovery, Warning, TEXT("%s: owner is not an ACharacter, tracker disabled."), *GetNameSafe(this));
		SetComponentTickEnabled(false);
		return;
	}

	PrimaryComponentTick.TickInterval = FMath::Max(PollInterval, 0.05f);
}

void UAOSSafeGroundTracker::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	const ACharacter* Character = OwnerCharacter;
	if (!Character || bRecovering || !Character->GetController())
	{
		return;
	}

	const UCharacterMovementComponent* Movement = Character->GetCharacterMovement();
	if (!Movement || !Movement->IsMovingOnGround())
	{
		return;
	}

	if (!IsStandingOnSafeGround(*Character) || !IsClearOfEdges(*Character))
	{
		return;
	}

	const float Yaw = Character->GetControlRotation().Yaw;
	PushSafeTransform(FTransform(FRotator(0.f, Yaw, 0.f), Character->GetActorLocation()));
}

bool UAOSSafeGroundTracker::IsStandingOnSafeGround(const ACharacter& Character) const
{
	const UCharacterMovementComponent* Movement = Character.GetCharacterMovement();
	const FFindFloorResult& Floor = Movement->CurrentFloor;
	if (!Floor.IsWalkableFloor())
	{
		return false;
	}

	const UPrimitiveComponent* FloorComponent = Floor.HitResult.GetComponent();
	const AActor* FloorActor = Floor.HitResult.GetActor();
	return (FloorComponent && FloorComponent->ComponentHasTag(SafeGroundTag))
		|| (FloorActor && FloorActor->ActorHasTag(SafeGroundTag));
}

bool UAOSSafeGroundTracker::IsClearOfEdges(const ACharacter& Character) const
{
	const UWorld* World = GetWorld();
	const UCapsuleComponent* Capsule = Character.GetCapsuleComponent();
	const UCharacterMovementComponent* Movement = Character.GetCharacterMovement();
	if (!World || !Capsule || !Movement)
	{
		return false;
	}

	// Same query setup the movement component uses for floor sweeps: the capsule's own object type and responses.
	FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(AOSSafeGroundEdgeProbe), false, &Character);
	FCollisionResponseParams ResponseParams;
	Capsule->InitSweepCollisionParams(QueryParams, ResponseParams);

	const ECollisionChannel Channel = Capsule->GetCollisionObjectType();
	const FCollisionShape Probe = FCollisionShape::MakeSphere(EdgeProbeRadius);
	const FVector Feet = Character.GetActorLocation() - FVector(0.f, 0.f, Capsule->GetScaledCapsuleHalfHeight());
	const float StartZ = Feet.Z + Movement->MaxStepHeight;
	const float EndZ = Feet.Z - EdgeProbeDrop;

	constexpr int32 ProbeCount = 8;
	for (int32 Index = 0; Index < ProbeCount; ++Index)
	{
		const float Angle = UE_TWO_PI * static_cast<float>(Index) / static_cast<float>(ProbeCount);
		const FVector Offset(FMath::Cos(Angle) * EdgeClearanceRadius, FMath::Sin(Angle) * EdgeClearanceRadius, 0.f);
		const FVector Start(Feet.X + Offset.X, Feet.Y + Offset.Y, StartZ);
		const FVector End(Feet.X + Offset.X, Feet.Y + Offset.Y, EndZ);

		FHitResult Hit;
		// Any blocking hit (including a probe that starts inside solid geometry) means there is no drop at this side.
		if (!World->SweepSingleByChannel(Hit, Start, End, FQuat::Identity, Channel, Probe, QueryParams, ResponseParams))
		{
			return false;
		}
	}
	return true;
}

void UAOSSafeGroundTracker::PushSafeTransform(const FTransform& Pose)
{
	if (Ring.Num() != RingCapacity)
	{
		Ring.SetNum(RingCapacity);
	}
	Ring[RingHead] = Pose;
	RingHead = (RingHead + 1) % RingCapacity;
	RingCount = FMath::Min(RingCount + 1, RingCapacity);
}

bool UAOSSafeGroundTracker::GetLatestSafeTransform(FTransform& OutTransform) const
{
	if (RingCount == 0)
	{
		return false;
	}
	OutTransform = Ring[(RingHead + RingCapacity - 1) % RingCapacity];
	return true;
}

TArray<FTransform> UAOSSafeGroundTracker::GetSafeTransformsNewestFirst() const
{
	TArray<FTransform> Result;
	Result.Reserve(RingCount);
	for (int32 Age = 1; Age <= RingCount; ++Age)
	{
		Result.Add(Ring[(RingHead + RingCapacity - Age) % RingCapacity]);
	}
	return Result;
}

void UAOSSafeGroundTracker::ClearSafeTransforms()
{
	RingHead = 0;
	RingCount = 0;
}

bool UAOSSafeGroundTracker::TryBeginRecovery()
{
	if (bRecovering)
	{
		return false;
	}
	bRecovering = true;
	return true;
}

void UAOSSafeGroundTracker::EndRecovery()
{
	bRecovering = false;
}
