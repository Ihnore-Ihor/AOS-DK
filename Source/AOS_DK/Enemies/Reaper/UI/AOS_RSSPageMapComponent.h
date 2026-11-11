#pragma once

#include "CoreMinimal.h"
#include "ProceduralMeshComponent.h"
#include "AOS_DK/Enemies/Reaper/AOS_ReaperTypes.h"
#include "AOS_RSSPageMapComponent.generated.h"

class UTextRenderComponent;
class UMaterialInterface;

/**
 * "RSS Page Map": the Reaper's 3D world-space health display. A 4 x 4 grid of extruded memory-page prisms (16 resident pages =
 * full health), 3 decoy-charge pips and an evasion-readiness border, all generated as one procedural mesh (vertex colours).
 *  - 1 torpedo hit frees one page: it flashes white, then ejects towards the viewer and shrinks away.
 *  - Frame colour = alert state: Cyan (patrol) -> Yellow (investigate) -> Orange (combat) -> Red flicker (HP <= 25 %) -> Purple (brine).
 *  - Billboarded to the player's camera; follows SOCKET_UI_Health through a critically damped spring.
 * Not UMG, not Slate: a plain mesh, so it is depth-tested and hidden behind pillars.
 */
UCLASS(ClassGroup = (AOS_DK), meta = (BlueprintSpawnableComponent))
class AOS_DK_API UAOS_RSSPageMapComponent : public UProceduralMeshComponent
{
	GENERATED_BODY()

public:
	UAOS_RSSPageMapComponent(const FObjectInitializer& ObjectInitializer);

	virtual void OnRegister() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	void SetOwnerLabel(int32 InPID);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Reaper|PageMap")
	void SetHealth(float Current, float Max);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Reaper|PageMap")
	void SetAlert(EAOSPageAlert InAlert);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Reaper|PageMap")
	void SetDecoyCharges(int32 Charges, int32 MaxCharges);

	/** 0..1 border fill (refills over the dodge cooldown). */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Reaper|PageMap")
	void SetEvasionReadiness(float Readiness);

	/** Death: all remaining pages flash and eject radially, label switches to "exit 137", component destroys itself. */
	UFUNCTION(BlueprintCallable, Category = "AOS_DK|Reaper|PageMap")
	void PlayDeathRelease();

	UFUNCTION(BlueprintPure, Category = "AOS_DK|Reaper|PageMap")
	int32 GetResidentPages() const { return ResidentPages; }

	// ---- tuning ----------------------------------------------------------------------------------------------------------
	static constexpr int32 GridDim = 4;
	static constexpr int32 NumPages = GridDim * GridDim;
	static constexpr int32 NumPips = 3;
	static constexpr int32 BorderSegments = 64;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|PageMap", meta = (ClampMin = "0", Units = "cm"))
	float MaxVisibleDistance = 8000.f;

	/** World scale of the whole display (the raw plate is 52 cm tall; 3.4 makes it ~1.8 m, readable from the Shell cockpit). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|PageMap", meta = (ClampMin = "0.1"))
	float DisplayScale = 3.4f;

	/** Height above SOCKET_UI_Health (the top of the chassis capsule), cm. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|PageMap", meta = (Units = "cm"))
	float HeightAboveSocket = 100.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|PageMap", meta = (ClampMin = "0.1"))
	float FollowOmega = 8.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|PageMap", meta = (ClampMin = "0.01"))
	float EjectDuration = 0.4f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|PageMap", meta = (ClampMin = "0.01"))
	float FlashDuration = 0.15f;

	/** Material (Unlit, Emissive = VertexColor * Intensity). Falls back to the engine vertex-colour material. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|PageMap")
	TSoftObjectPtr<UMaterialInterface> PageMaterial;

	/** true: the display is on whenever a player camera is within MaxVisibleDistance (default). false: only when hurt / alerted / aimed at. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|Reaper|PageMap")
	bool bAlwaysVisible = true;

protected:
	virtual void BeginPlay() override;
	virtual void OnComponentDestroyed(bool bDestroyingHierarchy) override;

private:
	struct FPageState
	{
		bool bResident = true;
		float FlashTime = 0.f;   // > 0: white flash running
		float EjectTime = -1.f;  // >= 0: ejecting
		bool bGone = false;
	};

	void RebuildMesh();
	void BuildTopology();
	bool ShouldBeVisible(const FVector& CameraLocation, const FVector& CameraForward, float& OutDistance) const;
	FLinearColor ResidentColor() const;
	void UpdateTexts();

	FPageState Pages[NumPages];
	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UVs;
	TArray<FLinearColor> Colors;
	TArray<FProcMeshTangent> Tangents;
	bool bSectionCreated = false;
	bool bDirty = true;

	float Health = 1.f;
	float MaxHealth = 1.f;
	int32 ResidentPages = NumPages;
	EAOSPageAlert Alert = EAOSPageAlert::Patrol;
	int32 DecoyCharges = 3;
	int32 DecoyMax = 3;
	float Readiness = 1.f;
	int32 PID = 0;
	bool bReleasing = false;
	float ReleaseTime = 0.f;
	FVector SmoothedLocation = FVector::ZeroVector;
	FVector SmoothedVelocity = FVector::ZeroVector;
	bool bHaveSmoothed = false;
	float Clock = 0.f;
	bool bShown = true;

	UPROPERTY(Transient)
	TObjectPtr<UTextRenderComponent> LabelText;

	UPROPERTY(Transient)
	TObjectPtr<UTextRenderComponent> CountText;
};
