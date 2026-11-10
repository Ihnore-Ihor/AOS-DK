#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AOSTeleportStation.generated.h"

class UBoxComponent;
class UStaticMeshComponent;
class UArrowComponent;
class UPointLightComponent;
class UPrimitiveComponent;
class USoundBase;
class AShellPawn;

/** Direction in which Shell-1 thrusts into the shaft mouth (the kinematic alignment vector). */
UENUM(BlueprintType)
enum class EAOSTransitDirection : uint8
{
	/** Mouth faces up, the shaft runs down (surface station: dive into the deep). */
	Down,
	/** Mouth faces down, the shaft runs up (deep station: rise toward the surface). */
	Up,
	/** Horizontal: mouth faces the actor's -X, the shaft runs along +X (swim straight in, level). */
	Forward
};

UENUM(BlueprintType)
enum class EAOSTransitPhase : uint8
{
	Idle,
	/** Controls locked, the Shell is drawn into the shaft along the entry vector. */
	Intake,
	/** Camera fading to black, the Shell keeps gliding inside the shaft. */
	FadeOut
};

/**
 * Evacuation Transit Shaft (Lab 4): a two-way, trigger-driven long-distance teleport.
 *
 * Shell-1 entering EntranceTrigger -> 6DOF locked -> kinematic intake along the entry vector (IntakeDuration)
 * -> camera fade to black (FadeDuration) -> warp to LinkedStation->ExitPoint with an outward velocity
 * -> fade in, 6DOF restored. The destination trigger is ignored for ArrivalCooldown seconds (anti-loop).
 *
 * Local layout (bAutoLayout): the actor origin is the centre of the portal lens; PortalFrame's +X (lens axis)
 * points along the entry vector; ShaftMesh continues behind the frame; EntranceTrigger sits in front of the
 * mouth; ExitPoint is ExitClearance beyond the trigger (outside it), level, facing the actor's forward
 * (Down / Up) or facing out of the mouth (Forward, so the arriving Shell looks away from the station).
 */
UCLASS(Blueprintable, meta = (DisplayName = "AOS Teleport Station"))
class AOS_DK_API AAOSTeleportStation : public AActor
{
	GENERATED_BODY()

public:
	AAOSTeleportStation();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	/** Starts the transit sequence for a manned Shell. Returns false (and does nothing) when refused. */
	UFUNCTION(BlueprintCallable, Category = "AOS|Transit")
	bool BeginTransit(AShellPawn* Shell);

	/** Ignores the entrance trigger for Seconds (anti-loop after an arrival). */
	UFUNCTION(BlueprintCallable, Category = "AOS|Transit")
	void ApplyArrivalCooldown(float Seconds);

	UFUNCTION(BlueprintPure, Category = "AOS|Transit")
	bool IsOnCooldown() const;

	UFUNCTION(BlueprintPure, Category = "AOS|Transit")
	float GetCooldownRemaining() const;

	UFUNCTION(BlueprintPure, Category = "AOS|Transit")
	EAOSTransitPhase GetPhase() const { return Phase; }

	/** World-space unit vector the Shell thrusts along to enter this shaft. */
	UFUNCTION(BlueprintPure, Category = "AOS|Transit")
	FVector GetEntryVector() const;

	/** World-space velocity given to a Shell arriving here (outward along the shaft axis). */
	UFUNCTION(BlueprintPure, Category = "AOS|Transit")
	FVector GetExitVelocity() const;

	UFUNCTION(BlueprintPure, Category = "AOS|Transit")
	USceneComponent* GetExitPoint() const { return ExitPoint; }

	UFUNCTION(BlueprintPure, Category = "AOS|Transit")
	UBoxComponent* GetEntranceTrigger() const { return EntranceTrigger; }

	UFUNCTION(BlueprintPure, Category = "AOS|Transit")
	AAOSTeleportStation* GetLinkedStation() const;

	UFUNCTION(BlueprintPure, Category = "AOS|Transit")
	const FString& GetStationName() const { return StationName; }

	/** Current screen fade of local player 0 (0 = clear, 1 = black) - test telemetry; FadeAmount is not reflected. */
	UFUNCTION(BlueprintPure, Category = "AOS|Transit|Telemetry", meta = (WorldContext = "WorldContextObject"))
	static float GetLocalPlayerFadeAmount(const UObject* WorldContextObject);

	/** Completed departures / arrivals since BeginPlay (telemetry for tests). */
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "AOS|Transit|Telemetry")
	int32 DepartureCount = 0;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "AOS|Transit|Telemetry")
	int32 ArrivalCount = 0;

	/** Overlaps refused because of the arrival cooldown. */
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category = "AOS|Transit|Telemetry")
	int32 CooldownRejectCount = 0;

