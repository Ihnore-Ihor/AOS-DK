#pragma once

#include "CoreMinimal.h"
#include "AOS_DK/Core/UI/HUD/AOSHudElement.h"
#include "HudDroneHoneycomb.generated.h"

/**
 * Readable state of a drone cell. Each state has its own Dracula colour AND motion, so it reads under
 * the blue-green water and without relying on colour alone:
 *  Formation - Purple, calm, thin outline          Deployed - Green, steady, bold outline
 *  Attack    - Pink, fast flicker + firing spark   LowAmmo  - Orange, slow pulse (last magazine)
 *  Depleted  - Red, hard blink, red tint           Service  - Cyan, scanner running around the cell
 */
UENUM(BlueprintType)
enum class EAOSHudDroneStatus : uint8
{
	Empty     UMETA(DisplayName = "Empty slot"),
	Formation UMETA(DisplayName = "Formation (passive escort)"),
	Deployed  UMETA(DisplayName = "Deployed (combat position)"),
	Attack    UMETA(DisplayName = "Attack (firing)"),
	LowAmmo   UMETA(DisplayName = "Low ammo (last magazine)"),
	Depleted  UMETA(DisplayName = "Depleted (no ammo)"),
	Service   UMETA(DisplayName = "Docking / resupply")
};

/** What one honeycomb cell shows. */
USTRUCT(BlueprintType)
struct FAOSHudDroneSlotView
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drone")
	EAOSHudDroneStatus Status = EAOSHudDroneStatus::Empty;

	/** Short module tag ("ATK"). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drone")
	FString Tag;

	/** Two-tier ammo: magnetic ring (tier 1) <- internal reserve (tier 2), counted in ring magazines. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drone")
	bool bHasAmmo = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drone")
	int32 RingAmmo = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drone")
	int32 RingCapacity = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drone")
	int32 ReserveAmmo = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drone")
	int32 ReserveCapacity = 0;

	/** Spinning up / firing. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drone")
	bool bPriming = false;

	/** RMB reload running: the next magazine travels into the ring. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drone")
	bool bReloading = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drone")
	float Heat = 0.f;

	/** Magazines in the reserve, a partly used one included ("[03]"). */
	int32 GetReserveMagazines() const { return RingCapacity > 0 ? FMath::DivideAndRoundUp(FMath::Max(ReserveAmmo, 0), RingCapacity) : 0; }
	/** Bar slots of the reserve (its capacity in magazines). */
	int32 GetReserveSlots() const { return RingCapacity > 0 ? FMath::DivideAndRoundUp(FMath::Max(ReserveCapacity, ReserveAmmo), RingCapacity) : 0; }
	/** Critical remainder: less than one full magazine left in the reserve. */
	bool IsLowAmmo() const { return bHasAmmo && RingCapacity > 0 && ReserveAmmo < RingCapacity; }
	/** Ring and reserve are empty. */
	bool IsDepleted() const { return bHasAmmo && RingAmmo <= 0 && ReserveAmmo <= 0; }
	/** Ring empty but magazines left: the player has to press RMB. */
	bool NeedsReload() const { return bHasAmmo && RingAmmo <= 0 && ReserveAmmo > 0 && !bReloading; }
};

/**
 * Top-right modular drone container: a honeycomb grid, one hexagon per drone slot (Dual-Core = 2 cells).
 * An ammo cell is filled from its top to its bottom edge by strictly HORIZONTAL magazine bars, evenly
 * spaced, one per magazine (1 ring + 7 reserve = 8 by default), light / white with a hint of the state
 * colour. The top bar is the magnetic ring: it thins torpedo by torpedo (32) and goes out when the ring is
 * empty; below it the reserve magazines (the partly used one thinner), spent capacity as faint hairlines.
 * Every bar is a horizontal slice of the hexagon inset by BarPadding, so its ends are cut along the walls
 * (isosceles trapezoids, flush with the border at a uniform gap). The active (ring) bar is set apart by the
 * state accent, a soft neon halo and a thin frame around its full slot - the frame stays when the ring is dry.
 * The labels ("ATK", "32/32", "[07]") sit on one compact dark pill (Dracula Background ~0.82) in bright
 * ink; the bars stay visible above, below and on both sides of it.
 */
UCLASS(meta = (DisplayName = "AOS HUD Drone Honeycomb"))
class AOS_DK_API UAOSHudDroneHoneycomb : public UAOSHudElement
{
	GENERATED_BODY()

public:
	UAOSHudDroneHoneycomb(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetSlotCount(int32 Count);

	UFUNCTION(BlueprintCallable, Category = "AOS_DK|HUD")
	void SetSlotView(int32 SlotIndex, const FAOSHudDroneSlotView& View);

	virtual void AdvanceHud(float DeltaSeconds) override;
	virtual void ResetHud() override;

protected:
	virtual void PaintHud(FAOSHudPainter& Painter) const override;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Honeycomb", meta = (ClampMin = "20"))
	float CellRadius = 56.f;

	/** Follow speed of the bar thickness (1/s). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Honeycomb", meta = (ClampMin = "1"))
	float BarFollowSpeed = 14.f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Honeycomb", meta = (ClampMin = "0.1"))
	float WarningPulseHz = 1.6f;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor FormationColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor DeployedColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor AttackColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor LowAmmoColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor DepletedColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor ServiceColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor EmptyColor;

	/** Loaded magazines: light / white, tinted with the state colour by MagazineTint. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor MagazineColor;

	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style", meta = (ClampMin = "0", ClampMax = "1"))
	float MagazineTint = 0.18f;

	/** Gap between the cell border and the magazine bars, measured perpendicular to the walls. */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Honeycomb", meta = (ClampMin = "0"))
	float BarPadding = 3.5f;

	/** Bar thickness / bar pitch (the rest is the gap). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Honeycomb", meta = (ClampMin = "0.3", ClampMax = "0.95"))
	float BarFillRatio = 0.78f;

	/** Dark backdrop pill under the label block (Dracula Background, translucent). */
	UPROPERTY(EditAnywhere, Category = "AOS_DK|HUD|Style")
	FLinearColor LabelPlateColor;

private:
	/** Animated thickness 0..1 of the bars of one cell: [0] = ring, [1..] = reserve magazines (top -> bottom). */
	struct FCellBars
	{
		TArray<float> Fill;
	};

	FVector2f GetCellCentre(int32 Index) const;
	FLinearColor GetStatusColor(EAOSHudDroneStatus Status) const;
	static void GetBarTargets(const FAOSHudDroneSlotView& View, TArray<float>& OutTargets);
	void PaintCell(FAOSHudPainter& P, int32 Index) const;

	TArray<FAOSHudDroneSlotView> Views;
	TArray<FCellBars> Bars;
};
