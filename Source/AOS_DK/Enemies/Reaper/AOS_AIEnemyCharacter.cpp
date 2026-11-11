#include "AOS_AIEnemyCharacter.h"
#include "AOS_AIController.h"
#include "AOS_AIWeapon.h"
#include "AOS_EvasionComponent.h"
#include "AOS_CombatThreatSubsystem.h"
#include "UI/AOS_RSSPageMapComponent.h"
#include "Anim/AOS_ReaperAnimInstance.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/DamageEvents.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraFunctionLibrary.h"
#include "Perception/AISense_Damage.h"
#include "UObject/ConstructorHelpers.h"

DEFINE_LOG_CATEGORY(LogAOSAI);

namespace
{
	int32 GNextReaperPID = 4700;
}

AAOS_AIEnemyCharacter::AAOS_AIEnemyCharacter()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;

	AIControllerClass = AAOS_AIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
	SetCanBeDamaged(true);
	Tags.AddUnique(TEXT("AOS.FuseTarget"));   // torpedo proximity fuse

	// Capsule: R 120, HH 135 (covers Z 0..270). The mesh origin (floor level) sits at -135.
	UCapsuleComponent* Capsule = GetCapsuleComponent();
	Capsule->InitCapsuleSize(120.f, 135.f);
	Capsule->SetCollisionProfileName(TEXT("Pawn"));

	USkeletalMeshComponent* SkelMesh = GetMesh();
	SkelMesh->SetRelativeLocation(FVector(0.f, 0.f, -135.f));
	SkelMesh->SetRelativeRotation(FRotator::ZeroRotator);   // authored forward = +X, no Mannequin -90
	SkelMesh->SetCollisionProfileName(TEXT("NoCollision"));  // the hit volume does the work
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MeshFinder(TEXT("/Game/AOS_DK_Game/Enemies/Reaper/Meshes/SK_OOMReaper.SK_OOMReaper"));
	if (MeshFinder.Succeeded())
	{
		SkelMesh->SetSkeletalMesh(MeshFinder.Object);
	}
	SkelMesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	SkelMesh->AnimClass = UAOS_ReaperAnimInstance::StaticClass();
	// Bones drive the eye point, arm origin and the weapon socket: keep them fresh even off screen.
	SkelMesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;

	// Whole-body hit volume: torpedoes (WorldDynamic sweeps), crosshair (Visibility) and the Shell hull block on it.
	HitVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("HitVolume"));
	HitVolume->SetupAttachment(Capsule);
	HitVolume->SetBoxExtent(FVector(210.f, 190.f, 100.f));
	HitVolume->SetRelativeLocation(FVector(0.f, 0.f, 10.f));
	HitVolume->SetCollisionEnabled(ECollisionEnabled::QueryOnly);   // profile "AOS_EnemyHitVolume"
	HitVolume->SetCollisionObjectType(ECC_WorldDynamic);
	HitVolume->SetCollisionResponseToAllChannels(ECR_Ignore);
	HitVolume->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
	HitVolume->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
	HitVolume->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
	HitVolume->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Block);
	HitVolume->SetCollisionResponseToChannel(ECC_Vehicle, ECR_Block);
	HitVolume->SetGenerateOverlapEvents(false);
	HitVolume->CanCharacterStepUpOn = ECB_No;

	Evasion = CreateDefaultSubobject<UAOS_EvasionComponent>(TEXT("Evasion"));

	PageMap = CreateDefaultSubobject<UAOS_RSSPageMapComponent>(TEXT("PageMap"));
	PageMap->SetupAttachment(SkelMesh, TEXT("SOCKET_UI_Health"));

	// Underwater walker: never swims, buoyant weight, heavy.
	UCharacterMovementComponent* Move = GetCharacterMovement();
	Move->DefaultLandMovementMode = MOVE_Walking;
	Move->DefaultWaterMovementMode = MOVE_Walking;
	Move->NavAgentProps.bCanSwim = false;
	Move->NavAgentProps.AgentRadius = 140.f;
	Move->NavAgentProps.AgentHeight = 280.f;
	Move->GravityScale = 0.55f;
	Move->GroundFriction = 6.f;
	Move->BrakingDecelerationWalking = 900.f;
	Move->MaxStepHeight = 60.f;
	Move->SetWalkableFloorAngle(35.f);
	Move->bOrientRotationToMovement = true;
	Move->RotationRate = FRotator(0.f, 120.f, 0.f);
	Move->MaxWalkSpeed = WalkSpeed;
	Move->MaxAcceleration = 900.f;
	Move->Mass = 2400.f;
	bUseControllerRotationYaw = false;

	WeaponClass = AAOS_AIWeapon::StaticClass();
	Health = MaxHealth;
}

