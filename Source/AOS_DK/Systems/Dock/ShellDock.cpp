#include "ShellDock.h"
#include "Components/BoxComponent.h"
#include "AOS_DK/Player/AdminCharacter.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"
#include "TimerManager.h"
#include "GameFramework/CharacterMovementComponent.h"

AShellDock::AShellDock()
{
	PrimaryActorTick.bCanEverTick = false;

	DefaultRoot = CreateDefaultSubobject<USceneComponent>(TEXT("DefaultRoot"));
	RootComponent = DefaultRoot;

	DockTrigger = CreateDefaultSubobject<UBoxComponent>(TEXT("DockTrigger"));
	DockTrigger->SetupAttachment(RootComponent);
	DockTrigger->SetBoxExtent(FVector(400.f, 400.f, 200.f));
	DockTrigger->SetCollisionProfileName(TEXT("Trigger")); 

	DisembarkPoint = CreateDefaultSubobject<USceneComponent>(TEXT("DisembarkPoint"));
	DisembarkPoint->SetupAttachment(RootComponent);
	DisembarkPoint->SetRelativeLocation(FVector(0.f, 500.f, 100.f));
}

void AShellDock::BeginPlay()
{
	Super::BeginPlay();

	if (!LinkedSubmarine)
	{
		LinkedSubmarine = Cast<AShellPawn>(UGameplayStatics::GetActorOfClass(GetWorld(), AShellPawn::StaticClass()));
	}
}

void AShellDock::Interact_Implementation(AActor* InstigatorActor)
{
	if (AAdminCharacter* Admin = Cast<AAdminCharacter>(InstigatorActor))
	{
		if (LinkedSubmarine)
		{
			if (APlayerController* PC = Cast<APlayerController>(Admin->GetController()))
			{
				Admin->GetCharacterMovement()->SetMovementMode(MOVE_None);
				PC->SetViewTargetWithBlend(LinkedSubmarine, 1.0f);

				FTimerHandle BlendTimer;
				GetWorld()->GetTimerManager().SetTimer(BlendTimer, [PC, Admin, this]()
				{
					FRotator CamRot = PC->PlayerCameraManager->GetCameraRotation();
					
					PC->Possess(LinkedSubmarine);
					PC->SetControlRotation(CamRot);
					
					Admin->AttachToComponent(LinkedSubmarine->GetRootComponent(), FAttachmentTransformRules::SnapToTargetNotIncludingScale);
					Admin->SetActorHiddenInGame(true);
					Admin->SetActorEnableCollision(false);
				}, 1.0f, false);
			}
		}
	}
	else if (AShellPawn* Shell = Cast<AShellPawn>(InstigatorActor))
	{
		if (APlayerController* PC = Cast<APlayerController>(Shell->GetController()))
		{
			TArray<AActor*> AttachedActors;
			Shell->GetAttachedActors(AttachedActors);

			for (AActor* Attached : AttachedActors)
			{
				if (AAdminCharacter* AdminToUnpack = Cast<AAdminCharacter>(Attached))
				{
					AdminToUnpack->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
					AdminToUnpack->SetActorLocationAndRotation(DisembarkPoint->GetComponentLocation(), DisembarkPoint->GetComponentRotation(), false, nullptr, ETeleportType::TeleportPhysics);
					AdminToUnpack->SetActorHiddenInGame(false);
					AdminToUnpack->SetActorEnableCollision(true);
					AdminToUnpack->GetCharacterMovement()->SetMovementMode(MOVE_None);

					PC->SetViewTargetWithBlend(AdminToUnpack, 1.0f);

					FTimerHandle BlendTimer;
					GetWorld()->GetTimerManager().SetTimer(BlendTimer, [PC, AdminToUnpack]()
					{
						FRotator CamRot = PC->PlayerCameraManager->GetCameraRotation();
						
						PC->Possess(AdminToUnpack);
						PC->SetControlRotation(CamRot);
						
						AdminToUnpack->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
					}, 1.0f, false);

					break;
				}
			}
		}
	}
}