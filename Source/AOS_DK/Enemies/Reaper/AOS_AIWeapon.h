#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOS_AIWeapon.generated.h"

class UStaticMeshComponent;
class UDamageType;
class UNiagaraSystem;
class AShellPawn;

/**
 * SIGKILL arc pike (SM_WPN_SigkillPike). Clamped in the Reaper's wrist jaws on SOCKET_Weapon_Dorsal (Arm_Wrist_Bone).
 * A strike is a swept sphere along SOCKET_Strike_Trace_Start -> SOCKET_Strike_Trace_End (re-swept from the previous
 * frame's segment so nothing tunnels); one hit per swing, 5 % of the Shell's core energy.
 */
UCLASS(Blueprintable)
class AOS_DK_API AAOS_AIWeapon : public AActor
{
	GENERATED_BODY()

public:
	AAOS_AIWeapon();

	virtual void Tick(float DeltaSeconds) override;

	/** Attaches the pike mount (SOCKET_Mount_Base, = actor origin) to a skeletal socket. */
	void AttachToSocket(USceneComponent* Parent, FName ParentSocket);

	/** Detaches and drops the pike with water-drag physics (Reaper death). */
	void DropWithPhysics();

	void BeginSwing(AController* InInstigatorController);
	void EndSwing();
	bool IsSwinging() const { return bSwinging; }
	bool HasHitThisSwing() const { return bHitThisSwing; }

	/** Distance from the mount to the tip socket along the pike axis (cm), measured from the mesh sockets when present. */
	float GetTipDistance() const;

	UStaticMeshComponent* GetPikeMesh() const { return PikeMesh; }

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Reaper|Weapon", meta = (DisplayName = "On Pike Hit"))
	void BP_OnPikeHit(const FHitResult& Hit);

	/** Damage in percent points of core energy (AShellPawn::TakeDamage interprets damage as percent). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Weapon", meta = (ClampMin = "0", Units = "Percent"))
	float StrikeDamagePercent = 5.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AOS_DK|Reaper|Weapon", meta = (ClampMin = "1", Units = "cm"))
	float SweepRadius = 22.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Weapon")
	FName MountSocket = TEXT("SOCKET_Mount_Base");

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Weapon")
	FName TraceStartSocket = TEXT("SOCKET_Strike_Trace_Start");

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Weapon")
	FName TraceEndSocket = TEXT("SOCKET_Strike_Trace_End");

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Weapon")
	TSubclassOf<UDamageType> DamageTypeClass;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|Weapon|FX")
	TObjectPtr<UNiagaraSystem> ImpactFX;

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> PikeMesh;

private:
	bool GetTraceSegment(FVector& OutStart, FVector& OutEnd) const;
	void SweepStrike();

	bool bSwinging = false;
	bool bHitThisSwing = false;
	bool bHavePrevSegment = false;
	FVector PrevStart = FVector::ZeroVector;
	FVector PrevEnd = FVector::ZeroVector;
	TWeakObjectPtr<AController> InstigatorController;
};