void AAOS_AIEnemyCharacter::PostInitializeComponents()
{
	Super::PostInitializeComponents();
	PID = GNextReaperPID++;
}

AAOS_AIController* AAOS_AIEnemyCharacter::GetReaperController() const
{
	return Cast<AAOS_AIController>(GetController());
}

bool AAOS_AIEnemyCharacter::HasLineOfSightToTarget() const
{
	const AAOS_AIController* C = GetReaperController();
	return C && C->HasLineOfSight();
}

float AAOS_AIEnemyCharacter::GetSecondsSinceHeard() const
{
	const AAOS_AIController* C = GetReaperController();
	return C ? C->GetSecondsSinceHeard() : 1000.f;
}

void AAOS_AIEnemyCharacter::BeginPlay()
{
	Super::BeginPlay();
	SpawnTransform = GetActorTransform();   // the arena spawn point a respawn returns to
	Health = MaxHealth;
	ApplySpeed();

	if (UWorld* World = GetWorld())
	{
		FActorSpawnParameters Params;
		Params.Owner = this;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Weapon = World->SpawnActor<AAOS_AIWeapon>(WeaponClass ? WeaponClass.Get() : AAOS_AIWeapon::StaticClass(), GetActorTransform(), Params);
		if (Weapon)
		{
			Weapon->AttachToSocket(GetMesh(), WeaponSocketName);
			const float Measured = Weapon->GetTipDistance();
			if (!FMath::IsNearlyEqual(Measured, PikeTipDistance, 1.f))
			{
				UE_LOG(LogAOSAI, Warning, TEXT("oom_reaper[%d]: pike tip %.1f cm differs from PikeTipDistance %.1f cm"), PID, Measured, PikeTipDistance);
			}
		}
		else
		{
			UE_LOG(LogAOSAI, Error, TEXT("oom_reaper[%d]: failed to spawn the pike"), PID);
		}
	}
	if (PageMap)
	{
		PageMap->SetOwnerLabel(PID);
		PageMap->SetHealth(Health, MaxHealth);
	}
	UE_LOG(LogAOSAI, Log, TEXT("oom_reaper[%d]: online, %.0f HP, socket %s"), PID, MaxHealth, *WeaponSocketName.ToString());
}

// ---------------------------------------------------------------------------------------------------------------------
// Tick
// ---------------------------------------------------------------------------------------------------------------------
void AAOS_AIEnemyCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bDead)
	{
		DeathAlpha = FMath::Min(1.f, DeathAlpha + DeltaSeconds / 0.8f);
		return;
	}
	UpdateStrike(DeltaSeconds);
	UpdateHazardRamp(DeltaSeconds);
	UpdatePageMapAlert();
	SpotFlare = FMath::Max(0.f, SpotFlare - DeltaSeconds / 0.45f);

	// Fall safety: knocked off a roof edge for > 2 s -> back to the nearest patrol node (or spawn).
	if (GetCharacterMovement()->IsMovingOnGround())
	{
		OffGroundTime = 0.f;
	}
	else
	{
		OffGroundTime += DeltaSeconds;
		if (OffGroundTime > 2.f && PatrolNodes.Num() > 0)
		{
			AActor* Nearest = nullptr;
			float Best = TNumericLimits<float>::Max();
			for (AActor* Node : PatrolNodes)
			{
				const float D = Node ? FVector::DistSquared(Node->GetActorLocation(), GetActorLocation()) : TNumericLimits<float>::Max();
				if (D < Best) { Best = D; Nearest = Node; }
			}
			if (Nearest)
			{
				TeleportTo(Nearest->GetActorLocation() + FVector(0, 0, 150.f), GetActorRotation());
			}
			OffGroundTime = 0.f;
		}
	}
}

