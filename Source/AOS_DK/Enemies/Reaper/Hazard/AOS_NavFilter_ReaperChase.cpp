#include "AOS_NavFilter_ReaperChase.h"
#include "AOS_NavArea_Brine.h"

UAOS_NavFilter_ReaperChase::UAOS_NavFilter_ReaperChase()
{
	AddTravelCostOverride(UAOS_NavArea_Brine::StaticClass(), 1.0f);
	AddEnteringCostOverride(UAOS_NavArea_Brine::StaticClass(), 0.0f);
}
