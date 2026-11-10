#include "AOSTeleportStation.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/ArrowComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/CollisionProfile.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "AOS_DK/Submarine/ShellPawn.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"

DEFINE_LOG_CATEGORY_STATIC(LogAOSTransit, Log, All);

namespace AOSTransit
{
	static APlayerCameraManager* CameraOf(const AShellPawn* Shell)
	{
		const APlayerController* PC = Shell ? Cast<APlayerController>(Shell->GetController()) : nullptr;
		return PC ? PC->PlayerCameraManager.Get() : nullptr;
	}
}

AAOSTeleportStation::AAOSTeleportStation()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;
	PrimaryActorTick.TickGroup = TG_PrePhysics;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
	SceneRoot->SetMobility(EComponentMobility::Static);

	PortalFrame = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PortalFrame"));
	PortalFrame->SetupAttachment(SceneRoot);
	PortalFrame->SetMobility(EComponentMobility::Static);
	PortalFrame->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
	PortalFrame->SetGenerateOverlapEvents(false);
	PortalFrame->SetCanEverAffectNavigation(false);

	ShaftMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ShaftMesh"));
	ShaftMesh->SetupAttachment(SceneRoot);
	ShaftMesh->SetMobility(EComponentMobility::Static);
	ShaftMesh->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
	ShaftMesh->SetGenerateOverlapEvents(false);
	ShaftMesh->SetCanEverAffectNavigation(false);

	EntranceTrigger = CreateDefaultSubobject<UBoxComponent>(TEXT("EntranceTrigger"));
	EntranceTrigger->SetupAttachment(SceneRoot);
	EntranceTrigger->SetMobility(EComponentMobility::Static);
	EntranceTrigger->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	EntranceTrigger->SetCollisionObjectType(ECC_WorldDynamic);
	EntranceTrigger->SetCollisionResponseToAllChannels(ECR_Ignore);
	EntranceTrigger->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
	EntranceTrigger->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Overlap); // Shell-1 root is a PhysicsBody box
	EntranceTrigger->SetCollisionResponseToChannel(ECC_Vehicle, ECR_Overlap);
	EntranceTrigger->SetGenerateOverlapEvents(true);
	EntranceTrigger->SetCanEverAffectNavigation(false);
	EntranceTrigger->ShapeColor = FColor(139, 233, 253);
	EntranceTrigger->SetBoxExtent(FVector(250.f, 300.f, 300.f));

	ExitPoint = CreateDefaultSubobject<USceneComponent>(TEXT("ExitPoint"));
	ExitPoint->SetupAttachment(SceneRoot);
	ExitPoint->SetMobility(EComponentMobility::Static);

	EntryArrow = CreateDefaultSubobject<UArrowComponent>(TEXT("EntryArrow"));
	EntryArrow->SetupAttachment(SceneRoot);
	EntryArrow->SetMobility(EComponentMobility::Static);
	EntryArrow->ArrowColor = FColor(80, 250, 123);
	EntryArrow->ArrowSize = 6.f;
	EntryArrow->ArrowLength = 120.f;
	EntryArrow->SetHiddenInGame(true);

	ExitArrow = CreateDefaultSubobject<UArrowComponent>(TEXT("ExitArrow"));
	ExitArrow->SetupAttachment(ExitPoint);
	ExitArrow->SetMobility(EComponentMobility::Static);
	ExitArrow->ArrowColor = FColor(255, 184, 108);
	ExitArrow->ArrowSize = 3.f;
	ExitArrow->ArrowLength = 120.f;
	ExitArrow->SetHiddenInGame(true);

	MouthLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("MouthLight"));
	MouthLight->SetupAttachment(SceneRoot);
	MouthLight->SetMobility(EComponentMobility::Stationary);
	MouthLight->SetIntensityUnits(ELightUnits::Candelas);
	MouthLight->SetIntensity(60.f);
	MouthLight->SetAttenuationRadius(1800.f);
	MouthLight->SetLightColor(AOSDracula::Cyan());
	MouthLight->SetCastShadows(false);

	ApplyLayout();
}