void AAOS_AIEnemyCharacter::SetPhase(EAOSReaperPhase NewPhase)
{
	if (bDead && NewPhase != EAOSReaperPhase::Dead)
	{
		return;
	}
	if (StrikeStage != EStrikeStage::None && NewPhase != EAOSReaperPhase::Dead && NewPhase != EAOSReaperPhase::StrikeWindup
		&& NewPhase != EAOSReaperPhase::StrikeThrust && NewPhase != EAOSReaperPhase::StrikeRecover)
	{
		return; // the strike owns the phase
	}
	Phase = NewPhase;
}

void AAOS_AIEnemyCharacter::UpdatePageMapAlert()
{
	if (!PageMap)
	{
		return;
	}
	EAOSPageAlert Alert = EAOSPageAlert::Patrol;
	if (IsInHazard())
	{
		Alert = EAOSPageAlert::Brine;
	}
	else
	{
		switch (Phase)
		{
		case EAOSReaperPhase::Investigate: Alert = EAOSPageAlert::Investigate; break;
		case EAOSReaperPhase::Chase:
		case EAOSReaperPhase::Shadow:
		case EAOSReaperPhase::StrikeWindup:
		case EAOSReaperPhase::StrikeThrust:
		case EAOSReaperPhase::StrikeRecover:
		case EAOSReaperPhase::Evading:     Alert = EAOSPageAlert::Combat; break;
		default: break;
		}
	}
	PageMap->SetAlert(Alert);
}

// ---------------------------------------------------------------------------------------------------------------------
// Locomotion
// ---------------------------------------------------------------------------------------------------------------------
void AAOS_AIEnemyCharacter::SetLocomotionMode(EAOSLocomotionMode Mode)
{
	LocomotionMode = Mode;
	ApplySpeed();
}

void AAOS_AIEnemyCharacter::ApplySpeed()
{
	UCharacterMovementComponent* Move = GetCharacterMovement();
	if (!Move)
	{
		return;
	}
	float Base = WalkSpeed;
	switch (LocomotionMode)
	{
	case EAOSLocomotionMode::Investigate: Base = InvestigateSpeed; break;
	case EAOSLocomotionMode::Scuttle:     Base = ScuttleSpeed; break;
	case EAOSLocomotionMode::Combat:      Base = CombatSpeed; break;
	default: break;
	}
	Move->MaxWalkSpeed = Base * HazardSpeedCurrent;
	Move->MaxAcceleration = LocomotionMode == EAOSLocomotionMode::Scuttle ? 1600.f : 900.f;
	const bool bCombat = LocomotionMode == EAOSLocomotionMode::Combat;
	Move->bUseControllerDesiredRotation = bCombat;
	Move->bOrientRotationToMovement = !bCombat;
	Move->RotationRate = FRotator(0.f, LocomotionMode == EAOSLocomotionMode::Scuttle ? 220.f : 120.f, 0.f);
}

EAOSGaitMode AAOS_AIEnemyCharacter::GetGaitMode() const
{
	if (bSkittering)
	{
		return EAOSGaitMode::Skitter;
	}
	if (IsInHazard() && HazardSpeedCurrent < 0.95f)
	{
		return EAOSGaitMode::Brine;
	}
	switch (LocomotionMode)
	{
	case EAOSLocomotionMode::Investigate: return EAOSGaitMode::Investigate;
	case EAOSLocomotionMode::Scuttle:     return EAOSGaitMode::Scuttle;
	default:                              return EAOSGaitMode::Walk;
	}
}

