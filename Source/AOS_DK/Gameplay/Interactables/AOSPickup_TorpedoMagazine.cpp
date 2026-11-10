#include "AOSPickup_TorpedoMagazine.h"
#include "Components/PointLightComponent.h"
#include "Engine/World.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"
#include "AOS_DK/Submarine/Subdrones/Attacker/SubDrone_Attacker.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

AAOSPickup_TorpedoMagazine::AAOSPickup_TorpedoMagazine()
{
	Glow->SetLightColor(AOSDracula::Pink());
}

ASubDrone_Attacker* AAOSPickup_TorpedoMagazine::FindAttacker(const AShellPawn* Shell)
{
	const USubDroneBayComponent* Bay = Shell ? Shell->GetDroneBay() : nullptr;
	if (!Bay)
	{
		return nullptr;
	}
	for (int32 Slot = 0; Slot < Bay->GetNumSlots(); ++Slot)
	{
		if (ASubDrone_Attacker* Attacker = Cast<ASubDrone_Attacker>(Bay->GetDrone(Slot)))
		{
			return Attacker;
		}
	}
	return nullptr;
}

bool AAOSPickup_TorpedoMagazine::CanApplyPickup(const AShellPawn* Shell) const
{
	const ASubDrone_Attacker* Attacker = FindAttacker(Shell);
	return Attacker && Attacker->GetReserveAmmo() < Attacker->GetReserveCapacity();
}

FText AAOSPickup_TorpedoMagazine::GetSalvageLabel() const
{
	return FText::Format(NSLOCTEXT("AOSPickup", "SalvageAmmo", "SALVAGE AMMO (+{0})"), FText::AsNumber(TorpedoCount));
}

bool AAOSPickup_TorpedoMagazine::ApplyPickup(AShellPawn* Shell)
{
	ASubDrone_Attacker* Attacker = FindAttacker(Shell);
	const double Now = GetWorld()->GetTimeSeconds();
	if (!Attacker)
	{
		if (Now - LastRefusalLogTime > 3.0)
		{
			LastRefusalLogTime = Now;
			Shell->PushTerminalLog(TEXT("attacker"), TEXT("module offline - torpedo canister left in place"), EAOSHudLogSeverity::Warning);
		}
		return false;
	}
	const int32 Accepted = Attacker->AddToReserve(TorpedoCount);
	if (Accepted <= 0)
	{
		if (Now - LastRefusalLogTime > 3.0)
		{
			LastRefusalLogTime = Now;
			Shell->PushTerminalLog(TEXT("attacker"), FString::Printf(TEXT("reserve full %d/%d - canister left in place"),
				Attacker->GetReserveAmmo(), Attacker->GetReserveCapacity()), EAOSHudLogSeverity::Warning);
		}
		return false;
	}
	Shell->PushTerminalLog(TEXT("attacker"), FString::Printf(TEXT("+%d torpedoes salvaged"), Accepted), EAOSHudLogSeverity::System);
	return true;
}
