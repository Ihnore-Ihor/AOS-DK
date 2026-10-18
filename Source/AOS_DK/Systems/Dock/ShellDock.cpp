#include "ShellDock.h"
#include "Components/BoxComponent.h"
#include "AOS_DK/Player/AdminCharacter.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"
#include "TimerManager.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "AOS_DK/Player/PlayerController/AdminPlayerController.h"

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
    //~ Посадка в субмарину
    if (AAdminCharacter* Admin = Cast<AAdminCharacter>(InstigatorActor))
    {
        if (!LinkedSubmarine) return;

        AAdminPlayerController* AdminPC = Cast<AAdminPlayerController>(Admin->GetController());
        if (!AdminPC) return;

        AdminPC->SetInteractLocked(true);
        Admin->GetCharacterMovement()->SetMovementMode(MOVE_None);
        AdminPC->SetViewTargetWithBlend(LinkedSubmarine, 1.0f);

        // Безпечні слабкі вказівники для таймера
        TWeakObjectPtr<AAdminPlayerController> WeakPC = AdminPC;
        TWeakObjectPtr<AAdminCharacter> WeakAdmin = Admin;
        TWeakObjectPtr<AShellPawn> WeakSub = LinkedSubmarine;

        FTimerHandle BlendTimer;
        GetWorld()->GetTimerManager().SetTimer(BlendTimer, [WeakPC, WeakAdmin, WeakSub]()
        {
            // Перевіряємо валідність об'єктів перед зверненням
            if (!WeakPC.IsValid() || !WeakAdmin.IsValid() || !WeakSub.IsValid())
            {
                if (WeakPC.IsValid())
                {
                    WeakPC->SetInteractLocked(false);
                }
                return;
            }

            AAdminPlayerController* PC = WeakPC.Get();
            AAdminCharacter* AdminChar = WeakAdmin.Get();
            AShellPawn* Sub = WeakSub.Get();

            FRotator CamRot = PC->PlayerCameraManager ? PC->PlayerCameraManager->GetCameraRotation() : FRotator::ZeroRotator;

            PC->Possess(Sub);
            PC->SetControlRotation(CamRot);

            AdminChar->AttachToComponent(Sub->GetRootComponent(), FAttachmentTransformRules::SnapToTargetNotIncludingScale);
            AdminChar->SetActorHiddenInGame(true);
            AdminChar->SetActorEnableCollision(false);

            // Розблоковуємо взаємодію для нового стану
            PC->SetInteractLocked(false);

        }, 1.0f, false);
    }
    //~ Висадка на док
    else if (AShellPawn* Shell = Cast<AShellPawn>(InstigatorActor))
    {
        AAdminPlayerController* AdminPC = Cast<AAdminPlayerController>(Shell->GetController());
        if (!AdminPC) return;

        TArray<AActor*> AttachedActors;
        Shell->GetAttachedActors(AttachedActors);

        for (AActor* Attached : AttachedActors)
        {
            if (AAdminCharacter* AdminToUnpack = Cast<AAdminCharacter>(Attached))
            {
                AdminPC->SetInteractLocked(true);

                AdminToUnpack->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
                AdminToUnpack->SetActorLocationAndRotation(
                    DisembarkPoint->GetComponentLocation(),
                    DisembarkPoint->GetComponentRotation(),
                    false, nullptr, ETeleportType::TeleportPhysics
                );
                AdminToUnpack->SetActorHiddenInGame(false);
                AdminToUnpack->SetActorEnableCollision(true);
                AdminToUnpack->GetCharacterMovement()->SetMovementMode(MOVE_None);

                AdminPC->SetViewTargetWithBlend(AdminToUnpack, 1.0f);

                TWeakObjectPtr<AAdminPlayerController> WeakPC = AdminPC;
                TWeakObjectPtr<AAdminCharacter> WeakAdmin = AdminToUnpack;

                FTimerHandle BlendTimer;
                GetWorld()->GetTimerManager().SetTimer(BlendTimer, [WeakPC, WeakAdmin]()
                {
                    if (!WeakPC.IsValid() || !WeakAdmin.IsValid())
                    {
                        if (WeakPC.IsValid())
                        {
                            WeakPC->SetInteractLocked(false);
                        }
                        return;
                    }

                    AAdminPlayerController* PC = WeakPC.Get();
                    AAdminCharacter* AdminChar = WeakAdmin.Get();

                    FRotator CamRot = PC->PlayerCameraManager ? PC->PlayerCameraManager->GetCameraRotation() : FRotator::ZeroRotator;

                    PC->Possess(AdminChar);
                    PC->SetControlRotation(CamRot);
                    AdminChar->GetCharacterMovement()->SetMovementMode(MOVE_Walking);

                    PC->SetInteractLocked(false);

                }, 1.0f, false);

                break;
            }
        }
    }
}