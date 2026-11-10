#include "AOSCableTangle.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "Engine/DamageEvents.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraFunctionLibrary.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "AOS_DK/Environment/Physics/AOSFluidPhysicsComponent.h"

DEFINE_LOG_CATEGORY_STATIC(LogAOSTangle, Log, All);

namespace AOSTangle
{
	static const FName ProfileName(TEXT("AOS_SoftFoliage"));
	static const FName FuseTag(TEXT("AOS.FuseTarget"));
}

AAOSCableTangle::AAOSCableTangle()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;
	PrimaryActorTick.TickGroup = TG_PrePhysics;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	SetRootComponent(Mesh);
	Mesh->SetMobility(EComponentMobility::Static);
	Mesh->SetCollisionProfileName(AOSTangle::ProfileName);
	Mesh->SetGenerateOverlapEvents(true);
	Mesh->SetCanEverAffectNavigation(false);
	Mesh->CastShadow = true;

	SetCanBeDamaged(true);
	Tags.AddUnique(AOSTangle::FuseTag);
}

void AAOSCableTangle::BeginPlay()
{
	Super::BeginPlay();
	Integrity = MaxIntegrity;
	Mesh->OnComponentBeginOverlap.AddDynamic(this, &AAOSCableTangle::HandleBeginOverlap);

	// A Shell already inside at spawn is snagged too.
	TArray<AActor*> Overlapping;
	Mesh->GetOverlappingActors(Overlapping, AShellPawn::StaticClass());
	if (Overlapping.Num() > 0)
	{
		Entangle(Cast<AShellPawn>(Overlapping[0]));
	}
}

void AAOSCableTangle::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	EntangledShell.Reset();
	Super::EndPlay(EndPlayReason);
}

void AAOSCableTangle::HandleBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
	int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	if (AShellPawn* Shell = Cast<AShellPawn>(OtherActor))
	{
		Entangle(Shell);
	}
}

UPrimitiveComponent* AAOSCableTangle::GetShellBody() const
{
	const AShellPawn* Shell = EntangledShell.Get();
	return Shell ? Cast<UPrimitiveComponent>(Shell->GetRootComponent()) : nullptr;
}

void AAOSCableTangle::Entangle(AShellPawn* Shell)
{
	if (bSevered || !Shell || EntangledShell.IsValid())
	{
		return;
	}
	const double Now = GetWorld()->GetTimeSeconds();
	if (CooldownShell.Get() == Shell && Now < CooldownUntil)
	{
		return;
	}

	EntangledShell = Shell;
	EntangleTimeLeft = EntangleDuration;

	// Extra linear drag k so that, against the Shell's own linear water drag d, the thrust-limited
	// steady-state speed is scaled by (1 - f):  v' = T / (d + k) = (1 - f) * T / d  ->  k = d * f / (1 - f).
	const float F = FMath::Clamp(VelocityDamping, 0.f, 0.95f);
	const UAOSFluidPhysicsComponent* Fluid = Shell->GetFluidPhysics();
	const float OwnDrag = Fluid ? FMath::Max(Fluid->FluidDrag, 0.1f) : 1.f;
	ExtraDragRate = OwnDrag * F / (1.f - F);

	if (UPrimitiveComponent* Body = GetShellBody())
	{
		if (Body->IsSimulatingPhysics())
		{
			Body->SetPhysicsLinearVelocity(Body->GetPhysicsLinearVelocity() * (1.f - F));
			Body->SetPhysicsAngularVelocityInRadians(Body->GetPhysicsAngularVelocityInRadians() * (1.f - F));
		}
	}
	SetActorTickEnabled(true);

	if (SnagSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, SnagSound, Shell->GetActorLocation());
	}
	Shell->PushTerminalLog(TEXT("hull"), FString::Printf(TEXT("entangled - velocity -%d%% for %.1f s (torpedoes clear it)"),
		FMath::RoundToInt(F * 100.f), EntangleDuration), EAOSHudLogSeverity::Warning);
	UE_LOG(LogAOSTangle, Log, TEXT("%s snagged %s (k=%.2f/s, %.1f s)"), *GetName(), *Shell->GetName(), ExtraDragRate, EntangleDuration);
	BP_OnEntangled(Shell);
}

void AAOSCableTangle::Release(bool bByTorpedo)
{
	AShellPawn* Shell = EntangledShell.Get();
	EntangledShell.Reset();
	EntangleTimeLeft = 0.f;
	SetActorTickEnabled(false);
	if (!Shell)
	{
		return;
	}
	CooldownShell = Shell;
	CooldownUntil = GetWorld()->GetTimeSeconds() + ReentangleCooldown;
	if (!bByTorpedo)
	{
		Shell->PushTerminalLog(TEXT("hull"), TEXT("tangle slipped - drive nominal"), EAOSHudLogSeverity::Info);
	}
	BP_OnReleased(Shell);
}

void AAOSCableTangle::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UPrimitiveComponent* Body = GetShellBody();
	if (!Body)
	{
		Release(false);
		return;
	}
	if (Body->IsSimulatingPhysics())
	{
		const FVector V = Body->GetPhysicsLinearVelocity();
		// Never reverse the velocity within one frame (stable for any dt).
		const float Rate = FMath::Min(ExtraDragRate, 1.f / FMath::Max(DeltaSeconds, KINDA_SMALL_NUMBER));
		Body->AddForce(-V * Rate, NAME_None, /*bAccelChange*/ true);
	}

	EntangleTimeLeft -= DeltaSeconds;
	if (EntangleTimeLeft <= 0.f)
	{
		Release(false);
	}
}

float AAOSCableTangle::TakeDamage(float DamageAmount, FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser)
{
	const float Applied = Super::TakeDamage(DamageAmount, DamageEvent, EventInstigator, DamageCauser);
	if (bSevered || Applied <= 0.f)
	{
		return Applied;
	}
	Integrity -= Applied;
	if (Integrity <= 0.f)
	{
		Sever(DamageCauser);
	}
	return Applied;
}

void AAOSCableTangle::Sever(AActor* Cause)
{
	if (bSevered)
	{
		return;
	}
	bSevered = true;
	Integrity = 0.f;

	AShellPawn* Shell = EntangledShell.Get();
	if (!Shell)
	{
		Shell = Cast<AShellPawn>(UGameplayStatics::GetPlayerPawn(this, 0));
	}
	Release(true);
	if (Shell)
	{
		Shell->PushTerminalLog(TEXT("attacker"), TEXT("cable tangle severed - passage clear"), EAOSHudLogSeverity::System);
	}

	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetHiddenInGame(true);
	Tags.Remove(AOSTangle::FuseTag);
	SetCanBeDamaged(false);

	const FVector Center = Mesh->Bounds.Origin;
	if (SeverFX)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, SeverFX, Center, FRotator::ZeroRotator, FVector(1.f), true, true, ENCPoolMethod::AutoRelease);
	}
	if (SeverSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, SeverSound, Center);
	}
	BP_OnSevered(Cause);
	Destroy();
}