FVector AAOSTeleportStation::LocalEntryAxis() const
{
	switch (EntryDirection)
	{
	case EAOSTransitDirection::Down:    return FVector::DownVector;
	case EAOSTransitDirection::Forward: return FVector::ForwardVector;
	default:                            return FVector::UpVector;
	}
}

void AAOSTeleportStation::ApplyLayout()
{
	const FVector A = LocalEntryAxis();
	const bool bHorizontal = EntryDirection == EAOSTransitDirection::Forward;
	// Frame +X on the axis; the frame's up follows the actor forward for vertical shafts, world up for a level one.
	const FQuat AxisQ = FRotationMatrix::MakeFromXZ(A, bHorizontal ? FVector::UpVector : FVector::ForwardVector).ToQuat();

	PortalFrame->SetRelativeLocationAndRotation(-AxisQ.RotateVector(FrameLensOffset), AxisQ);
	// Shaft: frame rotation, axis on the frame's round bore (the physical opening, FrameBoreCenter - FrameLensOffset from the lens),
	// mouth flush on the exit face, outer wall scaled to the bore radius. The lens (traversal) axis stays inside the tube.
	const FVector BoreFromLens = AxisQ.RotateVector(FVector(0.f, FrameBoreCenter.Y - FrameLensOffset.Y, FrameBoreCenter.Z - FrameLensOffset.Z));
	const float RadialFit = (FrameBoreRadius > 0.f && ShaftOuterRadius > 0.f) ? FrameBoreRadius / ShaftOuterRadius : 1.f;
	ShaftMesh->SetRelativeLocationAndRotation(A * FrameBackFace + BoreFromLens, AxisQ);
	ShaftMesh->SetRelativeScale3D(FVector(1.f, RadialFit, RadialFit));
	EntranceTrigger->SetRelativeLocationAndRotation(-A * (FrameFrontFace + TriggerDepth * 0.5f), AxisQ);
	EntranceTrigger->SetBoxExtent(FVector(TriggerDepth * 0.5f, TriggerHalfWidth, TriggerHalfWidth));
	// Level exit; a horizontal station hands the Shell over facing out of the mouth (along the exit push).
	ExitPoint->SetRelativeLocationAndRotation(-A * (FrameFrontFace + TriggerDepth + ExitClearance),
		bHorizontal ? FRotationMatrix::MakeFromX(-A).ToQuat() : FQuat::Identity);
	EntryArrow->SetRelativeLocationAndRotation(-A * (FrameFrontFace + TriggerDepth), AxisQ);
	ExitArrow->SetRelativeRotation(bHorizontal ? FQuat::Identity : FRotationMatrix::MakeFromX(-A).ToQuat()); // child of ExitPoint
	MouthLight->SetRelativeLocation(-A * (FrameFrontFace + 150.f));
}

void AAOSTeleportStation::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	if (bAutoLayout)
	{
		ApplyLayout();
	}
}

void AAOSTeleportStation::BeginPlay()
{
	Super::BeginPlay();
	EntranceTrigger->OnComponentBeginOverlap.AddUniqueDynamic(this, &AAOSTeleportStation::HandleEntranceOverlap);
	if (LinkedStation.IsNull())
	{
		UE_LOG(LogAOSTransit, Warning, TEXT("%s (%s): LinkedStation is not set"), *StationName, *GetName());
	}
}

FVector AAOSTeleportStation::GetEntryVector() const
{
	return GetActorTransform().TransformVectorNoScale(LocalEntryAxis()).GetSafeNormal();
}

FVector AAOSTeleportStation::GetExitVelocity() const
{
	return -GetEntryVector() * ExitSpeed;
}