void AAOS_AIEnemyCharacter::NotifyFootPlanted(int32 Leg, const FVector& GroundLocation)
{
	UNiagaraSystem* FX = (IsInHazard() && BrineWadeFX) ? BrineWadeFX.Get() : SiltPuffFX.Get();
	if (FX && GetWorld() && GetVelocity().SizeSquared2D() > 25.f)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, FX, GroundLocation, FRotator::ZeroRotator, FVector(1.f), true, true, ENCPoolMethod::AutoRelease);
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Hazard (IAOS_HazardReceiver)
// ---------------------------------------------------------------------------------------------------------------------
void AAOS_AIEnemyCharacter::EnterHazard_Implementation(AActor* Source, const FAOSHazardParams& Params)
{
	if (bDead || !Source)
	{
		return;
	}
	const bool bFirst = ActiveHazards.Num() == 0;
	ActiveHazards.Add(Source, Params);
	RecomputeHazards();
	if (bFirst)
	{
		ReportToShell(TEXT("heap brine - traction lost"), EAOSHudLogSeverity::Info);
	}
}

void AAOS_AIEnemyCharacter::ExitHazard_Implementation(AActor* Source)
{
	if (ActiveHazards.Remove(Source) > 0)
	{
		RecomputeHazards();
		if (ActiveHazards.Num() == 0)
		{
			ReportToShell(TEXT("traction restored"), EAOSHudLogSeverity::Info);
		}
	}
}

void AAOS_AIEnemyCharacter::RecomputeHazards()
{
	// min over the active hazards (not the product).
	float Speed = 1.f, Sight = 1.f, Angle = 180.f, Dodge = 1.f;
	bool bBlockRegen = false;
	for (const TPair<TWeakObjectPtr<AActor>, FAOSHazardParams>& Pair : ActiveHazards)
	{
		Speed = FMath::Min(Speed, Pair.Value.SpeedScale);
		Sight = FMath::Min(Sight, Pair.Value.SightRadiusScale);
		Angle = FMath::Min(Angle, Pair.Value.SightHalfAngle);
		Dodge = FMath::Min(Dodge, Pair.Value.DodgeScale);
		bBlockRegen |= Pair.Value.bBlockDecoyRegen;
	}
	HazardSpeedTarget = Speed;
	if (AAOS_AIController* C = GetReaperController())
	{
		if (ActiveHazards.Num() > 0) { C->SetSightDegradation(Sight, Angle); }
		else { C->ResetSightDegradation(); }
	}
	if (Evasion)
	{
		Evasion->SetHazardScale(Dodge);
		Evasion->SetChargeRegenPaused(bBlockRegen);
	}
	if (AAOS_AIController* C = GetReaperController())
	{
		if (UBlackboardComponent* BB = C->GetBlackboardComponent())
		{
			BB->SetValueAsBool(AOSReaperBB::bInHazard, ActiveHazards.Num() > 0);
		}
	}
}

void AAOS_AIEnemyCharacter::UpdateHazardRamp(float Dt)
{
	if (FMath::IsNearlyEqual(HazardSpeedCurrent, HazardSpeedTarget, 0.001f))
	{
		return;
	}
	const bool bEntering = HazardSpeedTarget < HazardSpeedCurrent;
	const float Rate = FMath::Max(0.05f, 1.f - FMath::Min(HazardSpeedTarget, HazardSpeedCurrent)) / (bEntering ? HazardRampIn : HazardRampOut);
	HazardSpeedCurrent = FMath::FInterpConstantTo(HazardSpeedCurrent, HazardSpeedTarget, Dt, Rate);
	ApplySpeed();
}

