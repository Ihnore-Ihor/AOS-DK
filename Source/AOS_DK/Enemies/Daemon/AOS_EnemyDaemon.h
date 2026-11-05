#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DaemonGeometry.h"
#include "AOS_EnemyDaemon.generated.h"

class USphereComponent;
class UCapsuleComponent;
class USplineComponent;
class UProceduralMeshComponent;
class UPointLightComponent;
class UNiagaraComponent;
class UNiagaraSystem;
class UWidgetComponent;
class UMaterialInterface;
class UDamageType;
class UEnemyHealthBarWidget;
class AShellPawn;
class AAOS_EnemySpawner;

/**
 * Deterministic behaviour states (no AI framework: a plain C++ finite-state machine driven by
 * distances, timers and a line trace - same inputs always give the same motion).
 */
UENUM(BlueprintType)
enum class EDaemonState : uint8
{
	Patrol    UMETA(DisplayName = "Patrol"),     // follows the closed patrol spline
	Engage    UMETA(DisplayName = "Engage"),     // closes in and circles the Shell at stand-off range
	Telegraph UMETA(DisplayName = "Telegraph"),  // readable wind-up: charge, recoil, halos spin up
	Strike    UMETA(DisplayName = "Strike"),     // lunge (ram) in flight
	Recover   UMETA(DisplayName = "Recover"),    // cool-down drift after the attack
	Return    UMETA(DisplayName = "Return"),     // back to the closest point of the patrol route
	Dying     UMETA(DisplayName = "Dying")
};

UENUM(BlueprintType)
enum class EDaemonAttackMode : uint8
{
	/** Wind-up recoil, then a dash into the hull (contact damage). */
	Lunge UMETA(DisplayName = "Lunge (ram)"),
	/** Wind-up charge, then a spherical EMP discharge (radius damage). */
	Pulse UMETA(DisplayName = "Pulse (EMP discharge)")
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnDaemonDestroyed, AAOS_EnemyDaemon*, Daemon);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnDaemonStateChanged, EDaemonState, NewState, EDaemonState, OldState);

/** Custom Primitive Data layout of M_EnemyDaemon_Hull / M_EnemyDaemon_Glow. */
namespace DaemonCPD
{
	inline constexpr int32 GlowColor     = 0; // RGBA (0..3)
	inline constexpr int32 GlowIntensity = 4;
	inline constexpr int32 HitFlash      = 5;
}

/**
 * "System daemon" - underwater security process of the Towers (Tasks 1, 2, 3, 5).
 *  - Procedural model (DaemonGeometry): plated core, eye lens, two gyroscopic halos, four
 *    data-cable tendrils animated with a travelling sine wave (swimming).
 *  - Patrol: closed USplineComponent route (from the spawner, any actor with a spline, or the
 *    local PatrolPoints array). Motion = carrot on the spline + FMath::VInterpTo velocity
 *    (water inertia) + swept movement + banking.
 *  - Attack: telegraph (charge colour ramp, recoil, halos/tendrils) -> Lunge or EMP Pulse,
 *    fixed damage to the Shell energy through the standard UE damage pipeline.
 *  - Health + 3D health bar (UWidgetComponent + UEnemyHealthBarWidget), Niagara explosion on death.
 */
UCLASS(Blueprintable)
class AOS_DK_API AAOS_EnemyDaemon : public AActor
{
	GENERATED_BODY()

public:
	AAOS_EnemyDaemon();

