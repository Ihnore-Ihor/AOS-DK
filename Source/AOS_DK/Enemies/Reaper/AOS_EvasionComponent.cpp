#include "AOS_EvasionComponent.h"
#include "AOS_AIEnemyCharacter.h"
#include "AOS_CavitationDecoy.h"
#include "AOS_CombatThreatSubsystem.h"
#include "UI/AOS_RSSPageMapComponent.h"
#include "AOS_DK/Submarine/Subdrones/Attacker/MicroTorpedo.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Math/RandomStream.h"
#include "NavigationSystem.h"
#include "TimerManager.h"

static TAutoConsoleVariable<int32> CVarForceDodge(TEXT("aos.ai.ForceDodge"), -1,
	TEXT("-1 = model, 0 = never dodge, 1 = always dodge (still subject to charges, cooldown and clearance)."));

namespace
{
	/** 32-bit avalanche mix. FRandomStream(Seed) maps consecutive seeds to near-linear first outputs (+0.0457 per +1), so PID * 7919 + SalvoId
	 *  made u climb in steps of ~0.05 per salvo: runs of identical outcomes instead of independent rolls. Hash before seeding. */
	uint32 AOSMix32(uint32 X)
	{
		X ^= X >> 16; X *= 0x7feb352dU;
		X ^= X >> 15; X *= 0x846ca68bU;
		X ^= X >> 16;
		return X;
	}

	/** Monte-Carlo check of the analytic base law: aos.ai.DodgeMonteCarlo [N]. */
	void RunDodgeMonteCarlo(const TArray<FString>& Args)
	{
		const int32 N = Args.Num() > 0 ? FMath::Max(100, FCString::Atoi(*Args[0])) : 10000;
		UE_LOG(LogAOSAI, Log, TEXT("aos.ai.DodgeMonteCarlo N=%d  (seeded rolls of the base law)"), N);
		bool bAllPass = true;
		TArray<float> Distances;
		for (float D = 400.f; D < 2500.f; D += 250.f) { Distances.Add(D); }
		Distances.Add(2500.f);
		int32 Row = 0;
		for (const float DistCm : Distances)
		{
			const double P = UAOS_EvasionComponent::ComputeBaseProbability(DistCm);
			FRandomStream Stream(4700 * 7919 + (++Row) * 131);
			int32 Hits = 0;
			for (int32 i = 0; i < N; ++i)
			{
				Hits += Stream.FRand() < P ? 1 : 0;
			}
			const double Emp = static_cast<double>(Hits) / N;
			const double Sigma = FMath::Sqrt(FMath::Max(P * (1.0 - P), 1e-9) / N);
			const bool bPass = FMath::Abs(Emp - P) <= 3.0 * Sigma + 1e-9;
			bAllPass &= bPass;
			UE_LOG(LogAOSAI, Log, TEXT("  D=%5.1f m  analytic=%.4f  empirical=%.4f  |d|=%.4f  3sigma=%.4f  %s"),
				DistCm / 100.0, P, Emp, FMath::Abs(Emp - P), 3.0 * Sigma, bPass ? TEXT("PASS") : TEXT("FAIL"));
		}
		UE_LOG(LogAOSAI, Log, TEXT("aos.ai.DodgeMonteCarlo: %s"), bAllPass ? TEXT("PASS") : TEXT("FAIL"));
	}

	FAutoConsoleCommand GDodgeMonteCarloCmd(TEXT("aos.ai.DodgeMonteCarlo"), TEXT("Monte-Carlo check of the Reaper dodge law."),
		FConsoleCommandWithArgsDelegate::CreateStatic(&RunDodgeMonteCarlo));
}

UAOS_EvasionComponent::UAOS_EvasionComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.1f;
	DecoyClass = AAOS_CavitationDecoy::StaticClass();
}

void UAOS_EvasionComponent::BeginPlay()
{
	Super::BeginPlay();
	Charges = MaxCharges;
	if (UAOS_CombatThreatSubsystem* Threats = GetWorld() ? GetWorld()->GetSubsystem<UAOS_CombatThreatSubsystem>() : nullptr)
	{
		Threats->RegisterEvasion(this);
	}
	PushPageMap();
}