// ---------------------------------------------------------------------------------------------------------------------
// Damage / death
// ---------------------------------------------------------------------------------------------------------------------
float AAOS_AIEnemyCharacter::TakeDamage(float DamageAmount, FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser)
{
	if (bDead || DamageAmount <= 0.f)
	{
		return 0.f;
	}
	const float Applied = Super::TakeDamage(DamageAmount, DamageEvent, EventInstigator, DamageCauser);
	if (Applied <= 0.f)
	{
		return 0.f;
	}
	Health = FMath::Max(0.f, Health - Applied);
	if (PageMap)
	{
		PageMap->SetHealth(Health, MaxHealth);
		const int32 Pages = PageMap->GetResidentPages();
		if (Pages < LastReportedPages && Health > 0.f && Health / MaxHealth < 0.25f)
		{
			UE_LOG(LogAOSAI, Log, TEXT("oom_reaper[%d]: RSS %d/16 pages resident"), PID, Pages);
		}
		LastReportedPages = Pages;
	}

	if (APawn* Shooter = UGameplayStatics::GetPlayerPawn(this, 0))
	{
		UAISense_Damage::ReportDamageEvent(this, this, Shooter, Applied, Shooter->GetActorLocation(), GetActorLocation());
	}
	if (Health <= 0.f)
	{
		Die();
	}
	return Applied;
}

void AAOS_AIEnemyCharacter::Die()
{
	if (bDead)
	{
		return;
	}
	bDead = true;
	Phase = EAOSReaperPhase::Dead;
	StrikeStage = EStrikeStage::None;

	if (AAOS_AIController* C = GetReaperController())
	{
		C->ShutDown();
	}
	GetCharacterMovement()->DisableMovement();
	GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	if (HitVolume)
	{
		HitVolume->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	}
	if (Weapon)
	{
		Weapon->DropWithPhysics();
	}
	if (PageMap)
	{
		PageMap->PlayDeathRelease();
	}
	if (PageReleaseFX)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, PageReleaseFX, GetActorLocation(), FRotator::ZeroRotator, FVector(1.f), true, true, ENCPoolMethod::AutoRelease);
	}
	ReportToShell(TEXT("reaped (exit 137)"), EAOSHudLogSeverity::Info);
	BP_OnDied();
	if (bAutoRespawn && GetWorld())
	{
		GetWorldTimerManager().SetTimer(RespawnTimer, this, &AAOS_AIEnemyCharacter::Respawn, FMath::Max(RespawnDelay, 0.01f), false);
		SetLifeSpan(FMath::Max(10.f, RespawnDelay + 2.f));   // the corpse must outlive its respawn timer
		UE_LOG(LogAOSAI, Log, TEXT("oom_reaper[%d]: respawn in %.1f s"), PID, RespawnDelay);
	}
	else
	{
		SetLifeSpan(10.f);
	}
}

void AAOS_AIEnemyCharacter::Respawn()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	AAOS_AIEnemyCharacter* Fresh = World->SpawnActorDeferred<AAOS_AIEnemyCharacter>(GetClass(), SpawnTransform, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
	if (!Fresh)
	{
		UE_LOG(LogAOSAI, Error, TEXT("oom_reaper[%d]: respawn failed"), PID);
		return;
	}
	Fresh->PatrolNodes = PatrolNodes;
	Fresh->HomeRadius = HomeRadius;
	Fresh->bAutoRespawn = bAutoRespawn;
	Fresh->RespawnDelay = RespawnDelay;
	Fresh->FinishSpawning(SpawnTransform);   // BeginPlay: full health, fresh evasion charges, new pike, AI controller + BT
	UE_LOG(LogAOSAI, Log, TEXT("oom_reaper[%d]: respawned as oom_reaper[%d] at (%.0f, %.0f, %.0f)"), PID, Fresh->PID,
		SpawnTransform.GetLocation().X, SpawnTransform.GetLocation().Y, SpawnTransform.GetLocation().Z);
}

