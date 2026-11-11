#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "AOS_ReaperTypes.h"
#include "AOS_CombatThreatSubsystem.generated.h"

class AMicroTorpedo;
class UAOS_EvasionComponent;
class AAOS_CavitationDecoy;

/**
 * Aggregates the Attacker's torpedoes into salvos (one dodge roll per salvo, not per torpedo) and routes them to the
 * evasion components of the threatened Reapers (spec 6.2). ASubDrone_Attacker::FireOnce reports every launch here.
 */
UCLASS()
class AOS_DK_API UAOS_CombatThreatSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override { RETURN_QUICK_DECLARE_CYCLE_STAT(UAOS_CombatThreatSubsystem, STATGROUP_Tickables); }
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override { return WorldType == EWorldType::Game || WorldType == EWorldType::PIE; }
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;

	void RegisterEvasion(UAOS_EvasionComponent* Component);
	void UnregisterEvasion(UAOS_EvasionComponent* Component);

	/** Called right after AMicroTorpedo::Launch. */
	void ReportTorpedoLaunch(AMicroTorpedo* Torpedo, AActor* Instigator, const FVector& LaunchOrigin, const FVector& AimPoint, AActor* AimActor);

	/** Salvo window: a torpedo launched within this time of the salvo's first one joins it. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Threat", meta = (ClampMin = "0.01", Units = "s"))
	float SalvoWindow = 0.30f;

private:
	struct FSalvoRecord
	{
		FAOSTorpedoSalvo Salvo;
		TMap<TWeakObjectPtr<UAOS_EvasionComponent>, TWeakObjectPtr<AAOS_CavitationDecoy>> Decoys;
	};

	TArray<FSalvoRecord> Salvos;
	TArray<TWeakObjectPtr<UAOS_EvasionComponent>> Evasions;
	int32 NextSalvoId = 1;
};