AAOS_AIEnemyCharacter* UAOS_EvasionComponent::GetReaper() const
{
	return Cast<AAOS_AIEnemyCharacter>(GetOwner());
}

// ---------------------------------------------------------------------------------------------------------------------
float UAOS_EvasionComponent::ComputeBaseProbability(float DistanceCm)
{
	// Defaults of the spec: D_pb 400, D_far 2500, P_min 0.05, P_max 0.80, k = 0.75 / 2100 = 3.571e-4 per cm.
	const UAOS_EvasionComponent* Defaults = GetDefault<UAOS_EvasionComponent>();
	if (DistanceCm < Defaults->ReactionGateDistance)
	{
		return 0.f;
	}
	const float K = (Defaults->MaxProbability - Defaults->MinProbability) / (Defaults->FarDistance - Defaults->PointBlankDistance);
	return FMath::Clamp(Defaults->MinProbability + K * (DistanceCm - Defaults->PointBlankDistance), Defaults->MinProbability, Defaults->MaxProbability);
}

float UAOS_EvasionComponent::ComputeAwareness() const
{
	const AAOS_AIEnemyCharacter* Reaper = GetReaper();
	if (!Reaper)
	{
		return 0.2f;
	}
	if (Reaper->HasLineOfSightToTarget())
	{
		return 1.f;
	}
	return Reaper->GetSecondsSinceHeard() <= 3.f ? 0.5f : 0.2f;
}

float UAOS_EvasionComponent::ComputeStateFactor() const
{
	const AAOS_AIEnemyCharacter* Reaper = GetReaper();
	switch (Reaper ? Reaper->GetPhase() : EAOSReaperPhase::Patrol)
	{
	case EAOSReaperPhase::StrikeWindup:  return 0.3f;
	case EAOSReaperPhase::StrikeThrust:  return 0.f;
	case EAOSReaperPhase::StrikeRecover: return 0.5f;
	case EAOSReaperPhase::Evading:
	case EAOSReaperPhase::Dead:          return 0.f;
	default:                             return 1.f;
	}
}

float UAOS_EvasionComponent::ComputeFatigue() const
{
	const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	int32 N = 0;
	for (const double T : RecentDodges)
	{
		N += (Now - T <= FatigueWindow) ? 1 : 0;
	}
	return FMath::Pow(FatigueBase, static_cast<float>(N));
}

float UAOS_EvasionComponent::ComputeDodgeProbability(float DistanceCm) const
{
	const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	if (Charges <= 0 || Now - LastDodgeTime < DodgeCooldown || bEvading)
	{
		return 0.f;
	}
	const float P = ComputeBaseProbability(DistanceCm) * ComputeAwareness() * ComputeStateFactor() * ComputeFatigue() * HazardScale;
	return FMath::Clamp(P, 0.f, MaxProbability);
}

float UAOS_EvasionComponent::GetReadiness() const
{
	const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	if (Charges <= 0)
	{
		return 0.f;
	}
	return DodgeCooldown > 0.f ? FMath::Clamp(static_cast<float>((Now - LastDodgeTime) / DodgeCooldown), 0.f, 1.f) : 1.f;
}

bool UAOS_EvasionComponent::IsThreatenedBy(const FAOSTorpedoSalvo& Salvo) const
{
	const AAOS_AIEnemyCharacter* Reaper = GetReaper();
	if (!Reaper || Reaper->IsDead())
	{
		return false;
	}
	if (Salvo.AimActor.Get() == Reaper)
	{
		return true;
	}
	if (const UBoxComponent* Hit = Reaper->GetHitVolume())
	{
		FVector Closest;
		const float Dist = Hit->GetClosestPointOnCollision(Salvo.AimPoint, Closest);
		return Dist >= 0.f ? Dist <= ThreatAimRadius : FVector::Dist(Salvo.AimPoint, Hit->GetComponentLocation()) <= ThreatAimRadius;
	}
	return false;
}

