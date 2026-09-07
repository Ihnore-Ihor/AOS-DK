#include "TerminalActor.h"

void ATerminalActor::BeginPlay()
{
	Super::BeginPlay();
	
	//insert all available commands from CommandsInfo
	if (CommandDataTable)
	{
		for (FName Command : CommandDataTable->GetRowNames())
		{
			Commands.Add(Command.ToString().ToLower());
		}
	}
}

FString ATerminalActor::ProcessInput(FString RawInput)
{
	if (RawInput.IsEmpty()) //user pressed Enter on an empty prompt
	{
		return "";
	} 
	if (RawInput.StartsWith("#")) // user entered comment 
	{
		return ""; //but save in history chat as an entered command
	}
	TArray<FString> InputTokens; 
	RawInput.ParseIntoArray(InputTokens, TEXT(" "),true);
	
	FString InputCommand = InputTokens[0].ToLower();
	if (InputCommand == "help")
	{
		return HelpCommandFormer();
	}
	//rest of the commands
	return FString::Printf(TEXT("bash: %s: command not found"), *InputCommand);
}


FString ATerminalActor::HelpCommandFormer() const
{
	FString Output = "Available Commands:\n\n"; // Two \n for a nice top margin
    
	if (CommandDataTable)
	{
		int LongestLeftColumn = 0;
		TArray<FName> RowNames = CommandDataTable->GetRowNames();
		// 1. CORRECT CALCULATION OF THE MAXIMUM WIDTH
		for (FName CommandName : RowNames)
		{
			// Check the length of the command itself
			LongestLeftColumn = FMath::Max(LongestLeftColumn, CommandName.ToString().Len());
          
			FCommandsInfo* CommandRowInfo = CommandDataTable->FindRow<FCommandsInfo>(CommandName, TEXT("Length Check"));
			if (CommandRowInfo)
			{
				// Check the length of the syntax (+4 spaces of indentation)
				for (auto& [Key, Value]: CommandRowInfo->Syntax)
				{
					LongestLeftColumn = FMath::Max(LongestLeftColumn, Key.Len() + 4);
				}
			}
		}
		// 2. FORMING THE OUTPUT
		for (FName CommandName : RowNames)
		{
			FCommandsInfo* CommandRowInfo = CommandDataTable->FindRow<FCommandsInfo>(CommandName, TEXT("Terminal call help"));
			if (!CommandRowInfo) continue; // Protection against null
          
			// Output the main command
			Output.Append(HelpCommandTextWrapper(LongestLeftColumn, CommandName.ToString(), CommandRowInfo->Description));
			// Output the syntaxes with indentation
			for (auto& [Key, Value]: CommandRowInfo->Syntax)
			{
				// SIMPLE MAGIC: add 4 spaces directly into the string!
				FString IndentedKey = TEXT("    ") + Key;
				Output.Append(HelpCommandTextWrapper(LongestLeftColumn, IndentedKey, Value));
			}
          
			// Empty line between command blocks for better readability
			Output.Append("\n");
		}
	}
    
	return Output;
}

FString ATerminalActor::HelpCommandTextWrapper(const int LongestLeftLength, const FString &LeftText, const FString &RightText, int RowLength) const
{
	// 1. Form the left part. %-*s will automatically pad the short text with spaces.
	FString Output = FString::Printf(TEXT("%-*s    "), LongestLeftLength, *LeftText);

	// 2. Calculate the column widths
	int LeftOffset = LongestLeftLength + 4; // Width of the left part + 4 spaces of indentation
	int MaxRightWidth = RowLength - LeftOffset;

	// 3. Split the right text into words
	TArray<FString> Words;
	RightText.ParseIntoArray(Words, TEXT(" "), true);

	int CurrentLineLength = 0;

	for (int32 i = 0; i < Words.Num(); ++i)
	{
		FString Word = Words[i];

		// How much space does this word need? (The word itself + 1 space if it's not the first in the line)
		int SpaceNeeded = Word.Len() + (CurrentLineLength > 0 ? 1 : 0);

		// If adding this word will exceed the column limit
		if (CurrentLineLength + SpaceNeeded > MaxRightWidth)
		{
			// Wrap to a new line
			Output.Append(TEXT("\n"));
			// Add empty indentation on the left so the text stays in the right column
			Output.Append(FString::ChrN(LeftOffset, ' ')); 
           
			// Now this is the first word on the new line
			CurrentLineLength = 0; 
		}
		else if (CurrentLineLength > 0)
		{
			// If the line is not empty and there is space - add a space before the word
			Output.Append(TEXT(" "));
			CurrentLineLength += 1;
		}

		// Add the word itself and increase the counter
		Output.Append(Word);
		CurrentLineLength += Word.Len();
	}

	Output.Append(TEXT("\n")); // Close the entire block with a line break
	return Output;
}
