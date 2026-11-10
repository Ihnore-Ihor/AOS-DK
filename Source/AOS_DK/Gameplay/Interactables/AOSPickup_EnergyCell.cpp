#include "AOSPickup_EnergyCell.h"
#include "Components/PointLightComponent.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "AOS_DK/Submarine/Energy/ShellEnergyComponent.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

AAOSPickup_EnergyCell::AAOSPickup_EnergyCell()
{
	Glow->SetLightColor(AOSDracula::Yellow());
}

bool AAOSPickup_EnergyCell::CanApplyPickup(const AShellPawn* Shell) const
{
	const UShellEnergyComponent* Energy = Shell ? Shell->GetEnergy() : nullptr;
	return Energy && !Energy->IsDepleted() && !(bRequireMissingEnergy && Energy->GetEnergyFraction() >= 0.999f);
}

FText AAOSPickup_EnergyCell::GetSalvageLabel() const
{
	return FText::Format(NSLOCTEXT("AOSPickup", "SalvageEnergy", "SALVAGE ENERGY (+{0}%)"), FText::AsNumber(FMath::RoundToInt(EnergyAmount)));
}

bool AAOSPickup_EnergyCell::ApplyPickup(AShellPawn* Shell)
{
	UShellEnergyComponent* Energy = Shell ? Shell->GetEnergy() : nullptr;
	if (!CanApplyPickup(Shell))
	{
		return false;
	}
	const float Added = Energy->AddEnergy(EnergyAmount);
	if (Added <= 0.f && bRequireMissingEnergy)
	{
		return false;
	}
	Shell->PushTerminalLog(TEXT("core"), FString::Printf(TEXT("energy cell absorbed +%.0f%% - core %d%%"),
		Added, FMath::RoundToInt(Energy->GetEnergyFraction() * 100.f)), EAOSHudLogSeverity::Charge);
	return true;
}
