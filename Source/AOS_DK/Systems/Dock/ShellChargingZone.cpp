#include "ShellChargingZone.h"

#include "AOS_DK/Core/UI/AOSDraculaPalette.h"
#include "AOS_DK/Submarine/Energy/ShellEnergyComponent.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"
#include "Components/BoxComponent.h"
#include "Components/PointLightComponent.h"
#include "GameFramework/PlayerController.h"
#include "TimerManager.h"

AShellChargingZone::AShellChargingZone()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.f;

	ChargeVolume = CreateDefaultSubobject<UBoxComponent>(TEXT("ChargeVolume"));
	RootComponent = ChargeVolume;
	ChargeVolume->SetBoxExtent(FVector(560.f, 460.f, 600.f));
	ChargeVolume->SetCollisionProfileName(TEXT("Trigger"));
	ChargeVolume->SetGenerateOverlapEvents(true);
	ChargeVolume->ShapeColor = FColor(80, 250, 123);

	BeaconLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("BeaconLight"));
	BeaconLight->SetupAttachment(ChargeVolume);
	BeaconLight->SetRelativeLocation(FVector(0.f, 0.f, 220.f));
	BeaconLight->SetIntensityUnits(ELightUnits::Candelas);
	BeaconLight->SetIntensity(BeaconIdleIntensity);
	BeaconLight->SetAttenuationRadius(900.f);
	BeaconLight->SetLightColor(AOSDracula::Green());
	BeaconLight->SetCastShadows(false);
}

void AShellChargingZone::BeginPlay()
{
	Super::BeginPlay();
	ChargeVolume->OnComponentBeginOverlap.AddDynamic(this, &AShellChargingZone::OnVolumeBeginOverlap);
	ChargeVolume->OnComponentEndOverlap.AddDynamic(this, &AShellChargingZone::OnVolumeEndOverlap);
	// Shells already moored inside at level start (overlaps are resolved after the first frame).
	GetWorldTimerManager().SetTimerForNextTick(this, &AShellChargingZone::ScanInitialOverlaps);
}

void AShellChargingZone::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	for (const TWeakObjectPtr<AShellPawn>& Shell : ChargingShells)
	{
		if (AShellPawn* Ptr = Shell.Get())
		{
			if (UShellEnergyComponent* Energy = Ptr->GetEnergy())
			{
				Energy->RemoveChargeSource(this);
			}
			if (USubDroneBayComponent* Bay = Ptr->GetDroneBay())
			{
				Bay->SetServiceStationLinked(this, false);
			}
		}
	}
	ChargingShells.Reset();
	Super::EndPlay(EndPlayReason);
}

void AShellChargingZone::ScanInitialOverlaps()
{
	TArray<AActor*> Overlapping;
	ChargeVolume->GetOverlappingActors(Overlapping, AShellPawn::StaticClass());
	for (AActor* Actor : Overlapping)
	{
		RefreshShell(Cast<AShellPawn>(Actor));
	}
}

void AShellChargingZone::OnVolumeBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
	int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	RefreshShell(Cast<AShellPawn>(OtherActor));
}

void AShellChargingZone::OnVolumeEndOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp, int32 OtherBodyIndex)
{
	RefreshShell(Cast<AShellPawn>(OtherActor));
}

void AShellChargingZone::RefreshShell(AShellPawn* Shell)
{
	if (!Shell)
	{
		return;
	}
	UShellEnergyComponent* Energy = Shell->GetEnergy();
	if (!Energy)
	{
		return;
	}
	const bool bInside = ChargeVolume->IsOverlappingActor(Shell);
	const bool bPiloted = Cast<APlayerController>(Shell->GetController()) != nullptr;
	const bool bShouldCharge = bInside && (!bRequirePilot || bPiloted);
	const bool bWasCharging = ChargingShells.Contains(Shell);

	if (bShouldCharge && !bWasCharging)
	{
		ChargingShells.Add(Shell);
		Energy->AddChargeSource(this, ChargeRatePercentPerSecond);
	}
	else if (!bShouldCharge && bWasCharging)
	{
		ChargingShells.Remove(Shell);
		Energy->RemoveChargeSource(this);
	}
	if (USubDroneBayComponent* Bay = Shell->GetDroneBay())
	{
		Bay->SetServiceStationLinked(this, bShouldCharge && bRearmDrones);
	}
}

void AShellChargingZone::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Re-evaluate the pilot requirement and drop destroyed Shells (cheap: usually 0-1 entries).
	for (int32 i = ChargingShells.Num() - 1; i >= 0; --i)
	{
		if (!ChargingShells[i].IsValid())
		{
			ChargingShells.RemoveAt(i);
		}
		else if (bRequirePilot)
		{
			RefreshShell(ChargingShells[i].Get());
		}
	}

	bool bActive = false;
	for (const TWeakObjectPtr<AShellPawn>& Shell : ChargingShells)
	{
		const UShellEnergyComponent* Energy = Shell.IsValid() ? Shell->GetEnergy() : nullptr;
		bActive |= Energy && !Energy->IsDepleted() && Energy->GetEnergyFraction() < 0.999f;
	}
	BeaconTime += DeltaSeconds;
	BeaconBlend = FMath::FInterpTo(BeaconBlend, bActive ? 1.f : 0.f, DeltaSeconds, 3.f);
	const float Pulse = 0.5f + 0.5f * FMath::Sin(BeaconTime * 2.f * PI * BeaconPulseHz);
	BeaconLight->SetIntensity(FMath::Lerp(BeaconIdleIntensity, BeaconChargeIntensity * (0.55f + 0.45f * Pulse), BeaconBlend));
}