// ---------------------------------------------------------------------------------------------------------------------
AAOS_CavitationDecoy* UAOS_EvasionComponent::EvaluateSalvo(const FAOSTorpedoSalvo& Salvo)
{
	AAOS_AIEnemyCharacter* Reaper = GetReaper();
	UWorld* World = GetWorld();
	if (!Reaper || !World || Reaper->IsDead())
	{
		return nullptr;
	}

	// D: first launch point -> closest point of the hit volume.
	float D = FVector::Dist(Salvo.FirstLaunchOrigin, Reaper->GetActorLocation());
	if (const UBoxComponent* Hit = Reaper->GetHitVolume())
	{
		FVector Closest;
		const float Dist = Hit->GetClosestPointOnCollision(Salvo.FirstLaunchOrigin, Closest);
		if (Dist >= 0.f)
		{
			D = FVector::Dist(Closest, Salvo.FirstLaunchOrigin);
		}
	}

	++StatSalvos;
	const float PDodge = ComputeDodgeProbability(D);
	// Deterministic per (PID, salvo), but decorrelated between consecutive salvos (see AOSMix32).
	const int32 Seed = static_cast<int32>(AOSMix32(AOSMix32(static_cast<uint32>(Reaper->GetPID())) ^ (static_cast<uint32>(Salvo.SalvoId) * 0x9e3779b9U)));
	FRandomStream Stream(Seed);
	const float U = Stream.FRand();
	const int32 Force = CVarForceDodge.GetValueOnGameThread();
	if (Force != -1)
	{
		// A console CVar outlives PIE sessions inside one editor run: a leftover test value silently disables (0) or forces (1) every roll.
		UE_LOG(LogAOSAI, Warning, TEXT("oom_reaper[%d] evade: aos.ai.ForceDodge=%d is ACTIVE (debug override, natural rolls bypassed). Set it to -1 for the model."), Reaper->GetPID(), Force);
	}
	const bool bCanAct = Charges > 0 && (World->GetTimeSeconds() - LastDodgeTime) >= DodgeCooldown && !bEvading && ComputeStateFactor() > 0.f;
	bool bDodge = (Force == 1) ? bCanAct : (Force == 0 ? false : U < PDodge);

	UE_LOG(LogAOSAI, Log, TEXT("oom_reaper[%d] evade: D=%.1fm P=%.2f u=%.2f charges=%d%s -> %s"),
		Reaper->GetPID(), D / 100.f, PDodge, U, Charges, Force != -1 ? *FString::Printf(TEXT(" force=%d"), Force) : TEXT(""), bDodge ? TEXT("DODGE") : TEXT("hold"));

	if (!bDodge)
	{
		++StatLanded;
		StatLandedDistanceSum += D;
		return nullptr;
	}

	++StatDodges;
	StatDodgedDistanceSum += D;
	--Charges;
	LastDodgeTime = World->GetTimeSeconds();
	RecentDodges.Add(LastDodgeTime);
	RegenTimer = 0.f;

	// Skitter away from the aim point; if both sides are blocked the decoy still fires.
	const bool bMoved = TrySkitter(Salvo.FirstLaunchOrigin, Salvo.AimPoint);
	if (!bMoved)
	{
		++StatBlocked;
		UE_LOG(LogAOSAI, Log, TEXT("oom_reaper[%d] evade: blocked"), Reaper->GetPID());
	}

	// Decoy between the torpedoes and the old position.
	FVector ToAttacker = Salvo.FirstLaunchOrigin - Reaper->GetActorLocation();
	ToAttacker = ToAttacker.GetSafeNormal();
	const FVector SpawnLoc = Reaper->GetActorLocation() + ToAttacker * DecoyOffset;
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Params.Owner = Reaper;
	AAOS_CavitationDecoy* Decoy = World->SpawnActor<AAOS_CavitationDecoy>(DecoyClass ? DecoyClass.Get() : AAOS_CavitationDecoy::StaticClass(), SpawnLoc, ToAttacker.Rotation(), Params);
	if (Decoy)
	{
		Decoy->Activate(DecoyLifetime);
	}
	PushPageMap();
	return Decoy;
}