protected:
	//~ Components
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> SceneRoot;

	/** Visual portal frame (SM_Breach_SomaLock). Lens axis = mesh +X. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> PortalFrame;

	/** Shaft tube continuing behind the frame (SM_AOS_TransitShaft, axis +X from its pivot). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UStaticMeshComponent> ShaftMesh;

	/** Query-only box in front of the mouth; overlaps Pawn / PhysicsBody / Vehicle. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UBoxComponent> EntranceTrigger;

	/** Where a Shell arriving from the linked station is placed (location + rotation). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<USceneComponent> ExitPoint;

	/** Kinematic alignment vector (editor visualisation of the entry direction). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UArrowComponent> EntryArrow;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UArrowComponent> ExitArrow;

	/** Beacon light at the mouth. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	TObjectPtr<UPointLightComponent> MouthLight;

	//~ Link
	/** The other end of the shaft (set mutually: A <-> B). */
	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "AOS|Transit")
	TSoftObjectPtr<AAOSTeleportStation> LinkedStation;

	/** Shown in the terminal log ("routing to <StationName>"). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit")
	FString StationName = TEXT("Transit Shaft");

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit")
	EAOSTransitDirection EntryDirection = EAOSTransitDirection::Down;

	//~ Sequence
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Sequence", meta = (ClampMin = "0.1", Units = "s"))
	float IntakeDuration = 1.2f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Sequence", meta = (ClampMin = "0.05", Units = "s"))
	float FadeDuration = 0.8f;

	/** Speed along the entry vector at the end of the intake (the glide continues through the fade). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Sequence", meta = (ClampMin = "0", Units = "cm/s"))
	float IntakeEndSpeed = 1000.f;

	/** Entry speed carried into the intake curve is clamped to this. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Sequence", meta = (ClampMin = "0", Units = "cm/s"))
	float MaxCarriedEntrySpeed = 1500.f;

	/** Share of the intake used to swing the nose onto the shaft axis. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Sequence", meta = (ClampMin = "0.1", ClampMax = "1"))
	float AlignFraction = 0.75f;

	/** Outward thrust given at the destination exit. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Sequence", meta = (ClampMin = "0", Units = "cm/s"))
	float ExitSpeed = 500.f;

	/** Re-trigger cooldown applied to the DESTINATION trigger on arrival. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Sequence", meta = (ClampMin = "0", Units = "s"))
	float ArrivalCooldown = 3.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Audio")
	TObjectPtr<USoundBase> DepartureSound;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Audio")
	TObjectPtr<USoundBase> ArrivalSound;

	//~ Layout (cm, measured on SM_Breach_SomaLock)
	/** Re-places frame / shaft / trigger / exit from the values below on every construction. Off = hand placement. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout")
	bool bAutoLayout = true;

	/** Lens axis offset in PortalFrame mesh space (the mesh pivot is not on the lens axis). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout")
	FVector FrameLensOffset = FVector(0.f, 162.f, 0.f);

	/** Distance from the lens centre to the mouth (front) face of the frame, along the axis. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout", meta = (ClampMin = "0"))
	float FrameFrontFace = 711.f;

	/**
	 * Distance from the lens centre to the back (exit) face of the frame along the lens axis; the shaft mouth sits exactly
	 * here (flush, no gap, no overlap). 420 = exit frame face of SM_Breach_SomaLock (its bounds reach 432 only at the bolt heads).
	 */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout", meta = (ClampMin = "0"))
	float FrameBackFace = 420.f;

	/**
	 * Centre of the frame's round tunnel bore in PortalFrame mesh space (Y, Z; X is ignored). The shaft continues THIS bore,
	 * i.e. the physical opening of the gate. The navigable lens (bore minus the jammed leaf) is off-centre by FrameLensOffset,
	 * so the actor origin / entry axis stay on the lens while the tube is coaxial with the bore. SM_Breach_SomaLock: (0, 0, 0).
	 */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout")
	FVector FrameBoreCenter = FVector::ZeroVector;

	/** Radius of that bore (SM_Breach_SomaLock: 410). The shaft is scaled radially so its outer wall meets it flush. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout", meta = (ClampMin = "0"))
	float FrameBoreRadius = 410.f;

	/** Outer wall radius of the ShaftMesh at its mouth, unscaled (SM_AOS_TransitShaft: 370). 0 = no radial fit. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout", meta = (ClampMin = "0"))
	float ShaftOuterRadius = 370.f;

	/** Trigger depth along the axis (in front of the mouth face). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout", meta = (ClampMin = "10"))
	float TriggerDepth = 500.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout", meta = (ClampMin = "10"))
	float TriggerHalfWidth = 300.f;

	/** Gap between the trigger's outer face and ExitPoint, so an arriving Shell starts outside the trigger. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout", meta = (ClampMin = "0"))
	float ExitClearance = 300.f;

	/** End of the intake curve: this far past the lens centre, inside the shaft. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AOS|Transit|Layout", meta = (ClampMin = "0"))
	float IntakeDepth = 300.f;

	UFUNCTION()
	void HandleEntranceOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

private:
	FVector LocalEntryAxis() const;
	void ApplyLayout();
	void TickIntake(float DeltaSeconds);
	void TickFade(float DeltaSeconds);
	void CompleteWarp();
	void AbortTransit(const TCHAR* Reason);
	/** Re-enables physics on the Shell and gives it Velocity. */
	static void ReleaseShell(AShellPawn* Shell, const FVector& Velocity);
	/** Cockpit terminal line, mirrored to LogAOSTransit. */
	static void TerminalLog(AShellPawn* Shell, const FString& Message, uint8 Severity);

	EAOSTransitPhase Phase = EAOSTransitPhase::Idle;
	float PhaseTime = 0.f;
	double CooldownUntil = -1.0;

	TWeakObjectPtr<AShellPawn> TransitShell;
	TWeakObjectPtr<AAOSTeleportStation> TransitTarget;

	FVector IntakeStart = FVector::ZeroVector;
	FVector IntakeStartVelocity = FVector::ZeroVector;
	FVector IntakeEnd = FVector::ZeroVector;
	FVector EntryWorld = FVector::DownVector;
	FQuat IntakeStartQuat = FQuat::Identity;
	FQuat IntakeTargetQuat = FQuat::Identity;
};
