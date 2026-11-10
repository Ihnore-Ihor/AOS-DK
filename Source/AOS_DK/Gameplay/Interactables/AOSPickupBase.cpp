#include "AOSPickupBase.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/CollisionProfile.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraComponent.h"
#include "AOS_DK/Submarine/ShellPawn.h"

AAOSPickupBase::AAOSPickupBase()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.f;

	Trigger = CreateDefaultSubobject<USphereComponent>(TEXT("Trigger"));
	SetRootComponent(Trigger);
	Trigger->InitSphereRadius(150.f);
	Trigger->SetMobility(EComponentMobility::Movable);
	Trigger->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Trigger->SetCollisionObjectType(ECC_WorldDynamic);
	Trigger->SetCollisionResponseToAllChannels(ECR_Ignore);
	Trigger->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
	Trigger->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Overlap);
	Trigger->SetCollisionResponseToChannel(ECC_Vehicle, ECR_Overlap);
	Trigger->SetGenerateOverlapEvents(true);
	Trigger->SetCanEverAffectNavigation(false);
	Trigger->ShapeColor = FColor(0xBD, 0x93, 0xF9);

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Trigger);
	Mesh->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->SetCanEverAffectNavigation(false);

	Glow = CreateDefaultSubobject<UPointLightComponent>(TEXT("Glow"));
	Glow->SetupAttachment(Mesh);
	Glow->SetIntensityUnits(ELightUnits::Candelas);
	Glow->SetIntensity(40.f);
	Glow->SetAttenuationRadius(450.f);
	Glow->SetCastShadows(false);
	Glow->bAffectTranslucentLighting = false;
}

void AAOSPickupBase::BeginPlay()
{
	Super::BeginPlay();
	MeshBaseLocation = Mesh->GetRelativeLocation();
	BaseLightIntensity = Glow->Intensity;
	// Desynchronise neighbouring pickups.
	Phase = FMath::Frac(static_cast<float>(GetActorLocation().X + GetActorLocation().Y) * 0.00137f) * UE_TWO_PI;
	// No overlap auto-collect: salvage is an explicit [F] on the pickup in the reticle focus (Interact).
}

void AAOSPickupBase::Interact_Implementation(AActor* InstigatorActor)
{
	TryCollect(Cast<AShellPawn>(InstigatorActor));
}

void AAOSPickupBase::GetInteractPrompt_Implementation(AActor* InstigatorActor, FText& OutAction, bool& bOutAvailable)
{
	const AShellPawn* Shell = Cast<AShellPawn>(InstigatorActor);
	bOutAvailable = !bCollected && Shell && CanApplyPickup(Shell);
	OutAction = bOutAvailable ? GetSalvageLabel() : NSLOCTEXT("AOSPickup", "Full", "FULL");
}

bool AAOSPickupBase::TryCollect(AShellPawn* Shell)
{
	if (bCollected || !IsValid(Shell) || !ApplyPickup(Shell))
	{
		return false;
	}
	bCollected = true;

	Trigger->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetHiddenInGame(true);

	const FVector Where = Mesh->GetComponentLocation();
	if (CollectSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, CollectSound, Where);
	}
	BP_OnCollected(Shell);

	if (CollectFXTime <= 0.f)
	{
		Destroy();
		return true;
	}
	if (CollectFX)
	{
		if (UNiagaraComponent* FX = UNiagaraFunctionLibrary::SpawnSystemAttached(CollectFX, Trigger, NAME_None, FVector::ZeroVector,
			FRotator::ZeroRotator, EAttachLocation::KeepRelativeOffset, true))
		{
			if (!CollectFXRateParam.IsNone())
			{
				FX->SetVariableFloat(CollectFXRateParam, CollectFXRate);
			}
		}
	}
	CollectAge = 0.f;
	SetLifeSpan(CollectFXTime); // -> Destroy()
	return true;
}

void AAOSPickupBase::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bCollected)
	{
		// Light flash: x3 pop, then fade out over the VFX time.
		CollectAge += DeltaSeconds;
		const float T = FMath::Clamp(CollectAge / FMath::Max(CollectFXTime, 0.01f), 0.f, 1.f);
		Glow->SetIntensity(BaseLightIntensity * 3.f * (1.f - T) * (1.f - T));
		return;
	}

	Phase += DeltaSeconds * BobFrequency * UE_TWO_PI;
	if (Phase > UE_TWO_PI)
	{
		Phase -= UE_TWO_PI;
	}
	Mesh->SetRelativeLocation(MeshBaseLocation + FVector(0.f, 0.f, BobAmplitude * FMath::Sin(Phase)));
	Mesh->AddRelativeRotation(FRotator(0.f, SpinSpeed * DeltaSeconds, 0.f));
	Glow->SetIntensity(BaseLightIntensity * (0.85f + 0.15f * FMath::Sin(Phase * 2.f)));
}
