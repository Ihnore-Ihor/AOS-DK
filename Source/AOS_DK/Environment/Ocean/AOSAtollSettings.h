#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "AOSAtollSettings.generated.h"

/**
 * Pontoon Atoll calm-lagoon mask (Urban Bible 2.3-2.5), live Lvl_FirstPerson anchor.
 * Single source for the CPU mask (water queries, fluid physics), MPC_AOS_Atoll (GPU) and the Taylor curtains.
 */
UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "AOS Atoll"))
class AOS_DK_API UAOSAtollSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	virtual FName GetCategoryName() const override { return FName(TEXT("Game")); }

	static const UAOSAtollSettings* Get() { return GetDefault<UAOSAtollSettings>(); }

	/** Wave amplitude scale at a world XY: 0 inside RCalm, smoothstep to 1 at RFull. */
	float WaveScaleAt(double X, double Y) const;

	/** Mask centre (ring centre of the breakwater), world XY. */
	UPROPERTY(Config, EditAnywhere, Category = "Wave Mask")
	FVector2D Center = FVector2D(-1000.0, 700.0);

	UPROPERTY(Config, EditAnywhere, Category = "Wave Mask", meta = (ClampMin = "0", Units = "cm"))
	float RCalm = 11200.f;

	UPROPERTY(Config, EditAnywhere, Category = "Wave Mask", meta = (ClampMin = "1", Units = "cm"))
	float RFull = 15200.f;

	/** BC-R bubble line. */
	UPROPERTY(Config, EditAnywhere, Category = "Foam", meta = (ClampMin = "0", Units = "cm"))
	float RingFoamR = 11000.f;

	UPROPERTY(Config, EditAnywhere, Category = "Foam", meta = (ClampMin = "1", Units = "cm"))
	float RingFoamWidth = 120.f;

	/** Ocean gate azimuths, degrees from +X counter-clockwise. The GPU mask uses the first three. */
	UPROPERTY(Config, EditAnywhere, Category = "Gates")
	TArray<float> GateAzimuthsDeg = { 180.f, 60.f, 300.f };

	UPROPERTY(Config, EditAnywhere, Category = "Gates", meta = (ClampMin = "0.001"))
	float GateHalfAngleRad = 0.0667f;

	/** Radius of the gate Taylor pipe lines (curtain + gate foam centre line). */
	UPROPERTY(Config, EditAnywhere, Category = "Gates", meta = (ClampMin = "0", Units = "cm"))
	float GateCurtainR = 12120.f;

	/** Radial half width of the gate foam band. */
	UPROPERTY(Config, EditAnywhere, Category = "Gates", meta = (ClampMin = "1", Units = "cm"))
	float GateFoamWidth = 400.f;

	UPROPERTY(Config, EditAnywhere, Category = "Gates", meta = (ClampMin = "0", ClampMax = "1"))
	float GateFoamStrength = 0.9f;
};

namespace AOSAtoll
{
	/** Shared CPU mask: 0 in the lagoon, 1 in the open ocean. */
	AOS_DK_API float WaveScale(const FVector& WorldPosition);
}
