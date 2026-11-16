#include "AOSFallRecoveryVolume.h"

#include "AOSSafeGroundTracker.h"
#include "AOS_DK/Player/AdminCharacter.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerStart.h"
#include "TimerManager.h"

namespace
{
	/** PlayerStart_0 if present, otherwise any PlayerStart. */
	const APlayerStart* FindFallbackStart(const UWorld* World)
	{
		const APlayerStart* Any = nullptr;
		for (TActorIterator<APlayerStart> It(World); It; ++It)
		{
			if (It->GetFName() == FName(TEXT("PlayerStart_0")))
			{
				return *It;
			}
			if (!Any)
			{
				Any = *It;
			}
		}
		return Any;
	}
}

AAOSFallRecoveryVolume::AAOSFallRecoveryVolume()
{
	PrimaryActorTick.bCanEverTick = false;

	RecoveryBox = CreateDefaultSubobject<UBoxComponent>(TEXT("RecoveryBox"));
	SetRootComponent(RecoveryBox);
	RecoveryBox->SetMobility(EComponentMobility::Static);
	RecoveryBox->InitBoxExtent(FVector(1000.f, 1000.f, 140.f));
	RecoveryBox->SetCollisionProfileName(TEXT("AOS_FallRecovery"));
	RecoveryBox->SetGenerateOverlapEvents(true);
	RecoveryBox->SetCanEverAffectNavigation(false);
	RecoveryBox->SetHiddenInGame(true);
	RecoveryBox->ShapeColor = FColor(0, 170, 255);
	RecoveryBox->OnComponentBeginOverlap.AddDynamic(this, &AAOSFallRecoveryVolume::HandleBeginOverlap);
}

void AAOSFallRecoveryVolume::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	// Never leave the character locked if the volume goes away mid-recovery.
	if (ActiveCharacter.IsValid())
	{
		FinishRecovery();
	}
	Super::EndPlay(EndPlayReason);
}

void AAOSFallRecoveryVolume::HandleBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
	UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	AAdminCharacter* Character = Cast<AAdminCharacter>(OtherActor);
	if (Character && OtherComp == Character->GetCapsuleComponent())
	{
		BeginRecovery(Character);
	}
}

void AAOSFallRecoveryVolume::BeginRecovery(AAdminCharacter* Character)
{
	UAOSSafeGroundTracker* Tracker = Character->GetSafeGroundTracker();
	if (!Tracker || !Tracker->TryBeginRecovery())
	{
		return;
	}

	ActiveCharacter = Character;

	UCharacterMovementComponent* Movement = Character->GetCharacterMovement();
	Movement->StopMovementImmediately();
	Movement->DisableMovement();

	APlayerController* PlayerController = Cast<APlayerController>(Character->GetController());
	LockedController = PlayerController;
	if (PlayerController)
	{
		// Counted flags: Move and Look go through AddMovementInput / AddControllerYawInput, which honour them.
		PlayerController->SetIgnoreMoveInput(true);
		PlayerController->SetIgnoreLookInput(true);
		if (PlayerController->PlayerCameraManager)
		{
			PlayerController->PlayerCameraManager->StartCameraFade(0.f, 1.f, FadeOutDuration, FadeColor, false, true);
		}
	}

	UE_LOG(LogAOSFallRecovery, Log, TEXT("%s: %s fell into the water at %s, recovering."),
		*GetName(), *Character->GetName(), *Character->GetActorLocation().ToCompactString());

	GetWorldTimerManager().SetTimer(TeleportTimer, this, &AAOSFallRecoveryVolume::TeleportToSafeGround,
		FMath::Max(FadeOutDuration, 0.01f), false);
}

void AAOSFallRecoveryVolume::TeleportToSafeGround()
{
	AAdminCharacter* Character = ActiveCharacter.Get();
	if (!Character)
	{
		FinishRecovery();
		return;
	}

	FVector Location = FVector::ZeroVector;
	FRotator Rotation = FRotator::ZeroRotator;
	bool bHaveTarget = false;

	FTransform Pose;
	if (Character->GetSafeGroundTracker() && Character->GetSafeGroundTracker()->GetLatestSafeTransform(Pose))
	{
		Location = Pose.GetLocation() + FVector(0.f, 0.f, RecoveryLift);
		Rotation = Pose.Rotator();
		bHaveTarget = true;
	}
	else if (const APlayerStart* Start = FindFallbackStart(GetWorld()))
	{
		Location = Start->GetActorLocation();
		Rotation = Start->GetActorRotation();
		bHaveTarget = true;
		UE_LOG(LogAOSFallRecovery, Log, TEXT("%s: safe-ground ring is empty, falling back to %s."), *GetName(), *Start->GetName());
	}

	UCharacterMovementComponent* Movement = Character->GetCharacterMovement();
	Movement->StopMovementImmediately();
	Movement->Velocity = FVector::ZeroVector;

	if (bHaveTarget)
	{
		if (!Character->TeleportTo(Location, Rotation, false, false))
		{
			Character->SetActorLocationAndRotation(Location, Rotation, false, nullptr, ETeleportType::TeleportPhysics);
		}
		if (AController* Controller = Character->GetController())
		{
			Controller->SetControlRotation(FRotator(0.f, Rotation.Yaw, 0.f));
		}
		UE_LOG(LogAOSFallRecovery, Log, TEXT("%s: %s returned to %s."), *GetName(), *Character->GetName(), *Location.ToCompactString());
	}
	else
	{
		UE_LOG(LogAOSFallRecovery, Error, TEXT("%s: no safe pose and no PlayerStart, %s stays in place."), *GetName(), *Character->GetName());
	}

	// TeleportTo resets the movement mode (the character would start falling and walking under the fade-in): keep it frozen.
	Movement->DisableMovement();

	if (const APlayerController* PlayerController = Cast<APlayerController>(Character->GetController()))
	{
		if (PlayerController->PlayerCameraManager)
		{
			PlayerController->PlayerCameraManager->StartCameraFade(1.f, 0.f, FadeInDuration, FadeColor, false, false);
		}
	}

	GetWorldTimerManager().SetTimer(FinishTimer, this, &AAOSFallRecoveryVolume::FinishRecovery,
		FMath::Max(FadeInDuration, 0.01f), false);
}

void AAOSFallRecoveryVolume::FinishRecovery()
{
	GetWorldTimerManager().ClearTimer(TeleportTimer);
	GetWorldTimerManager().ClearTimer(FinishTimer);

	if (APlayerController* PlayerController = LockedController.Get())
	{
		PlayerController->SetIgnoreMoveInput(false);
		PlayerController->SetIgnoreLookInput(false);
	}
	LockedController.Reset();

	if (AAdminCharacter* Character = ActiveCharacter.Get())
	{
		Character->GetCharacterMovement()->SetMovementMode(MOVE_Falling);
		if (UAOSSafeGroundTracker* Tracker = Character->GetSafeGroundTracker())
		{
			Tracker->EndRecovery();
		}
	}
	ActiveCharacter.Reset();
}
