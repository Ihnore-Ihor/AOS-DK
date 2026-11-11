#include "AOS_AIWeapon.h"
#include "AOS_ReaperTypes.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Engine/DamageEvents.h"
#include "GameFramework/DamageType.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraFunctionLibrary.h"
#include "UObject/ConstructorHelpers.h"

AAOS_AIWeapon::AAOS_AIWeapon()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;

	PikeMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PikeMesh"));
	RootComponent = PikeMesh;
	PikeMesh->SetCollisionProfileName(TEXT("NoCollision"));
	PikeMesh->SetGenerateOverlapEvents(false);
	PikeMesh->SetCastShadow(true);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> MeshFinder(TEXT("/Game/AOS_DK_Game/Enemies/Reaper/Meshes/SM_WPN_SigkillPike.SM_WPN_SigkillPike"));
	if (MeshFinder.Succeeded())
	{
		PikeMesh->SetStaticMesh(MeshFinder.Object);
	}
	DamageTypeClass = UDamageType::StaticClass();
}

void AAOS_AIWeapon::AttachToSocket(USceneComponent* Parent, FName ParentSocket)
{
	if (!Parent)
	{
		return;
	}
	// The pike pivot is the mount collar (SOCKET_Mount_Base at the origin), so snapping the actor root puts the collar in the wrist jaws.
	AttachToComponent(Parent, FAttachmentTransformRules::SnapToTargetNotIncludingScale, ParentSocket);
}

void AAOS_AIWeapon::DropWithPhysics()
{
	EndSwing();
	DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
	if (PikeMesh)
	{
		PikeMesh->SetCollisionProfileName(TEXT("PhysicsActor"));
		PikeMesh->SetSimulatePhysics(true);
		PikeMesh->SetLinearDamping(2.f);   // water drag
		PikeMesh->SetAngularDamping(2.f);
		PikeMesh->SetMassOverrideInKg(NAME_None, 38.f, true);
	}
	SetLifeSpan(10.f);
}

float AAOS_AIWeapon::GetTipDistance() const
{
	if (PikeMesh && PikeMesh->GetStaticMesh() && PikeMesh->DoesSocketExist(TraceEndSocket))
	{
		return static_cast<float>(PikeMesh->GetSocketTransform(TraceEndSocket, RTS_Component).GetLocation().X);
	}
	return 262.f;
}

bool AAOS_AIWeapon::GetTraceSegment(FVector& OutStart, FVector& OutEnd) const
{
	if (!PikeMesh)
	{
		return false;
	}
	if (PikeMesh->DoesSocketExist(TraceStartSocket) && PikeMesh->DoesSocketExist(TraceEndSocket))
	{
		OutStart = PikeMesh->GetSocketLocation(TraceStartSocket);
		OutEnd = PikeMesh->GetSocketLocation(TraceEndSocket);
		return true;
	}
	// Fallback: authored values (X 170 -> 262 along the pike axis).
	OutStart = PikeMesh->GetComponentTransform().TransformPosition(FVector(170.f, 0.f, 0.f));
	OutEnd = PikeMesh->GetComponentTransform().TransformPosition(FVector(262.f, 0.f, 0.f));
	return true;
}

void AAOS_AIWeapon::BeginSwing(AController* InInstigatorController)
{
	InstigatorController = InInstigatorController;
	bSwinging = true;
	bHitThisSwing = false;
	bHavePrevSegment = false;
	SetActorTickEnabled(true);
}

void AAOS_AIWeapon::EndSwing()
{
	bSwinging = false;
	bHavePrevSegment = false;
	SetActorTickEnabled(false);
}

void AAOS_AIWeapon::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bSwinging && !bHitThisSwing)
	{
		SweepStrike();
	}
}

void AAOS_AIWeapon::SweepStrike()
{
	UWorld* World = GetWorld();
	FVector Start, End;
	if (!World || !GetTraceSegment(Start, End))
	{
		return;
	}

	FCollisionQueryParams Params(SCENE_QUERY_STAT(ReaperPikeSweep), false, this);
	if (AActor* Wielder = GetAttachParentActor())
	{
		Params.AddIgnoredActor(Wielder);
	}
	FCollisionObjectQueryParams Objects;
	Objects.AddObjectTypesToQuery(ECC_Pawn);
	Objects.AddObjectTypesToQuery(ECC_Vehicle);
	Objects.AddObjectTypesToQuery(ECC_PhysicsBody);
	Objects.AddObjectTypesToQuery(ECC_WorldDynamic);
	const FCollisionShape Sphere = FCollisionShape::MakeSphere(SweepRadius);

	TArray<FHitResult> Hits;
	// Current segment: tip-to-collar sweep covers the whole pike, so a target between the sockets is hit as well.
	World->SweepMultiByObjectType(Hits, Start, End, FQuat::Identity, Objects, Sphere, Params);
	if (bHavePrevSegment)
	{
		// Anti-tunnelling: both ends travel from last frame's positions to this frame's.
		TArray<FHitResult> TipHits;
		World->SweepMultiByObjectType(TipHits, PrevEnd, End, FQuat::Identity, Objects, Sphere, Params);
		Hits.Append(TipHits);
		TArray<FHitResult> BaseHits;
		World->SweepMultiByObjectType(BaseHits, PrevStart, Start, FQuat::Identity, Objects, Sphere, Params);
		Hits.Append(BaseHits);
	}
	PrevStart = Start;
	PrevEnd = End;
	bHavePrevSegment = true;

	for (const FHitResult& Hit : Hits)
	{
		AShellPawn* Shell = Cast<AShellPawn>(Hit.GetActor());
		if (!Shell)
		{
			continue;
		}
		const FVector Dir = (End - Start).GetSafeNormal();
		FHitResult Impact = Hit;
		if (Impact.ImpactPoint.IsNearlyZero())
		{
			Impact.ImpactPoint = End;
		}
		UGameplayStatics::ApplyPointDamage(Shell, StrikeDamagePercent, Dir, Impact, InstigatorController.Get(), this,
			DamageTypeClass ? DamageTypeClass : TSubclassOf<UDamageType>(UDamageType::StaticClass()));
		bHitThisSwing = true; // one hit per thrust
		if (ImpactFX)
		{
			UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, ImpactFX, Impact.ImpactPoint, Dir.Rotation(), FVector(1.f), true, true, ENCPoolMethod::AutoRelease);
		}
		BP_OnPikeHit(Impact);
		UE_LOG(LogAOSAI, Verbose, TEXT("SIGKILL arc hit: %s (%.1f %%)"), *Shell->GetName(), StrikeDamagePercent);
		break;
	}
}