void AAOS_AIEnemyCharacter::ReportToShell(const FString& Message, EAOSHudLogSeverity Severity)
{
	const FString Source = FString::Printf(TEXT("oom_reaper[%d]"), PID);
	UE_LOG(LogAOSAI, Log, TEXT("%s: %s"), *Source, *Message);
	if (AShellPawn* Shell = Cast<AShellPawn>(UGameplayStatics::GetPlayerPawn(this, 0)))
	{
		Shell->PushTerminalLog(Source, Message, Severity);
	}
}

void AAOS_AIEnemyCharacter::PlaySpotReaction()
{
	SpotFlare = 1.f;
	BP_OnSpotted();
}

// ---------------------------------------------------------------------------------------------------------------------
// Strike
// ---------------------------------------------------------------------------------------------------------------------
bool AAOS_AIEnemyCharacter::CanStrike() const
{
	return !bDead && StrikeStage == EStrikeStage::None && Weapon && !bSkittering
		&& GetWorld() && GetWorld()->GetTimeSeconds() - LastStrikeEndTime >= StrikeCooldown;
}

FVector AAOS_AIEnemyCharacter::GetArmTurretLocation() const
{
	const USkeletalMeshComponent* SkelMesh = GetMesh();
	if (SkelMesh && SkelMesh->GetBoneIndex(ArmTurretBone) != INDEX_NONE)
	{
		return SkelMesh->GetBoneLocation(ArmTurretBone, EBoneSpaces::WorldSpace);
	}
	return GetActorLocation() + GetActorForwardVector() * -40.f + FVector(0, 0, 60.f);
}

bool AAOS_AIEnemyCharacter::RequestStrike(const AShellPawn* Shell, const FVector& ClosestHullPoint)
{
	if (!Shell || !CanStrike())
	{
		return false;
	}
	StrikeTarget = ClosestHullPoint;
	StrikeDir = (ClosestHullPoint - GetArmTurretLocation()).GetSafeNormal();   // line is committed at wind-up
	StrikeStage = EStrikeStage::Windup;
	StageTime = 0.f;
	bStrikeHitReported = false;
	Phase = EAOSReaperPhase::StrikeWindup;
	ShellTarget = Shell;
	GetCharacterMovement()->StopMovementImmediately();
	return true;
}

void AAOS_AIEnemyCharacter::AbortStrike()
{
	if (StrikeStage == EStrikeStage::None)
	{
		return;
	}
	if (Weapon)
	{
		Weapon->EndSwing();
	}
	StrikeStage = EStrikeStage::None;
	LastStrikeEndTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
}

