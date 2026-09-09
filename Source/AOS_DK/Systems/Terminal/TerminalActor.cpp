#include "TerminalActor.h"
#include "CommandsInfo/CommandsInfo.h"
#include "DeviceComponent/TerminalDeviceComponent.h"
#include "Misc/Paths.h"

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
	
	CommandRouters.Add("help", [this](const FTerminalCommandContext& Prompt){return HelpCommandFormer(Prompt);});
	CommandRouters.Add("ls", [this](const FTerminalCommandContext& Prompt){return LsCommandFormer(Prompt);});
	CommandRouters.Add("cat", [this](const FTerminalCommandContext& Prompt){return CatCommandFormer(Prompt);});
	CommandRouters.Add("echo", [this](const FTerminalCommandContext& Prompt){return EchoCommandFormer(Prompt);});
}

FString ATerminalActor::ProcessInput(FString RawInput)
{
	if (RawInput.IsEmpty()) //user pressed Enter on an empty prompt
	{
		return "";
	}
	
	FTerminalCommandContext Prompt;
	Prompt.RawPrompt = RawInput;
	
	if (RawInput.StartsWith("#")) // user entered comment 
	{
		return ""; //but save in history chat as an entered command
	}
	
	RawInput.ParseIntoArray(Prompt.ParsedPrompt, TEXT(" "),true);
	
	if (Prompt.ParsedPrompt.IsEmpty()) 
	{
		return "";
	}
	
	FString InputCommand = Prompt.ParsedPrompt[0].ToLower();
	
	if (!Commands.Contains(InputCommand))
	{
		return FString::Printf(TEXT("bash: %s: command not found"), *InputCommand);
	}
	
	if (const auto* CommandFunc = CommandRouters.Find(InputCommand)) 
		return (*CommandFunc)(Prompt);
	
	//rest of the commands
	return FString::Printf(TEXT("bash: %s: logic not implemented yet"), *InputCommand);
}


FString ATerminalActor::HelpCommandFormer(const FTerminalCommandContext& Prompt) const
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

FString ATerminalActor::LsCommandFormer(const FTerminalCommandContext& Prompt) const
{
	// 1. Collect all names and find the longest one
	TArray<FString> DeviceNames;
	int32 MaxLen = 0;
    
	for (AActor* Device : ConnectedDevices)
	{
		if (Device)
		{
			// Looking for OUR component on this Actor
			UTerminalDeviceComponent* TerminalComp = Device->FindComponentByClass<UTerminalDeviceComponent>();
			if (TerminalComp)
			{
				// Take its unique name
				FString Name = TerminalComp->DeviceID;
				// If the level designer forgot to enter a name, give a placeholder so there is no emptiness
				if (Name.IsEmpty()) Name = "unnamed_device";
				DeviceNames.Add(Name);
				MaxLen = FMath::Max(MaxLen, Name.Len());
			}
		}
	}
	// 2. Build the grid
	FString Output = "";
	int32 ColWidth = MaxLen + 4; // Longest name + 4 spaces of padding
	int32 MaxCols = 80 / ColWidth; // How many columns fit into 80 screen characters?
	if (MaxCols < 1) MaxCols = 1;  // Protection: minimum 1 column
	int32 CurrentCol = 0;
	for (FString Name : DeviceNames)
	{
		// Print the name, filling the rest of the column with spaces
		Output.Append(FString::Printf(TEXT("%-*s"), ColWidth, *Name));
		CurrentCol++;
		// If we reached the column limit - wrap to a new line
		if (CurrentCol >= MaxCols)
		{
			Output.Append("\n");
			CurrentCol = 0;
		}
	}
	// Add a final line break if the last row was incomplete
	if (CurrentCol > 0) 
	{
		Output.Append("\n");
	}
	return Output;
}

FString ATerminalActor::CatCommandFormer(const FTerminalCommandContext& Prompt) const
{
	if (Prompt.ParsedPrompt.Num() < 2) return "bash: cat: missing operand";

	FString ErrorMessage, FileName;
	UTerminalDeviceComponent* TargetComp = GetTargetDevice(Prompt.ParsedPrompt[1], FileName, ErrorMessage);
	
	if (!TargetComp) return ErrorMessage;

	if (const FString* FileContent = TargetComp->VirtualFiles.Find(FileName))
	{
		return *FileContent + "\n";
	}

	return FString::Printf(TEXT("bash: %s: No such file or directory"), *Prompt.ParsedPrompt[1]);
}

FString ATerminalActor::EchoCommandFormer(const FTerminalCommandContext& Prompt) const
{
	FString RawInput = Prompt.RawPrompt;
	
	if (RawInput.Len() <= 5) return "\n";
	RawInput = RawInput.Mid(5);
	
	FString LeftText, RightText;
	
	if (RawInput.Split(TEXT(">"), &LeftText, &RightText))
	{
		LeftText.TrimStartAndEndInline();
		if (LeftText.StartsWith("\"") && LeftText.EndsWith("\"")) 
			LeftText = LeftText.Mid(1, LeftText.Len() - 2);
		
		FString ErrorMessage, FileName;
		UTerminalDeviceComponent* TargetComp = GetTargetDevice(RightText, FileName, ErrorMessage);
		
		if (!TargetComp) return ErrorMessage;
		
		EFileUpdateResult UpdateFileResult;
		FString UpdateFileMessage;
		TargetComp->UpdateVirtualFiles(FileName, LeftText, UpdateFileResult, UpdateFileMessage);
		
		if (UpdateFileResult == EFileUpdateResult::Success) return "";
		
		return UpdateFileMessage;
	}
	
	RawInput.TrimStartAndEndInline();
	if (RawInput.StartsWith("\"") && RawInput.EndsWith("\"")) 
		RawInput = RawInput.Mid(1, RawInput.Len() - 2);
	
	return RawInput;
}



UTerminalDeviceComponent* ATerminalActor::GetTargetDevice(const FString& TargetPath, FString& OutFileName, FString& OutErrorMessage) const
{
	FString DevicePath = FPaths::GetPath(TargetPath);
	OutFileName = FPaths::GetCleanFilename(TargetPath);

	for (AActor* Device : ConnectedDevices)
	{
		if (!Device) continue;

		UTerminalDeviceComponent* TerminalComp = Device->FindComponentByClass<UTerminalDeviceComponent>();
		if (TerminalComp)
		{
			if (TerminalComp->DeviceID == TargetPath)
			{
				OutErrorMessage = FString::Printf(TEXT("bash: %s: Is a directory"), *TargetPath);
				return nullptr;
			}
            
			if (TerminalComp->DeviceID == DevicePath)
			{
				return TerminalComp;
			}
		}
	}

	OutErrorMessage = FString::Printf(TEXT("bash: %s: No such file or directory"), *TargetPath);
	return nullptr;
}