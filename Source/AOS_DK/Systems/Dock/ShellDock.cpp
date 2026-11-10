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
#include "LARS/LARSDockArm.h"

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

	ParkingPoint = CreateDefaultSubobject<USceneComponent>(TEXT("ParkingPoint"));
	ParkingPoint->SetupAttachment(RootComponent);
	ParkingPoint->SetRelativeLocation(FVector(230.f, 220.f, -164.f));
}

void AShellDock::BeginPlay()
{
	Super::BeginPlay();

	if (!LinkedSubmarine)
	{
		LinkedSubmarine = Cast<AShellPawn>(UGameplayStatics::GetActorOfClass(GetWorld(), AShellPawn::StaticClass()));
	}
	if (!LARSArm)
	{
		LARSArm = Cast<ALARSDockArm>(UGameplayStatics::GetActorOfClass(GetWorld(), ALARSDockArm::StaticClass()));
	}
	if (LinkedSubmarine)
	{
		// The Shell starts the level moored at its berth: remember that pose for recoveries.
		CapturedParking = LinkedSubmarine->GetActorTransform();
		CapturedParking.SetScale3D(FVector::OneVector);
		bHasCapturedParking = true;
	}
}

FTransform AShellDock::GetParkingTransform() const
{
	if (LARSArm)
	{
		return LARSArm->GetHoldTransform();   // the berth is the arm's cradle, above the waves
	}
	if (bUseParkingPoint || !bHasCapturedParking)
	{
		return FTransform(ParkingPoint->GetComponentRotation(), ParkingPoint->GetComponentLocation());
	}
	return CapturedParking;
}

void AShellDock::RecoverShell(AShellPawn* Shell)
{
	if (!Shell)
	{
		return;
	}
	APlayerController* PC = Cast<APlayerController>(Shell->GetController());

	AAdminCharacter* Admin = nullptr;
	TArray<AActor*> AttachedActors;
	Shell->GetAttachedActors(AttachedActors);
	for (AActor* Attached : AttachedActors)
	{
		Admin = Cast<AAdminCharacter>(Attached);
		if (Admin)
		{
			break;
		}
	}

	// 1) Pilot back on the surface dock, on foot.
	if (Admin)
	{
		const FRotator Facing(0.f, DisembarkPoint->GetComponentRotation().Yaw, 0.f);
		Admin->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
		Admin->SetActorLocationAndRotation(DisembarkPoint->GetComponentLocation(), Facing, false, nullptr, ETeleportType::TeleportPhysics);
		Admin->SetActorHiddenInGame(false);
		Admin->SetActorEnableCollision(true);
		if (PC)
		{
			PC->Possess(Admin);
			PC->SetControlRotation(Facing);
			PC->SetViewTarget(Admin);
		}
		Admin->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
	}

	// 2) Shell back to its berth with the base charge.
	Shell->FinishRecovery(GetParkingTransform());
	if (LARSArm)
	{
		LARSArm->SnapToHold(Shell);   // straight back into the jaws, out of the water
	}

	if (AAdminPlayerController* AdminPC = Cast<AAdminPlayerController>(PC))
	{
		AdminPC->SetInteractLocked(false);
	}
}

void AShellDock::GetInteractPrompt_Implementation(AActor* InstigatorActor, FText& OutAction, bool& bOutAvailable)
{
	const bool bFromShell = InstigatorActor && InstigatorActor->IsA<AShellPawn>();
	bOutAvailable = true;
	OutAction = bFromShell
		? NSLOCTEXT("AOSDock", "Disembark", "DISEMBARK")
		: NSLOCTEXT("AOSDock", "Board", "BOARD SHELL");
	if (LARSArm)
	{
		if (LARSArm->IsBusy())
		{
			OutAction = NSLOCTEXT("AOSDock", "LarsBusy", "LARS BUSY");
			bOutAvailable = false;
		}
		else
		{
			bOutAvailable = bFromShell ? LARSArm->CanRecover() : LARSArm->IsHoldingShell();
		}
	}
}

void AShellDock::HandleLARSRecoveryComplete(AShellPawn* Shell)
{
	DisembarkPilot(Shell);
}

void AShellDock::Interact_Implementation(AActor* InstigatorActor)
{
    if (AAdminCharacter* Admin = Cast<AAdminCharacter>(InstigatorActor))
    {
        BoardShell(Admin);
    }
    else if (AShellPawn* Shell = Cast<AShellPawn>(InstigatorActor))
    {
        if (LARSArm)
        {
            // Docking with the LARS: align -> capture -> lift; the pilot steps out when the arm reports back.
            if (LARSArm->CanRecover())
            {
                LARSArm->BeginRecovery(Shell, this);
            }
            return;
        }
        DisembarkPilot(Shell);
    }
}

void AShellDock::BoardShell(AAdminCharacter* Admin)
{
    //~ Посадка в субмарину
    {
        if (!LinkedSubmarine || !Admin) return;
        if (LARSArm && !LARSArm->IsHoldingShell()) return;   // the Shell is not in the cradle

        AAdminPlayerController* AdminPC = Cast<AAdminPlayerController>(Admin->GetController());
        if (!AdminPC) return;

        AdminPC->SetInteractLocked(true);
        Admin->GetCharacterMovement()->SetMovementMode(MOVE_None);

        // LARS: blend out to the pier's cinematic LaunchCam; otherwise straight into the cockpit.
        float BlendTime = 1.0f;
        const bool bCinematic = LARSArm && LARSArm->BeginCinematic(AdminPC, BlendTime);
        if (!bCinematic)
        {
            BlendTime = 1.0f;
            AdminPC->SetViewTargetWithBlend(LinkedSubmarine, BlendTime);
        }

        // Безпечні слабкі вказівники для таймера
        TWeakObjectPtr<AAdminPlayerController> WeakPC = AdminPC;
        TWeakObjectPtr<AAdminCharacter> WeakAdmin = Admin;
        TWeakObjectPtr<AShellPawn> WeakSub = LinkedSubmarine;
        TWeakObjectPtr<ALARSDockArm> WeakArm = LARSArm;

        FTimerHandle BlendTimer;
        GetWorld()->GetTimerManager().SetTimer(BlendTimer, [WeakPC, WeakAdmin, WeakSub, WeakArm, bCinematic]()
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

            // During the cinematic the possess must not snap the view to the Shell (the arm hands it over later).
            const bool bAutoCam = PC->bAutoManageActiveCameraTarget;
            if (bCinematic)
            {
                PC->bAutoManageActiveCameraTarget = false;
            }
            PC->Possess(Sub);
            PC->bAutoManageActiveCameraTarget = bAutoCam;
            PC->SetControlRotation(CamRot);

            AdminChar->AttachToComponent(Sub->GetRootComponent(), FAttachmentTransformRules::SnapToTargetNotIncludingScale);
            AdminChar->SetActorHiddenInGame(true);
            AdminChar->SetActorEnableCollision(false);

            // Розблоковуємо взаємодію для нового стану
            PC->SetInteractLocked(false);

            // LARS: the pilot is aboard - lower the Shell into the water; 6DOF + HUD come at the release.
            if (ALARSDockArm* Arm = WeakArm.Get())
            {
                Arm->BeginLaunch();
            }

        }, BlendTime, false);
    }
}

void AShellDock::DisembarkPilot(AShellPawn* Shell)
{
    //~ Висадка на док
    if (Shell)
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