#include "ManSaveSubsystem.h"

void UManSaveSubsystem::AddPage(FName PageName, EAddPageResult& Result)
{
	if (PageName.IsNone() || PageName.IsValid())
	{
		Result = EAddPageResult::Error;
		return;
	}
	if (CollectedPages.Contains(PageName))
	{
		Result = EAddPageResult::DuplicatePage;
		return;
	}
	CollectedPages.Add(PageName);
	Result = EAddPageResult::Success;
}

bool UManSaveSubsystem::HasPage(FName PageName) const
{
	if (CollectedPages.Contains(PageName))
	{
		return true;
	}
	return false;
}