AAOSTeleportStation* AAOSTeleportStation::GetLinkedStation() const
{
	AAOSTeleportStation* Station = LinkedStation.Get();
	if (!Station && !LinkedStation.IsNull())
	{
		Station = LinkedStation.LoadSynchronous();
	}
	return Station;
}

void AAOSTeleportStation::ApplyArrivalCooldown(float Seconds)
{
	if (const UWorld* World = GetWorld())
	{
		CooldownUntil = FMath::Max(CooldownUntil, World->GetTimeSeconds() + FMath::Max(0.f, Seconds));
	}
}

bool AAOSTeleportStation::IsOnCooldown() const
{
	return GetCooldownRemaining() > 0.f;
}

float AAOSTeleportStation::GetCooldownRemaining() const
{
	const UWorld* World = GetWorld();
	return World ? FMath::Max(0.f, float(CooldownUntil - World->GetTimeSeconds())) : 0.f;
}

void AAOSTeleportStation::HandleEntranceOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
	int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	AShellPawn* Shell = Cast<AShellPawn>(OtherActor);
	if (!Shell)
	{
		return;
	}
	if (IsOnCooldown())
	{
		++CooldownRejectCount;
		UE_LOG(LogAOSTransit, Verbose, TEXT("%s: entry ignored, arrival cooldown %.2f s"), *StationName, GetCooldownRemaining());
		return;
	}
	BeginTransit(Shell);
}

bool AAOSTeleportStation::BeginTransit(AShellPawn* Shell)
{
	if (Phase != EAOSTransitPhase::Idle || !IsValid(Shell) || IsOnCooldown())
	{
		return false;
	}
	// Only a manned, powered Shell that is not already in a scripted sequence.
	if (!Cast<APlayerController>(Shell->GetController()) || Shell->IsSystemsHalted() || Shell->AreControlsBlocked())
	{
		return false;
	}
	AAOSTeleportStation* Target = GetLinkedStation();
	if (!Target || Target == this || Target->GetPhase() != EAOSTransitPhase::Idle)
	{
		TerminalLog(Shell, TEXT("shaft offline - no linked station"), uint8(EAOSHudLogSeverity::Warning));
		UE_LOG(LogAOSTransit, Warning, TEXT("%s: transit refused, LinkedStation is not set"), *StationName);
		return false;
	}
	UPrimitiveComponent* Body = Cast<UPrimitiveComponent>(Shell->GetRootComponent());
	if (!Body)
	{
		return false;
	}

	Shell->SetBlockControls(true);

	// Kinematic intake: physics off, the station drives the hull.
	IntakeStartVelocity = Body->IsSimulatingPhysics() ? Body->GetPhysicsLinearVelocity() : FVector::ZeroVector;
	IntakeStartVelocity = IntakeStartVelocity.GetClampedToMaxSize(MaxCarriedEntrySpeed);
	Body->SetPhysicsLinearVelocity(FVector::ZeroVector);
	Body->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
	Body->SetSimulatePhysics(false);

	EntryWorld = GetEntryVector();
	IntakeStart = Shell->GetActorLocation();
	IntakeEnd = GetActorLocation() + EntryWorld * IntakeDepth;
	IntakeStartQuat = Shell->GetActorQuat();
	FVector UpHint = FVector::VectorPlaneProject(Shell->GetActorForwardVector(), EntryWorld);
	if (UpHint.SizeSquared() < 0.01f)
	{
		UpHint = FVector::VectorPlaneProject(Shell->GetActorUpVector(), EntryWorld);
	}
	if (UpHint.SizeSquared() < 0.01f)
	{
		UpHint = GetActorForwardVector();
	}
	IntakeTargetQuat = FRotationMatrix::MakeFromXZ(EntryWorld, UpHint).ToQuat();

	TransitShell = Shell;
	TransitTarget = Target;
	Phase = EAOSTransitPhase::Intake;
	PhaseTime = 0.f;
	SetActorTickEnabled(true);

	if (DepartureSound)
	{
		UGameplayStatics::PlaySound2D(this, DepartureSound);
	}
	TerminalLog(Shell, FString::Printf(TEXT("decompression seal locked \u2014 routing to %s"), *Target->GetStationName()),
		uint8(EAOSHudLogSeverity::System));
	UE_LOG(LogAOSTransit, Log, TEXT("%s -> %s: intake started at %s (entry %s, carried v %.0f cm/s)"), *StationName, *Target->GetStationName(),
		*IntakeStart.ToCompactString(), *EntryWorld.ToCompactString(), IntakeStartVelocity.Size());
	return true;
}