bool UAOS_EvasionComponent::TrySkitter(const FVector& AttackOrigin, const FVector& AimPoint)
{
	AAOS_AIEnemyCharacter* Reaper = GetReaper();
	UWorld* World = GetWorld();
	UCharacterMovementComponent* Move = Reaper ? Reaper->GetCharacterMovement() : nullptr;
	if (!Reaper || !World || !Move)
	{
		return false;
	}

	const FVector B = Reaper->GetActorLocation();
	FVector ToReaper = B - AttackOrigin;
	ToReaper.Z = 0.f;
	const FVector UHat = ToReaper.GetSafeNormal();
	FVector Side = FVector::CrossProduct(FVector::UpVector, UHat).GetSafeNormal2D();
	if (Side.IsNearlyZero())
	{
		Side = FVector::RightVector;
	}
	// Away from the aim point; on a tie the seeded stream decides.
	const float AimSide = FVector::DotProduct(Side, AimPoint - B);
	if (FMath::Abs(AimSide) < 1.f)
	{
		FRandomStream Stream(Reaper->GetPID() * 131 + StatSalvos);
		Side *= Stream.FRand() < 0.5f ? 1.f : -1.f;
	}
	else if (AimSide > 0.f)
	{
		Side = -Side;
	}

	const UCapsuleComponent* Capsule = Reaper->GetCapsuleComponent();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(ReaperSkitter), false, Reaper);
	Params.bFindInitialOverlaps = false;   // the enclosing ocean volume (WorldStatic = Block, Pawn = Overlap) must not count as an obstacle: sweep as a Pawn
	UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);

	for (int32 Attempt = 0; Attempt < 2; ++Attempt)
	{
		const FVector Goal = B + Side * SkitterDistance;
		FHitResult Hit;
		const bool bBlocked = World->SweepSingleByChannel(Hit, B, Goal, FQuat::Identity, ECC_Pawn,
			FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight()), Params);
		bool bOnNav = true;
		if (Nav)
		{
			FNavLocation Projected;
			bOnNav = Nav->ProjectPointToNavigation(Goal, Projected, FVector(80.f, 80.f, 150.f));
		}
		if (!bBlocked && bOnNav)
		{
			// Fallback of Appendix B #6: lateral launch with the friction removed for the skitter duration.
			SavedGroundFriction = Move->GroundFriction;
			SavedBraking = Move->BrakingDecelerationWalking;
			Move->GroundFriction = 0.f;
			Move->BrakingDecelerationWalking = 0.f;
			Reaper->LaunchCharacter(Side * (SkitterDistance / SkitterDuration), true, false);
			bEvading = true;
			Reaper->AbortStrike();
			Reaper->SetSkittering(true);
			Reaper->SetPhase(EAOSReaperPhase::Evading);
			World->GetTimerManager().SetTimer(SkitterTimer, this, &UAOS_EvasionComponent::EndSkitter, SkitterDuration, false);
			return true;
		}
		Side = -Side;
	}
	return false;
}

void UAOS_EvasionComponent::EndSkitter()
{
	AAOS_AIEnemyCharacter* Reaper = GetReaper();
	bEvading = false;
	if (Reaper)
	{
		if (UCharacterMovementComponent* Move = Reaper->GetCharacterMovement())
		{
			Move->GroundFriction = SavedGroundFriction;
			Move->BrakingDecelerationWalking = SavedBraking;
			Move->Velocity = FVector::ZeroVector;
		}
		Reaper->SetSkittering(false);
		Reaper->SetPhase(EAOSReaperPhase::Chase);
	}
	PushPageMap();
}

void UAOS_EvasionComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (Charges < MaxCharges && !bRegenPaused)
	{
		RegenTimer += DeltaTime;
		if (RegenTimer >= ChargeRegenInterval)
		{
			RegenTimer = 0.f;
			++Charges;
		}
	}
	PushPageMap();
}

void UAOS_EvasionComponent::PushPageMap()
{
	if (const AAOS_AIEnemyCharacter* Reaper = GetReaper())
	{
		if (UAOS_RSSPageMapComponent* Map = Reaper->GetPageMap())
		{
			Map->SetDecoyCharges(Charges, MaxCharges);
			Map->SetEvasionReadiness(GetReadiness());
		}
	}
}
