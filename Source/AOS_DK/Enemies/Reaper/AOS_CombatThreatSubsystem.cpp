#include "AOS_CombatThreatSubsystem.h"
#include "AOS_EvasionComponent.h"
#include "AOS_CavitationDecoy.h"
#include "AOS_AIEnemyCharacter.h"
#include "AOS_DK/Submarine/Subdrones/Attacker/MicroTorpedo.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"

void UAOS_CombatThreatSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	// aos.ai.ForceDodge is a debug override that lives in the editor process, not in the PIE world: a test or screenshot pass that left it at 0
	// ("never dodge") kept every later PIE session passive. Every new play session starts on the natural dodge model.
	if (IConsoleVariable* Force = IConsoleManager::Get().FindConsoleVariable(TEXT("aos.ai.ForceDodge")))
	{
		const int32 Old = Force->GetInt();
		if (Old != -1)
		{
			UE_LOG(LogAOSAI, Warning, TEXT("aos.ai.ForceDodge was %d (left over from an earlier session) - reset to -1 (natural dodge model)."), Old);
			Force->Set(-1, ECVF_SetByConsole);
		}
	}
}

void UAOS_CombatThreatSubsystem::RegisterEvasion(UAOS_EvasionComponent* Component)
{
	if (Component)
	{
		Evasions.AddUnique(Component);
	}
}

void UAOS_CombatThreatSubsystem::UnregisterEvasion(UAOS_EvasionComponent* Component)
{
	Evasions.Remove(Component);
}

void UAOS_CombatThreatSubsystem::Tick(float DeltaTime)
{
	const double Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	Salvos.RemoveAll([Now](const FSalvoRecord& R) { return Now - R.Salvo.OpenTime > 2.0; });
	Evasions.RemoveAll([](const TWeakObjectPtr<UAOS_EvasionComponent>& E) { return !E.IsValid(); });
}

void UAOS_CombatThreatSubsystem::ReportTorpedoLaunch(AMicroTorpedo* Torpedo, AActor* Instigator, const FVector& LaunchOrigin, const FVector& AimPoint, AActor* AimActor)
{
	UWorld* World = GetWorld();
	if (!Torpedo || !World)
	{
		return;
	}
	const double Now = World->GetTimeSeconds();

	// Join the open salvo of the same shooter.
	for (FSalvoRecord& Record : Salvos)
	{
		if (Record.Salvo.Instigator.Get() == Instigator && Now - Record.Salvo.OpenTime <= SalvoWindow)
		{
			Record.Salvo.Torpedoes.Add(Torpedo);
			for (const TPair<TWeakObjectPtr<UAOS_EvasionComponent>, TWeakObjectPtr<AAOS_CavitationDecoy>>& Pair : Record.Decoys)
			{
				if (AAOS_CavitationDecoy* Decoy = Pair.Value.Get())
				{
					Torpedo->Retarget(Decoy, Decoy->GetActorLocation());   // late joiners follow the same decoy
				}
			}
			return;
		}
	}

	FSalvoRecord& Record = Salvos.AddDefaulted_GetRef();
	Record.Salvo.SalvoId = NextSalvoId++;
	Record.Salvo.Instigator = Instigator;
	Record.Salvo.AimActor = AimActor;
	Record.Salvo.FirstLaunchOrigin = LaunchOrigin;
	Record.Salvo.AimPoint = AimPoint;
	Record.Salvo.OpenTime = Now;
	Record.Salvo.Torpedoes.Add(Torpedo);

	for (const TWeakObjectPtr<UAOS_EvasionComponent>& WeakEvasion : Evasions)
	{
		UAOS_EvasionComponent* Evasion = WeakEvasion.Get();
		if (!Evasion || !Evasion->IsThreatenedBy(Record.Salvo))
		{
			continue;
		}
		AAOS_CavitationDecoy* Decoy = Evasion->EvaluateSalvo(Record.Salvo);
		if (!Decoy)
		{
			continue;
		}
		Record.Decoys.Add(Evasion, Decoy);
		int32 Diverted = 0;
		for (const TWeakObjectPtr<AMicroTorpedo>& WeakTorpedo : Record.Salvo.Torpedoes)
		{
			if (AMicroTorpedo* T = WeakTorpedo.Get())
			{
				if (T->IsInFlight())
				{
					T->Retarget(Decoy, Decoy->GetActorLocation());
					++Diverted;
				}
			}
		}
		if (AAOS_AIEnemyCharacter* Reaper = Cast<AAOS_AIEnemyCharacter>(Evasion->GetOwner()))
		{
			Reaper->ReportToShell(FString::Printf(TEXT("decoy launched - %d torpedoes lost lock"), FMath::Max(Diverted, 1)), EAOSHudLogSeverity::Info);
		}
	}
}
