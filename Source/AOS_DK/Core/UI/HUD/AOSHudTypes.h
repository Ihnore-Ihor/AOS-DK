#pragma once

#include "CoreMinimal.h"
#include "AOSHudTypes.generated.h"

/** Severity of a cockpit terminal-log line (drives the source/plate colours). */
UENUM(BlueprintType)
enum class EAOSHudLogSeverity : uint8
{
	Info    UMETA(DisplayName = "Info"),
	System  UMETA(DisplayName = "System"),
	Charge  UMETA(DisplayName = "Charge"),
	Warning UMETA(DisplayName = "Warning"),
	Damage  UMETA(DisplayName = "Damage"),
	Fatal   UMETA(DisplayName = "Fatal")
};
