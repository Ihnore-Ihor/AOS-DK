#include "HudTerminalLog.h"
#include "AOS_DK/Core/UI/HUD/AOSHudPainter.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

UAOSHudTerminalLog::UAOSHudTerminalLog(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	DesignSize = FVector2D(560.0, 210.0);
	PlateColor = AOSDracula::WithAlpha(AOSDracula::Mix(AOSDracula::Background(), FLinearColor::Black, 0.7f), 0.72f); // black, translucent
	MessageColor = AOSDracula::Foreground();

	// Designer preview = sketch.
	FLogLine A;
	A.Source = TEXT("shell"); A.Message = TEXT("damage 5%"); A.Severity = EAOSHudLogSeverity::Damage; A.Age = 2.f; A.Row = 1.f;
	FLogLine B;
	B.Source = TEXT("gyro"); B.Message = TEXT("horizon locked - stabilizer idle"); B.Severity = EAOSHudLogSeverity::Info; B.Age = 2.f; B.Row = 0.f;
	Lines.Add(A);
	Lines.Add(B);
}

void UAOSHudTerminalLog::AddLine(const FString& Source, const FString& Message, EAOSHudLogSeverity Severity)
{
	if (Lines.Num() > 0)
	{
		FLogLine& Last = Lines.Last();
		if (Last.Source == Source && Last.Message == Message && Last.Age < MergeWindow + HoldTime)
		{
			++Last.Count;
			Last.Age = FMath::Min(Last.Age, (Source.Len() + Message.Len() + 2) / CharsPerSecond);
			return;
		}
	}
	FLogLine Line;
	Line.Source = Source;
	Line.Message = Message;
	Line.Severity = Severity;
	Line.Row = -1.f; // slides in from below
	Lines.Add(MoveTemp(Line));

	// Oldest lines beyond the limit jump straight to their fade-out.
	const int32 Excess = Lines.Num() - MaxLines;
	for (int32 i = 0; i < Excess; ++i)
	{
		Lines[i].Age = FMath::Max(Lines[i].Age, HoldTime);
	}
}

void UAOSHudTerminalLog::ClearLog()
{
	Lines.Reset();
}

void UAOSHudTerminalLog::AdvanceHud(float DeltaSeconds)
{
	Super::AdvanceHud(DeltaSeconds);
	if (IsDesignTime())
	{
		return;
	}
	for (int32 i = Lines.Num() - 1; i >= 0; --i)
	{
		Lines[i].Age += DeltaSeconds;
		if (Lines[i].Age > HoldTime + FadeTime)
		{
			Lines.RemoveAt(i);
		}
	}
	// Smooth stacking: row 0 = newest (bottom).
	for (int32 i = 0; i < Lines.Num(); ++i)
	{
		const float TargetRow = float(Lines.Num() - 1 - i);
		Lines[i].Row = AOSHudMath::Approach(Lines[i].Row, TargetRow, 14.f, DeltaSeconds);
	}
}

FLinearColor UAOSHudTerminalLog::GetSeverityColor(EAOSHudLogSeverity Severity) const
{
	switch (Severity)
	{
	case EAOSHudLogSeverity::System:  return AOSDracula::Purple();
	case EAOSHudLogSeverity::Charge:  return AOSDracula::Green();
	case EAOSHudLogSeverity::Warning: return AOSDracula::Orange();
	case EAOSHudLogSeverity::Damage:  return AOSDracula::Red();
	case EAOSHudLogSeverity::Fatal:   return AOSDracula::Red();
	default:                          return AOSDracula::Cyan();
	}
}

void UAOSHudTerminalLog::PaintHud(FAOSHudPainter& P) const
{
	const float Bottom = P.Extent().Y - 4.f;
	const float PlateH = RowHeight - 5.f;

	for (const FLogLine& Line : Lines)
	{
		const float FadeAlpha = 1.f - FMath::Clamp((Line.Age - HoldTime) / FMath::Max(FadeTime, 0.01f), 0.f, 1.f);
		const float InAlpha = FMath::Clamp(Line.Age / 0.08f, 0.f, 1.f);
		const float Alpha = FadeAlpha * InAlpha;
		if (Alpha <= 0.01f)
		{
			continue;
		}
		const float Y = Bottom - (Line.Row + 1.f) * RowHeight + 5.f;
		const float MidY = Y + PlateH * 0.5f;
		const FLinearColor SevColor = GetSeverityColor(Line.Severity);

		// Typed text: "source: message" revealed char by char.
		const FString Prefix = Line.Source + TEXT(": ");
		const int32 TotalChars = Prefix.Len() + Line.Message.Len();
		const int32 Visible = FMath::Clamp(FMath::FloorToInt(Line.Age * CharsPerSecond), 0, TotalChars);
		const bool bTyping = Visible < TotalChars;
		const FString PrefixVisible = Prefix.Left(Visible);
		const FString MessageVisible = Line.Message.Left(FMath::Max(0, Visible - Prefix.Len()));
		const FString CountText = (Line.Count > 1 && !bTyping) ? FString::Printf(TEXT("  x%d"), Line.Count) : FString();

		// Plate sized to the FULL line (no width jitter while typing).
		const float FullWidth = P.MeasureText(Prefix + Line.Message + CountText, Font, FontSize).X;
		const float PlateW = FullWidth + 26.f;
		const FLinearColor Plate = Line.Severity == EAOSHudLogSeverity::Fatal
			? AOSDracula::Mix(PlateColor, AOSDracula::WithAlpha(AOSDracula::Red(), PlateColor.A), 0.25f)
			: PlateColor;
		P.FillRect(FVector2f(0.f, Y), FVector2f(PlateW, Y + PlateH), AOSDracula::WithAlpha(Plate, Plate.A * Alpha));
		P.FillRect(FVector2f(0.f, Y), FVector2f(3.f, Y + PlateH), AOSDracula::WithAlpha(SevColor, Alpha));

		float X = 12.f;
		X += P.Text(PrefixVisible, Font, FontSize, FVector2f(X, MidY), FVector2f(0.f, 0.5f), AOSDracula::WithAlpha(SevColor, Alpha)).X;
		const FLinearColor MsgColor = Line.Severity == EAOSHudLogSeverity::Fatal ? AOSDracula::Red() : MessageColor;
		X += P.Text(MessageVisible, Font, FontSize, FVector2f(X, MidY), FVector2f(0.f, 0.5f), AOSDracula::WithAlpha(MsgColor, Alpha)).X;
		if (!CountText.IsEmpty())
		{
			P.Text(CountText, Font, FontSize, FVector2f(X, MidY), FVector2f(0.f, 0.5f), AOSDracula::WithAlpha(AOSDracula::Comment(), Alpha));
		}
		if (bTyping || (FMath::Frac(HudTime * 1.6f) < 0.5f && &Line == &Lines.Last()))
		{
			// Block cursor after the newest line.
			const float CursorH = FontSize * 1.1f;
			P.FillRect(FVector2f(X + 2.f, MidY - CursorH * 0.5f), FVector2f(X + 2.f + FontSize * 0.55f, MidY + CursorH * 0.5f),
				AOSDracula::WithAlpha(AOSDracula::Foreground(), 0.7f * Alpha));
		}
	}
}