void AAOSTeleportStation::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (Phase == EAOSTransitPhase::Idle)
	{
		SetActorTickEnabled(false);
		return;
	}
	if (!TransitShell.IsValid())
	{
		AbortTransit(TEXT("shell lost"));
		return;
	}
	PhaseTime += DeltaSeconds;
	if (Phase == EAOSTransitPhase::Intake)
	{
		TickIntake(DeltaSeconds);
	}
	else
	{
		TickFade(DeltaSeconds);
	}
}

void AAOSTeleportStation::TickIntake(float DeltaSeconds)
{
	AShellPawn* Shell = TransitShell.Get();
	const float T = IntakeDuration;
	const float t = FMath::Clamp(PhaseTime / T, 0.f, 1.f);
	const float t2 = t * t, t3 = t2 * t;
	// Cubic Hermite: carries the entry velocity in, leaves on the shaft axis at IntakeEndSpeed.
	const FVector V1 = EntryWorld * IntakeEndSpeed;
	const FVector P = (2.f * t3 - 3.f * t2 + 1.f) * IntakeStart + (t3 - 2.f * t2 + t) * T * IntakeStartVelocity
		+ (-2.f * t3 + 3.f * t2) * IntakeEnd + (t3 - t2) * T * V1;
	const float Align = FMath::SmoothStep(0.f, 1.f, FMath::Clamp(t / AlignFraction, 0.f, 1.f));
	const FQuat Q = FQuat::Slerp(IntakeStartQuat, IntakeTargetQuat, Align).GetNormalized();
	Shell->SetActorLocationAndRotation(P, Q, false, nullptr, ETeleportType::TeleportPhysics);

	if (t >= 1.f)
	{
		Phase = EAOSTransitPhase::FadeOut;
		PhaseTime = 0.f;
		if (APlayerCameraManager* Cam = AOSTransit::CameraOf(Shell))
		{
			Cam->StartCameraFade(0.0f, 1.0f, FadeDuration, FLinearColor::Black, false, true);
		}
		UE_LOG(LogAOSTransit, Log, TEXT("%s: intake complete at %s, fading out"), *StationName, *Shell->GetActorLocation().ToCompactString());
	}
}

void AAOSTeleportStation::TickFade(float DeltaSeconds)
{
	AShellPawn* Shell = TransitShell.Get();
	// Glide on down the shaft, easing to half speed over the fade.
	const float Tau = FMath::Min(PhaseTime, FadeDuration);
	const float Dist = IntakeEndSpeed * (Tau - Tau * Tau / (4.f * FadeDuration));
	Shell->SetActorLocationAndRotation(IntakeEnd + EntryWorld * Dist, IntakeTargetQuat, false, nullptr, ETeleportType::TeleportPhysics);
	if (PhaseTime >= FadeDuration)
	{
		CompleteWarp();
	}
}

void AAOSTeleportStation::ReleaseShell(AShellPawn* Shell, const FVector& Velocity)
{
	if (UPrimitiveComponent* Body = Shell ? Cast<UPrimitiveComponent>(Shell->GetRootComponent()) : nullptr)
	{
		Body->SetSimulatePhysics(true);
		Body->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
		Body->SetPhysicsLinearVelocity(Velocity);
	}
}

