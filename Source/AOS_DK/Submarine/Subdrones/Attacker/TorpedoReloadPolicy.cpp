#include "AOS_DK/Submarine/Subdrones/Attacker/TorpedoReloadPolicy.h"

#include "AOS_DK/Submarine/Subdrones/Attacker/SubDrone_Attacker.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"

int32 UTorpedoReloadPolicy_DockResupply::TickReserveResupply(ASubDrone_Attacker& Drone, float DeltaSeconds)
{
	if (!Drone.IsBeingServiced() || Drone.IsReserveFull())
	{
		Accumulator = 0.f;
		return 0;
	}

	Accumulator += DeltaSeconds;
	int32 Count = FMath::FloorToInt32(Accumulator / SecondsPerTorpedo);
	Accumulator -= Count * SecondsPerTorpedo;

	if (Count > 0)
	{
		if (USubDroneBayComponent* Bay = Drone.GetBay())
		{
			Count = Bay->RequestMunitionResupply(&Drone, Count); // Shell stock gate (RAM inventory later)
		}
	}
	return Count;
}
