#include "AOS_CavitationDecoy.h"
#include "Components/SphereComponent.h"
#include "NiagaraFunctionLibrary.h"

AAOS_CavitationDecoy::AAOS_CavitationDecoy()
{
	PrimaryActorTick.bCanEverTick = false;
	SetCanBeDamaged(true);
	Tags.AddUnique(TEXT("AOS.FuseTarget"));

	Sphere = CreateDefaultSubobject<USphereComponent>(TEXT("Sphere"));
	RootComponent = Sphere;
	Sphere->InitSphereRadius(Radius);
	// "AOS_Decoy": only torpedo sweeps (WorldDynamic) hit it.
	Sphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Sphere->SetCollisionObjectType(ECC_WorldDynamic);
	Sphere->SetCollisionResponseToAllChannels(ECR_Ignore);
	Sphere->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
	Sphere->SetGenerateOverlapEvents(false);
}

void AAOS_CavitationDecoy::Activate(float InLifetime)
{
	Lifetime = InLifetime > 0.f ? InLifetime : Lifetime;
	Sphere->SetSphereRadius(Radius);
	SetLifeSpan(Lifetime);
	if (BloomFX)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, BloomFX, GetActorLocation(), GetActorRotation(), FVector(1.f), true, true, ENCPoolMethod::AutoRelease);
	}
	BP_OnActivated();
}

float AAOS_CavitationDecoy::TakeDamage(float DamageAmount, FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser)
{
	return 0.f; // absorbs the torpedo, takes no damage
}