void AAOSTeleportStation::TerminalLog(AShellPawn* Shell, const FString& Message, uint8 Severity)
{
	if (Shell)
	{
		Shell->PushTerminalLog(TEXT("transit"), Message, static_cast<EAOSHudLogSeverity>(Severity));
	}
	UE_LOG(LogAOSTransit, Display, TEXT("[terminal] transit: %s"), *Message);
}

float AAOSTeleportStation::GetLocalPlayerFadeAmount(const UObject* WorldContextObject)
{
	const APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(WorldContextObject, 0);
	return (Cam && Cam->bEnableFading) ? Cam->FadeAmount : 0.f;
}

void AAOSTeleportStation::CompleteWarp()
{
	AShellPawn* Shell = TransitShell.Get();
	AAOSTeleportStation* Target = TransitTarget.Get();
	if (!Shell || !Target)
	{
		AbortTransit(TEXT("destination lost"));
		return;
	}
	// Anti-loop first: any overlap generated by the warp itself is already ignored.
	Target->ApplyArrivalCooldown(Target->ArrivalCooldown);

	const USceneComponent* Exit = Target->GetExitPoint();
	Shell->SetActorLocationAndRotation(Exit->GetComponentLocation(), Exit->GetComponentRotation(), false, nullptr, ETeleportType::TeleportPhysics);
	const FVector ExitVelocity = Target->GetExitVelocity();
	ReleaseShell(Shell, ExitVelocity);

	if (APlayerCameraManager* Cam = AOSTransit::CameraOf(Shell))
	{
		Cam->StartCameraFade(1.0f, 0.0f, FadeDuration, FLinearColor::Black, false, false);
	}
	Shell->SetBlockControls(false);
	if (Target->ArrivalSound)
	{
		UGameplayStatics::PlaySound2D(this, Target->ArrivalSound);
	}
	TerminalLog(Shell, FString::Printf(TEXT("arrived at %s \u2014 6DOF restored"), *Target->GetStationName()),
		uint8(EAOSHudLogSeverity::Info));

	++DepartureCount;
	++Target->ArrivalCount;
	UE_LOG(LogAOSTransit, Log, TEXT("%s -> %s: warped to %s, exit v %s, destination cooldown %.1f s"), *StationName, *Target->GetStationName(),
		*Shell->GetActorLocation().ToCompactString(), *ExitVelocity.ToCompactString(), Target->ArrivalCooldown);

	Phase = EAOSTransitPhase::Idle;
	PhaseTime = 0.f;
	TransitShell.Reset();
	TransitTarget.Reset();
	SetActorTickEnabled(false);
}

void AAOSTeleportStation::AbortTransit(const TCHAR* Reason)
{
	if (AShellPawn* Shell = TransitShell.Get())
	{
		ReleaseShell(Shell, FVector::ZeroVector);
		if (Phase == EAOSTransitPhase::FadeOut)
		{
			if (APlayerCameraManager* Cam = AOSTransit::CameraOf(Shell))
			{
				Cam->StartCameraFade(1.0f, 0.0f, FadeDuration, FLinearColor::Black, false, false);
			}
		}
		Shell->SetBlockControls(false);
		TerminalLog(Shell, FString::Printf(TEXT("aborted - %s"), Reason), uint8(EAOSHudLogSeverity::Warning));
	}
	UE_LOG(LogAOSTransit, Warning, TEXT("%s: transit aborted (%s)"), *StationName, Reason);
	Phase = EAOSTransitPhase::Idle;
	PhaseTime = 0.f;
	TransitShell.Reset();
	TransitTarget.Reset();
	SetActorTickEnabled(false);
}

void AAOSTeleportStation::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (Phase != EAOSTransitPhase::Idle && EndPlayReason == EEndPlayReason::Destroyed)
	{
		AbortTransit(TEXT("station removed"));
	}
	Super::EndPlay(EndPlayReason);
}
