#pragma once

#include "CoreMinimal.h"
#include "NavAreas/NavArea.h"
#include "AOS_NavArea_Brine.generated.h"

/**
 * Navigation area of the heap brine pool (Lab 5, Task 3). Traversal cost 3x: patrol pathfinding (default filter) routes
 * around the pool when a detour is cheaper, while a chase that overrides the cost reaches the target straight through it.
 */
UCLASS(MinimalAPI)
class UAOS_NavArea_Brine : public UNavArea
{
	GENERATED_BODY()

public:
	UAOS_NavArea_Brine();
};
