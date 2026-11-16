#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AOSSafeGroundTracker.generated.h"

class ACharacter;

DECLARE_LOG_CATEGORY_EXTERN(LogAOSFallRecovery, Log, All);

/**
 * Surface Fall Recovery, part 1 (Urban Bible 4.5): remembers where the owning character last stood on safe ground.
 *
 * While the owner walks (IsMovingOnGround) the tracker polls at PollInterval (4 Hz). If the floor under the feet is
 * tagged SafeGround (actor tag or component tag) and every edge probe around the feet also finds ground, the pose is
 * pushed into an 8-slot ring buffer. AAOSFallRecoveryVolume reads the newest pose to teleport the character back.
 */
UCLASS(ClassGroup = (AOS), meta = (BlueprintSpawnableComponent))
class AOS_DK_API UAOSSafeGroundTracker : public UActorComponent
{
	GENERATED_BODY()

public:
	UAOSSafeGroundTracker();

	/** Number of recovery poses kept (Bible 4.5: 8). */
	static constexpr int32 RingCapacity = 8;

	/** Tag (on the floor actor or the floor component) marking a surface that is safe to return to. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SafeGround")
	FName SafeGroundTag = TEXT("SafeGround");

	/** Seconds between polls while walking. 0.25 = 4 Hz. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SafeGround", meta = (ClampMin = "0.05", Units = "s"))
	float PollInterval = 0.25f;

	/** A pose is recorded only if ground exists at this horizontal distance from the feet in 8 directions. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SafeGround|Edge", meta = (ClampMin = "0.0", Units = "cm"))
	float EdgeClearanceRadius = 55.f;

	/** Radius of the sphere swept by every edge probe (wider than the 6 cm seam between pontoons). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SafeGround|Edge", meta = (ClampMin = "1.0", Units = "cm"))
	float EdgeProbeRadius = 12.f;

	/** How far below the feet an edge probe looks for ground. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "SafeGround|Edge", meta = (ClampMin = "1.0", Units = "cm"))
	float EdgeProbeDrop = 90.f;

	/** Newest recorded pose (capsule centre, yaw of the view). False while the buffer is empty. */
	UFUNCTION(BlueprintCallable, Category = "SafeGround")
	bool GetLatestSafeTransform(FTransform& OutTransform) const;

	/** All recorded poses, newest first. */
	UFUNCTION(BlueprintCallable, Category = "SafeGround")
	TArray<FTransform> GetSafeTransformsNewestFirst() const;

	UFUNCTION(BlueprintPure, Category = "SafeGround")
	int32 GetNumSafeTransforms() const { return RingCount; }

	UFUNCTION(BlueprintCallable, Category = "SafeGround")
	void ClearSafeTransforms();

	/** Pushes a pose into the ring (overwrites the oldest slot once 8 are stored). */
	UFUNCTION(BlueprintCallable, Category = "SafeGround")
	void PushSafeTransform(const FTransform& Pose);

	/** Latches a recovery for the owner. False if one is already running (overlapping volumes, repeated overlaps). */
	bool TryBeginRecovery();
	void EndRecovery();

	UFUNCTION(BlueprintPure, Category = "SafeGround")
	bool IsRecovering() const { return bRecovering; }

protected:
	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	bool IsStandingOnSafeGround(const ACharacter& Character) const;
	bool IsClearOfEdges(const ACharacter& Character) const;

	UPROPERTY(Transient)
	TObjectPtr<ACharacter> OwnerCharacter;

	TArray<FTransform> Ring;
	int32 RingHead = 0;
	int32 RingCount = 0;
	bool bRecovering = false;
};