	virtual void Tick(float DeltaSeconds) override;
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual float TakeDamage(float DamageAmount, struct FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override;

	/** Called by AAOS_EnemySpawner before FinishSpawning. */
	void InitializeFromSpawner(AAOS_EnemySpawner* InSpawner, USplineComponent* InRoute, float InStartDistance, EDaemonAttackMode InMode, int32 InSerial);

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Daemon")
	bool IsAlive() const { return State != EDaemonState::Dying && Health > 0.f; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Daemon")
	float GetHealthFraction() const { return MaxHealth > 0.f ? Health / MaxHealth : 0.f; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Daemon")
	EDaemonState GetState() const { return State; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Daemon")
	int32 GetProcessId() const { return ProcessId; }

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Daemon")
	FString GetProcessName() const;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Daemon")
	FOnDaemonDestroyed OnDaemonDestroyed;

	UPROPERTY(BlueprintAssignable, Category = "AOS_DK|Daemon")
	FOnDaemonStateChanged OnStateChanged;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Daemon", meta = (DisplayName = "On Daemon State Changed"))
	void BP_OnStateChanged(EDaemonState NewState, EDaemonState OldState);

	UFUNCTION(BlueprintImplementableEvent, Category = "AOS_DK|Daemon", meta = (DisplayName = "On Daemon Struck Shell"))
	void BP_OnStruckShell(const FVector& ImpactPoint);

	// --- Components ---------------------------------------------------------------------------
	/** Query-only sweep body: blocks world geometry, torpedo sweeps (WorldDynamic) and aim traces. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USphereComponent> Collision;

	/**
	 * Damage / aim volume matching the VISIBLE silhouette (halo rings). Query-only, blocks only the
	 * torpedo sweep channel (WorldDynamic) and the aim trace (Visibility) - movement uses Collision.
	 */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USphereComponent> HitVolume;

	/** Damage volume along the tendril bundle (behind the core). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UCapsuleComponent> TailHitVolume;

	/** Parent of the model: bob / sway / telegraph shake live here. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> VisualRoot;

	/** Section 0: armour plates (hull), section 1: inner core (glow through the seams). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UProceduralMeshComponent> CoreMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UProceduralMeshComponent> EyeMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UProceduralMeshComponent> HaloOuter;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UProceduralMeshComponent> HaloInner;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TArray<TObjectPtr<UProceduralMeshComponent>> TendrilMeshes;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UPointLightComponent> CoreLight;

	/** NS_DaemonCharge: energy drawn into the core during the telegraph. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UNiagaraComponent> ChargeFX;

	/** 3D health bar (Task 5). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UWidgetComponent> HealthBar;

	// --- Health ---------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Daemon|Health", meta = (ClampMin = "1"))
	float MaxHealth = 100.f;

	// --- Patrol (deterministic, no AI) ----------------------------------------------------------
	/** Any actor with a USplineComponent (closed loop recommended). The spawner sets its own spline. */
	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "AOS_DK|Daemon|Patrol")
	TObjectPtr<AActor> PatrolRouteActor;

	/** Fallback route: local points (3D widgets in the viewport), closed Catmull-Rom loop. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Daemon|Patrol", meta = (MakeEditWidget = true))
	TArray<FVector> PatrolPoints;

	/** No route and no points: circle of this radius around the start position. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Patrol", meta = (ClampMin = "100", Units = "cm"))
	float DefaultPatrolRadius = 1200.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Patrol", meta = (ClampMin = "10", Units = "CentimetersPerSecond"))
	float PatrolSpeed = 320.f;

	/** Carrot distance ahead on the spline (smooths the corners). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Patrol", meta = (ClampMin = "10", Units = "cm"))
	float PatrolLookAhead = 280.f;

	/** VInterpTo speed of the velocity (lower = heavier water inertia). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Patrol", meta = (ClampMin = "0.1"))
	float WaterResponsiveness = 1.6f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Patrol", meta = (ClampMin = "0.1"))
	float TurnSpeed = 3.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Patrol", meta = (ClampMin = "0", ClampMax = "60", Units = "Degrees"))
	float MaxBankAngle = 24.f;

	/** Keep this far below the sea surface (OceanSurfaceZ of the Shell). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Patrol", meta = (ClampMin = "0", Units = "cm"))
	float SurfaceClearance = 180.f;

	// --- Detection / engagement -------------------------------------------------------------------
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "100", Units = "cm"))
	float AggroRadius = 2600.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "100", Units = "cm"))
	float DisengageRadius = 4400.f;

	/** Max distance from the patrol route before the daemon gives up the chase. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "100", Units = "cm"))
	float LeashRadius = 5200.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat")
	bool bRequireLineOfSight = true;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "10", Units = "CentimetersPerSecond"))
	float EngageSpeed = 560.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (Units = "DegreesPerSecond"))
	float OrbitSpeed = 16.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat")
	EDaemonAttackMode AttackMode = EDaemonAttackMode::Lunge;

	/** Distance from the hull surface at which the wind-up starts. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "50", Units = "cm"))
	float AttackRange = 760.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "0.1", Units = "s"))
	float TelegraphTime = 0.95f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (Units = "CentimetersPerSecond"))
	float RecoilSpeed = 240.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "100", Units = "CentimetersPerSecond"))
	float LungeSpeed = 2500.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "0.05", Units = "s"))
	float LungeMaxTime = 0.6f;

	/** Contact distance (hull surface <-> daemon collision) that counts as a ram hit. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "0", Units = "cm"))
	float StrikeContactPadding = 70.f;

	/** EMP discharge reach (hull surface distance). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "50", Units = "cm"))
	float PulseRadius = 900.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "0.1", Units = "s"))
	float RecoverTime = 1.5f;

	/** Extra wait before the next wind-up. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "0", Units = "s"))
	float AttackCooldown = 1.2f;

	/** Fixed damage in percent points of the Shell core energy. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS_DK|Daemon|Combat", meta = (ClampMin = "0"))
	float AttackDamage = 8.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Combat")
	TSubclassOf<UDamageType> DamageTypeClass;

	// --- Model ----------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model")
	TObjectPtr<UMaterialInterface> HullMaterial;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model")
	TObjectPtr<UMaterialInterface> GlowMaterial;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model", meta = (ClampMin = "10", Units = "cm"))
	float CoreRadius = 52.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model", meta = (ClampMin = "10", Units = "cm"))
	float TendrilLength = 230.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model", meta = (ClampMin = "3", ClampMax = "24"))
	int32 TendrilSegments = 10;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model", meta = (ClampMin = "3", ClampMax = "12"))
	int32 TendrilSides = 6;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model", meta = (ClampMin = "0", Units = "cm"))
	float TendrilWaveAmplitude = 20.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model", meta = (ClampMin = "0", Units = "Hz"))
	float TendrilWaveFrequency = 1.2f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model", meta = (ClampMin = "0", Units = "cm"))
	float BobAmplitude = 9.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model", meta = (Units = "DegreesPerSecond"))
	float HaloSpinSpeed = 40.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model")
	bool bCastShadows = false;

	/** Tendrils are re-meshed only when rendered recently and closer than this. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Model", meta = (ClampMin = "100", Units = "cm"))
	float TendrilUpdateDistance = 9000.f;

	// --- Colours (Dracula) -------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Look")
	FLinearColor IdleColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Look")
	FLinearColor AlertColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Look")
	FLinearColor ChargeColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Look")
	FLinearColor StrikeColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Look", meta = (ClampMin = "0"))
	float IdleGlow = 3.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Look", meta = (ClampMin = "0"))
	float ChargeGlowMax = 8.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|Look", meta = (ClampMin = "0"))
	float CoreLightIntensity = 90.f;

	// --- FX -----------------------------------------------------------------------------------------
	/** NS_DaemonExplosion: rupture of the process on death. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|FX")
	TObjectPtr<UNiagaraSystem> DeathFX;

	/** Optional second burst (e.g. NS_TorpedoHit bubbles, scaled). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|FX")
	TObjectPtr<UNiagaraSystem> DeathSecondaryFX;

	/** NS_DaemonPulse: EMP shock shell. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|FX")
	TObjectPtr<UNiagaraSystem> PulseFX;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|FX", meta = (ClampMin = "0.1"))
	float DeathFXScale = 1.f;

	// --- Health bar ---------------------------------------------------------------------------------
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|HealthBar")
	TSubclassOf<UEnemyHealthBarWidget> HealthBarWidgetClass;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|HealthBar", meta = (Units = "cm"))
	float HealthBarHeight = 125.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|HealthBar", meta = (ClampMin = "100", Units = "cm"))
	float HealthBarVisibleDistance = 6500.f;

	/** false = show only when damaged or engaged. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|HealthBar")
	bool bAlwaysShowHealthBar = true;

	/** Hide the bar when world geometry is between the camera and the daemon. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|HealthBar")
	bool bHideHealthBarWhenOccluded = true;

	/** World-space billboard (turns to the camera) instead of a screen-space overlay. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Daemon|HealthBar")
	bool bWorldSpaceHealthBar = false;

private:
	void BuildModel();
	void ResolvePatrolRoute();
	USplineComponent* BuildRuntimeRoute(const TArray<FVector>& WorldPoints);

	void SetState(EDaemonState NewState);
	void EvaluateTarget();
	AShellPawn* FindCandidateShell() const;
	bool HasLineOfSight(const AShellPawn* Shell) const;
	float DistanceToHull(const AShellPawn* Shell, FVector* OutClosest = nullptr) const;
	float DistanceFromRoute() const;

	void TickPatrol(float Dt);
	void TickEngage(float Dt);
	void TickTelegraph(float Dt);
	void TickStrike(float Dt);
	void TickRecover(float Dt);
	void TickReturn(float Dt);
	void TickDying(float Dt);

	/** Water-inertia steering: velocity -> VInterpTo(desired), swept move, slide, face + bank. */
	void Steer(const FVector& DesiredVelocity, float Responsiveness, float Dt, const FVector* FacePoint);
	void MoveSwept(const FVector& Delta);

	void StrikeShell(AShellPawn* Shell);
	void Die(AActor* Killer);

	void UpdateVisuals(float Dt);
	void UpdateTendrils(float Dt, float Speed01);
	void UpdateHealthBar(float Dt);
	void PushCPD(const FLinearColor& Color, float Glow, float Flash);
	float GetSurfaceCeilingZ() const;
	void LogToShell(const FString& Message, uint8 SeverityIndex) const;

	EDaemonState State = EDaemonState::Patrol;
	float StateTime = 0.f;
	float Health = 100.f;
	FVector Velocity = FVector::ZeroVector;
	FVector PrevVelocity = FVector::ZeroVector;

	UPROPERTY(Transient)
	TObjectPtr<USplineComponent> ActiveRoute;

	TWeakObjectPtr<AAOS_EnemySpawner> OwnerSpawner;
	TWeakObjectPtr<AShellPawn> Target;
	float RouteDistance = 0.f;
	float ReturnDistance = 0.f;
	bool bHasSpawnerStart = false;

	float DetectTimer = 0.f;
	float CooldownRemaining = 0.f;
	float OrbitSign = 1.f;
	FVector LungeDirection = FVector::ForwardVector;
	bool bStrikeLanded = false;
	bool bAnnouncedIntrusion = false;

	// Visual state
	float AnimTime = 0.f;
	float Phase = 0.f;
	float ChargeAlpha = 0.f;
	float HitFlash = 0.f;
	float DeathTime = 0.f;
	float HaloAngleOuter = 0.f;
	float HaloAngleInner = 0.f;
	float CoreSpin = 0.f;
	FLinearColor DisplayColor = FLinearColor::White;
	float DisplayGlow = 0.f;
	FVector4 LastCPDColor = FVector4(-1.0, -1.0, -1.0, -1.0);
	float LastCPDGlow = -1.f;
	float LastCPDFlash = -1.f;
	int32 ProcessId = 0;
	float OcclusionTimer = 0.f;
	bool bHealthBarOccluded = false;

	TArray<FDaemonMeshData> TendrilData;
	TArray<FVector> SpineScratch;
	TArray<float> RadiiScratch;
};
