#pragma once

#include "CoreMinimal.h"
#include "NavFilters/NavigationQueryFilter.h"
#include "AOS_NavFilter_ReaperChase.generated.h"

/**
 * Navigation query filter used while the Reaper is hunting the Shell (Hostile pursuit): the heap-brine area costs the standard
 * ground cost (1.0) instead of its patrol cost (UAOS_NavArea_Brine::DefaultCost = 3), so the chase goes straight through the pool.
 */
UCLASS(MinimalAPI)
class UAOS_NavFilter_ReaperChase : public UNavigationQueryFilter
{
	GENERATED_BODY()

public:
	UAOS_NavFilter_ReaperChase();
};