void AAOS_AIEnemyCharacter::UpdateStrike(float Dt)
{
	if (StrikeStage == EStrikeStage::None)
	{
		return;
	}
	StageTime += Dt;
	switch (StrikeStage)
	{
	case EStrikeStage::Windup:
		if (StageTime >= WindupTime)
		{
			StrikeStage = EStrikeStage::Thrust;
			StageTime = 0.f;
			Phase = EAOSReaperPhase::StrikeThrust;
			if (Weapon) { Weapon->BeginSwing(GetController()); }
		}
		break;
	case EStrikeStage::Thrust:
		if (Weapon && Weapon->HasHitThisSwing() && !bStrikeHitReported)
		{
			bStrikeHitReported = true;
			ReportToShell(TEXT("SIGKILL arc - core -5%"), EAOSHudLogSeverity::Damage);
		}
		if (StageTime >= ThrustTime)
		{
			StrikeStage = EStrikeStage::Recover;
			StageTime = 0.f;
			Phase = EAOSReaperPhase::StrikeRecover;
			if (Weapon) { Weapon->EndSwing(); }
		}
		break;
	case EStrikeStage::Recover:
		if (StageTime >= RecoverTime)
		{
			StrikeStage = EStrikeStage::None;
			LastStrikeEndTime = GetWorld()->GetTimeSeconds();
			Phase = EAOSReaperPhase::Chase;
		}
		break;
	default:
		break;
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Mast / arm / jaws (game-thread inputs of the procedural animation)
// ---------------------------------------------------------------------------------------------------------------------
void AAOS_AIEnemyCharacter::SetShellTarget(const AShellPawn* Shell)
{
	ShellTarget = Shell;
}

void AAOS_AIEnemyCharacter::SetMastLookPoint(const FVector& WorldPoint)
{
	MastLookPoint = WorldPoint;
	MastLookExpire = GetWorld() ? GetWorld()->GetTimeSeconds() + 2.0 : 0.0;
}

bool AAOS_AIEnemyCharacter::GetMastLookPoint(FVector& OutWorldPoint) const
{
	if (const AShellPawn* Shell = ShellTarget.Get())
	{
		OutWorldPoint = Shell->GetActorLocation();
		return true;
	}
	if (GetWorld() && GetWorld()->GetTimeSeconds() < MastLookExpire)
	{
		OutWorldPoint = MastLookPoint;
		return true;
	}
	return false;
}

float AAOS_AIEnemyCharacter::GetArmCommand(FVector& OutTipWorld, FVector& OutDirWorld, float& OutTipSpeed) const
{
	if (bDead)
	{
		return 0.f;
	}
	const FVector A = GetArmTurretLocation();
	auto Clamped = [&](const FVector& Tip)
	{
		const FVector D = Tip - A;
		return D.SizeSquared() > FMath::Square(MaxTipReach) ? A + D.GetSafeNormal() * MaxTipReach : Tip;
	};

	switch (StrikeStage)
	{
	case EStrikeStage::Windup:
		OutDirWorld = StrikeDir;
		OutTipWorld = Clamped(StrikeTarget - StrikeDir * 80.f);   // pike drawn back 80 cm short of the hull
		OutTipSpeed = 300.f;
		return 1.f;
	case EStrikeStage::Thrust:
		OutDirWorld = StrikeDir;
		OutTipWorld = Clamped(StrikeTarget + StrikeDir * 40.f);
		OutTipSpeed = 900.f;
		return 1.f;
	case EStrikeStage::Recover:
	{
		const AShellPawn* Shell = ShellTarget.Get();
		OutDirWorld = Shell ? (Shell->GetActorLocation() - A).GetSafeNormal() : StrikeDir;
		OutTipWorld = A + OutDirWorld * 300.f;
		OutTipSpeed = 250.f;
		return 1.f;
	}
	default:
		break;
	}

	// Guard pose: pike levelled on the hull while hunting / shadowing.
	if (const AShellPawn* Shell = ShellTarget.Get())
	{
		if (Phase == EAOSReaperPhase::Chase || Phase == EAOSReaperPhase::Shadow || Phase == EAOSReaperPhase::Evading)
		{
			OutDirWorld = (Shell->GetActorLocation() - A).GetSafeNormal();
			OutTipWorld = A + OutDirWorld * 300.f;
			OutTipSpeed = 400.f;
			return 1.f;
		}
	}
	return 0.f;   // stowed along the back
}

float AAOS_AIEnemyCharacter::GetJawOpenTarget() const
{
	if (bDead)
	{
		return 10.f;
	}
	switch (StrikeStage)
	{
	case EStrikeStage::Windup: return 35.f;   // telegraph
	case EStrikeStage::Thrust: return 35.f;
	default: break;
	}
	return SpotFlare > 0.f ? 30.f * SpotFlare : 0.f;
}

void AAOS_AIEnemyCharacter::GetActorEyesViewPoint(FVector& OutLocation, FRotator& OutRotation) const
{
	const USkeletalMeshComponent* SkelMesh = GetMesh();
	if (SkelMesh && SkelMesh->GetBoneIndex(SensorBone) != INDEX_NONE)
	{
		const FQuat Q = SkelMesh->GetBoneQuaternion(SensorBone, EBoneSpaces::WorldSpace);
		OutRotation = Q.Rotator();
		OutLocation = SkelMesh->GetBoneLocation(SensorBone, EBoneSpaces::WorldSpace) + Q.GetForwardVector() * 18.f;
		return;
	}
	Super::GetActorEyesViewPoint(OutLocation, OutRotation);
}
