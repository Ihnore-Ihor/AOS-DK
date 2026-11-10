#include "ShellPawn.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Camera/CameraComponent.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBayComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "AOS_DK/Player/AdminCharacter.h"
#include "AOS_DK/Player/PlayerController/AdminPlayerController.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "GameFramework/PhysicsVolume.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "AOS_DK/Submarine/Energy/ShellEnergyComponent.h"
#include "AOS_DK/Environment/Physics/AOSFluidPhysicsComponent.h"
#include "AOS_DK/Submarine/HUD/PlayerSubmarineHUDWidget.h"
#include "AOS_DK/Submarine/Subdrones/Core/SubDroneBase.h"
#include "AOS_DK/Submarine/Subdrones/Attacker/SubDrone_Attacker.h"
#include "AOS_DK/Systems/Dock/ShellDock.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"
#include "Components/PointLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/DamageEvents.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraComponent.h"
#include "TimerManager.h"

AShellPawn::AShellPawn()
{
	PrimaryActorTick.bCanEverTick = true;
	AutoPossessAI = EAutoPossessAI::Disabled;

	BoxRoot = CreateDefaultSubobject<UBoxComponent>(TEXT("BoxRoot"));
	RootComponent = BoxRoot;
	BoxRoot->SetSimulatePhysics(true);
	BoxRoot->SetEnableGravity(true);
	BoxRoot->SetCollisionProfileName(TEXT("PhysicsActor"));
	
	// Base physical damping, we apply hydrodynamic damping manually
	BoxRoot->SetLinearDamping(0.1f);
	BoxRoot->SetAngularDamping(0.5f);

	ShellMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ShellMesh"));
	ShellMesh->SetupAttachment(BoxRoot);
	ShellMesh->SetCollisionProfileName(TEXT("NoCollision"));

	FPCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FPCamera"));
	FPCamera->SetupAttachment(BoxRoot);
	FPCamera->bUsePawnControlRotation = false;

	// Water interaction: the Shell keeps its mass-agnostic vehicle hydrodynamics and steps them itself
	// (same frame order as before: fluid forces first, then ballast / thrust / gyro).
	FluidPhysics = CreateDefaultSubobject<UAOSFluidPhysicsComponent>(TEXT("FluidPhysics"));
	FluidPhysics->ResponseModel = EAOSFluidResponseModel::VehicleAcceleration;
	FluidPhysics->bAutoSimulate = false;
	// Original Shell hydrodynamics (cm/s^2 tuning)
	FluidPhysics->FluidDrag = 1.5f;
	FluidPhysics->FluidQuadraticDrag = 0.001f;
	FluidPhysics->AngularFluidDrag = 2.5f;
	FluidPhysics->RightingStiffness = 4.0f;

	DroneBay = CreateDefaultSubobject<USubDroneBayComponent>(TEXT("DroneBay"));
	Energy = CreateDefaultSubobject<UShellEnergyComponent>(TEXT("Energy"));

	// Cabin light: soft, close to the canopy, turns into the red emergency strobe on Kernel Panic.
	CabinLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("CabinLight"));
	CabinLight->SetupAttachment(BoxRoot);
	CabinLight->SetRelativeLocation(FVector(240.f, 0.f, 26.f));
	CabinLight->SetIntensityUnits(ELightUnits::Candelas);
	CabinLight->SetIntensity(6.f);
	CabinLight->SetAttenuationRadius(260.f);
	CabinLight->SetLightColor(AOSDracula::Cyan());
	CabinLight->SetCastShadows(false);

	// External headlights: volumetric beams in the underwater fog.
	auto MakeHeadlight = [this](const TCHAR* Name, float Side) -> USpotLightComponent*
	{
		USpotLightComponent* Light = CreateDefaultSubobject<USpotLightComponent>(Name);
		Light->SetupAttachment(BoxRoot);
		Light->SetRelativeLocation(FVector(305.f, Side * 58.f, -28.f));
		Light->SetRelativeRotation(FRotator(-5.f, Side * 4.f, 0.f));
		Light->SetIntensityUnits(ELightUnits::Lumens);
		Light->SetIntensity(5200.f);
		Light->SetAttenuationRadius(5200.f);
		// Soft flood profile (was 13 / 27 deg: two hard-edged discs on any wall in front of the nose).
		Light->SetInnerConeAngle(6.f);
		Light->SetOuterConeAngle(36.f);
		Light->SetSourceRadius(6.f);
		Light->SetLightColor(FLinearColor(1.f, 0.95f, 0.88f));
		Light->SetVolumetricScatteringIntensity(1.4f);
		Light->SetCastShadows(false);
		return Light;
	};
	HeadlightLeft = MakeHeadlight(TEXT("HeadlightLeft"), -1.f);
	HeadlightRight = MakeHeadlight(TEXT("HeadlightRight"), 1.f);

	HUDWidgetClass = UPlayerSubmarineHUDWidget::StaticClass();
}

void AShellPawn::BeginPlay()
{
	Super::BeginPlay();
	TargetBallastForce = 0.f;
	CurrentBallastForce = 0.f;
	bIsStabilizing = false;

	CacheLights();
	SetLightsLevel(GetController() ? 1.f : 0.f, false);

	if (Energy)
	{
		Energy->OnSubmarineEnergyDepleted.AddDynamic(this, &AShellPawn::HandleEnergyDepleted);
	}
	ResolveHomeDock();
}

void AShellPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	if (UEnhancedInputComponent* EnhancedInputComp = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		EnhancedInputComp->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AShellPawn::ApplyThrust);
		EnhancedInputComp->BindAction(MoveAction, ETriggerEvent::Completed, this, &AShellPawn::ResetThrust);
		EnhancedInputComp->BindAction(RotateAction, ETriggerEvent::Triggered, this, &AShellPawn::ApplyRotation);
		EnhancedInputComp->BindAction(InteractAction, ETriggerEvent::Started, this, &AShellPawn::HandleInteract);
		EnhancedInputComp->BindAction(BallastAction, ETriggerEvent::Triggered, this, &AShellPawn::ApplyBallast);
		EnhancedInputComp->BindAction(BallastAction, ETriggerEvent::Completed, this, &AShellPawn::ResetBallast);

		if (StabilizeAction)
		{
			EnhancedInputComp->BindAction(StabilizeAction, ETriggerEvent::Started, this, &AShellPawn::TriggerStabilization);
		}

		if (BoostAction)
		{
			EnhancedInputComp->BindAction(BoostAction, ETriggerEvent::Started, this, &AShellPawn::StartBoost);
			EnhancedInputComp->BindAction(BoostAction, ETriggerEvent::Completed, this, &AShellPawn::StopBoost);
		}

		if (DroneBay)
		{
			DroneBay->BindInput(EnhancedInputComp);
		}
	}
}

void AShellPawn::NotifyControllerChanged()
{
	Super::NotifyControllerChanged();
	if (APlayerController* OldPC = Cast<APlayerController>(CachedController))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(OldPC->GetLocalPlayer()))
		{
			if (SubMappingContext) Subsystem->RemoveMappingContext(SubMappingContext);
		}
	}

	CachedController = GetController();

	if (APlayerController* NewPC = Cast<APlayerController>(CachedController))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(NewPC->GetLocalPlayer()))
		{
			if (SubMappingContext) Subsystem->AddMappingContext(SubMappingContext, 0);
		}
		if (!bSystemsHalted)
		{
			ResetCameraPostProcess();
			SetLightsLevel(1.f, false);
		}
		if (!bInLARSCradle)
		{
			ShowCockpitHUD(NewPC);
		}
		else
		{
			EnsureCockpitHUD(NewPC);   // LARS: pre-built, shown the instant the camera lands in the cockpit
		}
	}
	else
	{
		TargetBallastForce = 0.f;
		CurrentBallastForce = 0.f;
		bIsStabilizing = false;
		bBoostHeld = false;
		MoveAxisRaw = FVector2D::ZeroVector;
		HideCockpitHUD();
		if (!bSystemsHalted)
		{
			SetLightsLevel(0.f, false);
		}
		if (Energy)
		{
			Energy->ClearConsumers();
		}
	}
}

void AShellPawn::Interact_Implementation(AActor* InstigatorActor)
{
	if (AAdminCharacter* Admin = Cast<AAdminCharacter>(InstigatorActor))
	{
		// Hanging in the LARS cradle: boarding goes through the dock (launch sequence), not a direct possess.
		if (bInLARSCradle)
		{
			if (AShellDock* Dock = ResolveHomeDock())
			{
				IInteractable::Execute_Interact(Dock, Admin);
			}
			return;
		}
		if (AController* PC = Admin->GetController())
		{
			PC->Possess(this);
			Admin->AttachToComponent(BoxRoot, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
			Admin->SetActorHiddenInGame(true);
			Admin->SetActorEnableCollision(false);
		}
	}
}

void AShellPawn::HandleInteract()
{
	if (bSystemsHalted || bControlsBlocked)
	{
		return;
	}
	// Fresh query: [F] acts on what is under the reticle now, not on the last 30 Hz sample.
	InteractFocus = QueryInteractFocus();
	InteractQueryTimer = 1.f / InteractQueryRate;
	if (AActor* Focus = InteractFocus.Get())
	{
		IInteractable::Execute_Interact(Focus, this);
		RefreshFocusPrompt();
		return;
	}
	if (AAdminPlayerController* PC = Cast<AAdminPlayerController>(GetController()))
	{
		PC->TryInteract();
	}
}

// ==================================================================================================
// [F] interaction focus
// ==================================================================================================
AActor* AShellPawn::QueryInteractFocus() const
{
	UWorld* World = GetWorld();
	AAdminPlayerController* PC = Cast<AAdminPlayerController>(GetController());
	if (!World || !PC || bSystemsHalted || bControlsBlocked || PC->IsInteractLocked())
	{
		return nullptr;
	}

	FVector ViewLoc;
	FRotator ViewRot;
	PC->GetPlayerViewPoint(ViewLoc, ViewRot);
	const FVector Dir = ViewRot.Vector();

	FCollisionQueryParams Params(SCENE_QUERY_STAT(ShellInteractFocus), false, this);
	TArray<AActor*> Attached;
	GetAttachedActors(Attached); // the hidden pilot
	Params.AddIgnoredActors(Attached);
	if (DroneBay)
	{
		for (int32 Slot = 0; Slot < DroneBay->GetNumSlots(); ++Slot)
		{
			if (const AActor* Drone = DroneBay->GetDrone(Slot))
			{
				Params.AddIgnoredActor(Drone);
			}
		}
	}

	// 1) What the reticle sees: walls occlude, terminals / docks that block Visibility are direct hits.
	AActor* Best = nullptr;
	float BestDistance = InteractRange;
	FHitResult Hit;
	if (World->LineTraceSingleByChannel(Hit, ViewLoc, ViewLoc + Dir * InteractRange, ECC_Visibility, Params))
	{
		BestDistance = Hit.Distance;
		AActor* HitActor = Hit.GetActor();
		if (HitActor && HitActor != this && HitActor->Implements<UInteractable>())
		{
			Best = HitActor;
		}
	}

	// 2) Query-only focus volumes (pickup spheres block no channel, so they never steal the drone aim):
	//    object sweep up to the occluder. Multi object queries report every hit as a touch, sorted by distance.
	TArray<FHitResult> Hits;
	World->SweepMultiByObjectType(Hits, ViewLoc, ViewLoc + Dir * BestDistance, FQuat::Identity,
		FCollisionObjectQueryParams(ECC_TO_BITFIELD(ECC_WorldDynamic)), FCollisionShape::MakeSphere(InteractAimRadius), Params);
	for (const FHitResult& Touch : Hits)
	{
		AActor* HitActor = Touch.GetActor();
		if (HitActor && HitActor != this && HitActor->Implements<UInteractable>() && Touch.Distance <= BestDistance)
		{
			Best = HitActor;
			BestDistance = Touch.Distance;
			break;
		}
	}

	// 3) Nothing aimed at: whatever the controller found by overlap (dock berth, disembark point).
	if (!Best)
	{
		AActor* Overlapped = PC->GetCurrentInteractable();
		Best = Overlapped != this ? Overlapped : nullptr;
	}
	return Best;
}

void AShellPawn::RefreshFocusPrompt()
{
	FocusAction = FText::GetEmpty();
	bFocusAvailable = false;
	AActor* Focus = InteractFocus.Get();
	if (!Focus || !Focus->Implements<UInteractable>())
	{
		InteractFocus.Reset();
		return;
	}
	bFocusAvailable = true;
	IInteractable::Execute_GetInteractPrompt(Focus, this, FocusAction, bFocusAvailable);
	if (FocusAction.IsEmpty())
	{
		FocusAction = NSLOCTEXT("AOSShell", "InteractGeneric", "INTERACT");
	}
}

void AShellPawn::UpdateInteractFocus(float DeltaTime)
{
	if (!IsLocallyControlled() || !Cast<APlayerController>(GetController()))
	{
		InteractFocus.Reset();
		return;
	}
	InteractQueryTimer -= DeltaTime;
	if (InteractQueryTimer > 0.f)
	{
		return;
	}
	InteractQueryTimer = 1.f / InteractQueryRate;
	InteractFocus = QueryInteractFocus();
	RefreshFocusPrompt();
}

bool AShellPawn::GetFocusPrompt(FText& OutAction, bool& bOutAvailable) const
{
	if (!InteractFocus.IsValid())
	{
		return false;
	}
	OutAction = FocusAction;
	bOutAvailable = bFocusAvailable;
	return true;
}

void AShellPawn::ApplyThrust(const FInputActionValue& Value)
{
	if (bSystemsHalted || bControlsBlocked)
	{
		return;
	}
	FVector RawInput = Value.Get<FVector>();
	MoveAxisRaw = FVector2D(RawInput.X, RawInput.Y);
	// Mapping: X is Forward/Back (W/S), Y is Strafing (A/D). Boost multiplies the main engines.
	const float Boost = bBoostHeld ? BoostThrustMultiplier : 1.f;
	CurrentMoveInput = FVector(RawInput.X * ForwardThrust * Boost, RawInput.Y * LateralThrust, 0.f);
	TargetThrustScalar = 1.0f;
}

void AShellPawn::ResetThrust(const FInputActionValue& Value)
{
	MoveAxisRaw = FVector2D::ZeroVector;
	CurrentMoveInput = FVector::ZeroVector;
	TargetThrustScalar = 0.f;
}

void AShellPawn::ApplyRotation(const FInputActionValue& Value)
{
	if (bSystemsHalted || bControlsBlocked)
	{
		return;
	}
	FVector RawInput = Value.Get<FVector>();
	FVector LocalTorque = FVector::ZeroVector;

	LocalTorque.X = RawInput.X * RollSensitivity;  // Q/E Keys -> Roll
	LocalTorque.Y = RawInput.Y * PitchSensitivity; // Mouse Y -> Pitch
	LocalTorque.Z = RawInput.Z * YawSensitivity;   // Mouse X -> Yaw

	FVector WorldTorque = BoxRoot->GetComponentTransform().TransformVector(LocalTorque);
	BoxRoot->AddTorqueInRadians(WorldTorque, NAME_None, true);
}

void AShellPawn::ApplyBallast(const FInputActionValue& Value)
{
	if (bSystemsHalted || bControlsBlocked)
	{
		return;
	}
	float BallastInput = Value.Get<float>();
	
	// Deadzone to prevent analog stick micro-drifts
	if (FMath::Abs(BallastInput) > 0.05f)
	{
		TargetBallastForce = BallastInput * BallastForce;
	}
	else
	{
		TargetBallastForce = 0.f;
	}
}

void AShellPawn::ResetBallast(const FInputActionValue& Value)
{
	TargetBallastForce = 0.f;
}

void AShellPawn::TriggerStabilization()
{
	if (bSystemsHalted)
	{
		PushTerminalLog(TEXT("gyro"), TEXT("offline - core halted"), EAOSHudLogSeverity::Warning);
		return;
	}
	if (bIsStabilizing || bControlsBlocked)
	{
		return;
	}
	bIsStabilizing = true;
	const float TiltDeg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(BoxRoot->GetUpVector(), FVector::UpVector), -1.f, 1.f)));
	PushTerminalLog(TEXT("gyro"), FString::Printf(TEXT("stabilizer engaged - aligning, tilt %.1f deg"), TiltDeg), EAOSHudLogSeverity::System);
}

void AShellPawn::UpdateHydrodynamics(float DeltaTime)
{
	if (!BoxRoot || !BoxRoot->IsSimulatingPhysics())
	{
		return; // kinematic (scripted) motion, e.g. a transit-shaft intake: no fluid forces on a non-simulating body
	}
	const bool bHasDriver = (GetController() != nullptr);

	// Shared water engine: wave query, gravity/entry, Morison drag, angular damping and - while empty -
	// the Archimedes flotation spring + wave-normal alignment.
	FluidPhysics->SetPassiveFlotation(!bHasDriver);
	const FAOSFluidSample Fluid = FluidPhysics->StepFluidPhysics(DeltaTime);

	if (!Fluid.bInWater)
	{
		// AIR STATE: full engine gravity (set by the component), propulsion disabled
		CurrentThrustScalar = 0.f;
		TargetThrustScalar = 0.f;
		CurrentBallastForce = 0.f;
		if (bIsStabilizing)
		{
			PushTerminalLog(TEXT("gyro"), TEXT("no water contact - stabilizer off"), EAOSHudLogSeverity::Warning);
		}
		bIsStabilizing = false;
		return;
	}

	if (!bHasDriver)
	{
		return; // EMPTY BOAT MODE: handled entirely by the passive flotation of the component
	}

	if (bControlsBlocked && !bSystemsHalted)
	{
		// LOCKED (scripted sequence): engines idle, the hull keeps neutral buoyancy.
		CurrentBallastForce = 0.f;
		CurrentThrustScalar = 0.f;
		return;
	}

	if (bSystemsHalted)
	{
		// HALTED: engines and gyro offline - the dead hull settles slowly.
		CurrentBallastForce = FMath::FInterpTo(CurrentBallastForce, 0.f, DeltaTime, BallastChangeSpeed);
		CurrentThrustScalar = FMath::FInterpTo(CurrentThrustScalar, 0.f, DeltaTime, ThrustRampSpeed);
		BoxRoot->AddForce(FVector(0.f, 0.f, -HaltedSinkAcceleration), NAME_None, true);
		return;
	}

	// MANNED 6DOF MODE: pure neutral buoyancy underwater

	// Vertical engines
	CurrentBallastForce = FMath::FInterpTo(CurrentBallastForce, TargetBallastForce, DeltaTime, BallastChangeSpeed);
	BoxRoot->AddForce(FVector(0.f, 0.f, CurrentBallastForce), NAME_None, true);

	// Directional engines
	CurrentThrustScalar = FMath::FInterpTo(CurrentThrustScalar, TargetThrustScalar, DeltaTime, ThrustRampSpeed);
	if (CurrentThrustScalar > 0.05f)
	{
		FVector LocalAccel = BoxRoot->GetComponentTransform().TransformVector(CurrentMoveInput * CurrentThrustScalar);
		BoxRoot->AddForce(LocalAccel, NAME_None, true);
	}

	// Manual gyrostabilizer (only while engaged): 3x the hull's metacentric stiffness
	if (bIsStabilizing)
	{
		FVector SubUp = BoxRoot->GetUpVector();
		FVector RestoringTorqueAxis = FVector::CrossProduct(SubUp, FVector::UpVector);
		BoxRoot->AddTorqueInRadians(RestoringTorqueAxis * (FluidPhysics->GetRightingStiffness() * 3.0f), NAME_None, true);

		// Auto-disable when horizon alignment is reached
		if (FVector::DotProduct(SubUp, FVector::UpVector) > 0.995f && Fluid.AngularVelocity.Size() < 0.1f)
		{
			bIsStabilizing = false;
			PushTerminalLog(TEXT("gyro"), TEXT("horizon locked - stabilizer idle"), EAOSHudLogSeverity::Info);
		}
	}
}

void AShellPawn::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	UpdateHydrodynamics(DeltaTime);
	UpdateEnergyLoads();
	UpdateLights(DeltaTime);
	UpdateHeadlightDimming(DeltaTime);
	UpdateCameraGlitch(DeltaTime);
	UpdateInteractFocus(DeltaTime);
	if (bSystemsHalted)
	{
		HaltElapsed += DeltaTime;
	}
}

// ==================================================================================================
// Boost
// ==================================================================================================
void AShellPawn::StartBoost(const FInputActionValue& Value)
{
	bBoostHeld = !bSystemsHalted && !bControlsBlocked;
}

// ==================================================================================================
// Scripted control lock (transit shafts)
// ==================================================================================================
void AShellPawn::SetBlockControls(bool bBlock)
{
	if (bControlsBlocked == bBlock)
	{
		return;
	}
	bControlsBlocked = bBlock;
	if (bBlock)
	{
		MoveAxisRaw = FVector2D::ZeroVector;
		CurrentMoveInput = FVector::ZeroVector;
		TargetThrustScalar = 0.f;
		CurrentThrustScalar = 0.f;
		TargetBallastForce = 0.f;
		CurrentBallastForce = 0.f;
		bBoostHeld = false;
		bIsStabilizing = false;
		if (DroneBay)
		{
			DroneBay->SetPrimaryActionHeld(false);
			DroneBay->RecallAllDrones();
		}
	}
	if (AAdminPlayerController* AdminPC = Cast<AAdminPlayerController>(GetController()))
	{
		AdminPC->SetInteractLocked(bBlock || bSystemsHalted);
	}
}

void AShellPawn::StopBoost(const FInputActionValue& Value)
{
	bBoostHeld = false;
}

// ==================================================================================================
// Energy budget
// ==================================================================================================
void AShellPawn::UpdateEnergyLoads()
{
	if (!Energy)
	{
		return;
	}
	const bool bManned = Cast<APlayerController>(GetController()) != nullptr;
	if (!bManned || bSystemsHalted)
	{
		Energy->ClearConsumers();
		return;
	}

	// Cruising is free. The boost multiplies only the main engines, so it pays only for the actual
	// (ramped) forward thrust: holding Ctrl while drifting costs nothing.
	const float BoostLoad = bBoostHeld ? CurrentThrustScalar * FMath::Clamp(FMath::Abs(MoveAxisRaw.X), 0.f, 1.f) : 0.f;
	Energy->SetConsumerDrain(TEXT("Boost"), BoostLoad * BoostDrainPerSec);

	float DroneDrain = 0.f;
	if (DroneBay)
	{
		for (int32 i = 0; i < DroneBay->GetNumSlots(); ++i)
		{
			const ASubDroneBase* Drone = DroneBay->GetDrone(i);
			if (!IsValid(Drone))
			{
				continue;
			}
			DroneDrain += Drone->GetDeployBlend() * DroneDeployedDrainPerSec;
			if (const ASubDrone_Attacker* Attacker = Cast<ASubDrone_Attacker>(Drone))
			{
				const EAttackerCombatState Combat = Attacker->GetCombatState();
				if (Combat == EAttackerCombatState::SpinUp || Combat == EAttackerCombatState::Attack)
				{
					DroneDrain += Attacker->GetSpinAlpha() * DroneCombatDrainPerSec;
				}
			}
		}
	}
	Energy->SetConsumerDrain(TEXT("Drones"), DroneDrain);
}

// ==================================================================================================
// Damage
// ==================================================================================================
float AShellPawn::TakeDamage(float DamageAmount, FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser)
{
	const float Damage = Super::TakeDamage(DamageAmount, DamageEvent, EventInstigator, DamageCauser);
	if (Damage <= 0.f || !Energy || Energy->IsDepleted() || bSystemsHalted)
	{
		return 0.f;
	}

	FVector HitLocation = GetActorLocation();
	FVector HitNormal = GetActorForwardVector();
	if (DamageEvent.IsOfType(FPointDamageEvent::ClassID))
	{
		const FPointDamageEvent& PointEvent = static_cast<const FPointDamageEvent&>(DamageEvent);
		if (!PointEvent.HitInfo.ImpactPoint.IsNearlyZero())
		{
			HitLocation = PointEvent.HitInfo.ImpactPoint;
		}
		if (!PointEvent.ShotDirection.IsNearlyZero())
		{
			HitNormal = -PointEvent.ShotDirection.GetSafeNormal();
		}
	}
	else if (DamageCauser)
	{
		const FVector ToCauser = (DamageCauser->GetActorLocation() - GetActorLocation()).GetSafeNormal();
		HitNormal = ToCauser;
		FVector Closest;
		if (BoxRoot && BoxRoot->GetClosestPointOnCollision(DamageCauser->GetActorLocation(), Closest) >= 0.f)
		{
			HitLocation = Closest;
		}
	}

	const float Applied = Energy->ApplyEnergyDamage(Damage, HitLocation, DamageCauser);
	if (Applied > 0.f)
	{
		CameraGlitch = 1.f;
		SpawnHullHitFX(HitLocation, HitNormal);
	}
	return Applied;
}

void AShellPawn::SpawnHullHitFX(const FVector& Location, const FVector& Normal)
{
	if (HullHitFX && BoxRoot)
	{
		// Attached: the discharge crawls with the hull instead of being left behind.
		UNiagaraFunctionLibrary::SpawnSystemAttached(HullHitFX, BoxRoot, NAME_None, Location, Normal.Rotation(),
			EAttachLocation::KeepWorldPosition, true, true, ENCPoolMethod::AutoRelease);
	}
	if (HullHitSecondaryFX)
	{
		UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, HullHitSecondaryFX, Location, Normal.Rotation(), FVector(1.f), true, true, ENCPoolMethod::AutoRelease);
	}
}

void AShellPawn::ResetCameraPostProcess()
{
	CameraGlitch = 0.f;
	if (FPCamera)
	{
		FPostProcessSettings& PP = FPCamera->PostProcessSettings;
		PP.bOverride_SceneFringeIntensity = false;
		PP.bOverride_FilmGrainIntensity = false;
	}
}

void AShellPawn::UpdateCameraGlitch(float DeltaTime)
{
	if (!FPCamera)
	{
		return;
	}
	CameraGlitch = FMath::Max(0.f, CameraGlitch - DeltaTime / FMath::Max(DamageGlitchTime, 0.05f));
	const float Panic = bSystemsHalted ? FMath::Clamp(HaltElapsed / 0.3f, 0.f, 1.f) : 0.f;
	const float Fringe = FMath::Pow(CameraGlitch, 0.7f) * DamageFringeIntensity + Panic * PanicFringeIntensity;

	FPostProcessSettings& PP = FPCamera->PostProcessSettings;
	if (Fringe > 0.001f)
	{
		PP.bOverride_SceneFringeIntensity = true;
		PP.SceneFringeIntensity = Fringe;
		PP.bOverride_FilmGrainIntensity = true;
		PP.FilmGrainIntensity = FMath::Clamp(0.15f * Fringe, 0.f, 1.f);
	}
	else if (PP.bOverride_SceneFringeIntensity)
	{
		// Hand the lens back to the level post-process volume.
		PP.bOverride_SceneFringeIntensity = false;
		PP.bOverride_FilmGrainIntensity = false;
	}
}

// ==================================================================================================
// Lights
// ==================================================================================================
void AShellPawn::CacheLights()
{
	CachedLights.Reset();
	TArray<ULightComponent*> Lights;
	GetComponents<ULightComponent>(Lights);
	for (ULightComponent* Light : Lights)
	{
		FCachedLight& Cached = CachedLights.AddDefaulted_GetRef();
		Cached.Light = Light;
		Cached.BaseIntensity = Light->Intensity;
		Cached.BaseColor = Light->GetLightColor();
	}
}

void AShellPawn::SetLightsLevel(float Level, bool bEmergencyRed)
{
	LightsLevel = Level;
	for (const FCachedLight& Cached : CachedLights)
	{
		ULightComponent* Light = Cached.Light.Get();
		if (!Light)
		{
			continue;
		}
		const bool bCabin = Light == CabinLight.Get();
		if (bEmergencyRed && bCabin)
		{
			Light->SetLightColor(AOSDracula::Red());
			Light->SetIntensity(Cached.BaseIntensity * 2.5f * Level);
		}
		else
		{
			Light->SetLightColor(Cached.BaseColor);
			Light->SetIntensity(Cached.BaseIntensity * Level * (IsHeadlight(Light) ? HeadlightDim : 1.f));
		}
		Light->SetVisibility(Level > 0.001f);
	}
}

bool AShellPawn::IsHeadlight(const ULightComponent* Light) const
{
	return Light && (Light == HeadlightLeft.Get() || Light == HeadlightRight.Get());
}

void AShellPawn::UpdateHeadlightDimming(float DeltaTime)
{
	UWorld* World = GetWorld();
	if (!World || BeamFullPowerDistance <= 0.f || bSystemsHalted || LightsLevel <= 0.001f)
	{
		return;
	}
	BeamProbeTimer -= DeltaTime;
	if (BeamProbeTimer <= 0.f)
	{
		BeamProbeTimer = 1.f / InteractQueryRate;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(ShellBeamProbe), false, this);
		TArray<AActor*> Attached;
		GetAttachedActors(Attached);
		Params.AddIgnoredActors(Attached);
		if (DroneBay)
		{
			for (int32 Slot = 0; Slot < DroneBay->GetNumSlots(); ++Slot)
			{
				if (const AActor* Drone = DroneBay->GetDrone(Slot))
				{
					Params.AddIgnoredActor(Drone);
				}
			}
		}
		// Nearest surface on either beam axis (Visibility: walls, props, Daemons; water and trigger volumes do not block it).
		float Nearest = BeamFullPowerDistance;
		for (const USpotLightComponent* Lamp : { HeadlightLeft.Get(), HeadlightRight.Get() })
		{
			if (!Lamp)
			{
				continue;
			}
			const FVector Start = Lamp->GetComponentLocation();
			FHitResult Hit;
			if (World->SweepSingleByChannel(Hit, Start, Start + Lamp->GetForwardVector() * BeamFullPowerDistance, FQuat::Identity,
				ECC_Visibility, FCollisionShape::MakeSphere(BeamProbeRadius), Params))
			{
				Nearest = FMath::Min(Nearest, Hit.Distance);
			}
		}
		const float R = Nearest / BeamFullPowerDistance;
		HeadlightDimTarget = FMath::Clamp(R * R, MinBeamDimming, 1.f);
	}

	// Smooth in log space (even perceived speed), then drive the two lamps.
	const float NewDim = FMath::Exp(FMath::FInterpTo(FMath::Loge(HeadlightDim), FMath::Loge(HeadlightDimTarget), DeltaTime, BeamDimmingSpeed));
	if (FMath::Abs(NewDim - HeadlightDim) < 1e-4f * HeadlightDim)
	{
		return;
	}
	HeadlightDim = NewDim;
	for (const FCachedLight& Cached : CachedLights)
	{
		ULightComponent* Light = Cached.Light.Get();
		if (IsHeadlight(Light))
		{
			Light->SetIntensity(Cached.BaseIntensity * LightsLevel * HeadlightDim);
		}
	}
}

void AShellPawn::UpdateLights(float DeltaTime)
{
	if (!bSystemsHalted)
	{
		return;
	}
	// Deterministic emergency pattern: the main lights stutter and die, then a red cabin strobe.
	const float Decay = FMath::Clamp(1.f - HaltElapsed / EmergencyLightDecayTime, 0.f, 1.f);
	const uint32 Step = uint32(HaltElapsed * 16.f);
	uint32 Hash = Step * 2654435761u;
	Hash ^= Hash >> 15;
	const bool bOn = (Hash % 100u) < uint32(20.f + 70.f * Decay);
	const float Main = bOn ? Decay * (0.55f + 0.45f * float((Hash >> 8) % 100u) / 100.f) : 0.f;

	for (const FCachedLight& Cached : CachedLights)
	{
		ULightComponent* Light = Cached.Light.Get();
		if (!Light)
		{
			continue;
		}
		if (Light == CabinLight.Get())
		{
			const float Strobe = Decay > 0.f ? Main : FMath::Max(0.f, FMath::Sin(HaltElapsed * 2.f * PI * 1.1f));
			Light->SetLightColor(Decay > 0.f ? Cached.BaseColor : AOSDracula::Red());
			Light->SetIntensity(Cached.BaseIntensity * (Decay > 0.f ? Strobe : 2.5f * Strobe));
			Light->SetVisibility(true);
		}
		else
		{
			Light->SetIntensity(Cached.BaseIntensity * Main);
			Light->SetVisibility(Main > 0.001f);
		}
	}
}

// ==================================================================================================
// HUD
// ==================================================================================================
UPlayerSubmarineHUDWidget* AShellPawn::EnsureCockpitHUD(APlayerController* PC)
{
	if (!CockpitHUD && PC && PC->IsLocalController())
	{
		UClass* WidgetClass = HUDWidgetClass ? HUDWidgetClass.Get() : UPlayerSubmarineHUDWidget::StaticClass();
		CockpitHUD = CreateWidget<UPlayerSubmarineHUDWidget>(PC, WidgetClass);
		if (CockpitHUD)
		{
			CockpitHUD->AddToViewport(HUDZOrder);
			CockpitHUD->SetVisibility(ESlateVisibility::Collapsed);
		}
	}
	return CockpitHUD;
}

void AShellPawn::SetCockpitHUDVisible(bool bVisible)
{
	if (bVisible)
	{
		ShowCockpitHUD(Cast<APlayerController>(GetController()));
	}
	else if (CockpitHUD)
	{
		CockpitHUD->SetVisibility(ESlateVisibility::Collapsed);
	}
}

void AShellPawn::ShowCockpitHUD(APlayerController* PC)
{
	if (!PC || !PC->IsLocalController() || !EnsureCockpitHUD(PC))
	{
		return;
	}
	CockpitHUD->SetVisibility(ESlateVisibility::HitTestInvisible);
	CockpitHUD->BindToShell(this);
}

void AShellPawn::HideCockpitHUD()
{
	if (CockpitHUD)
	{
		CockpitHUD->UnbindFromShell();
		CockpitHUD->SetVisibility(ESlateVisibility::Collapsed);
	}
}

void AShellPawn::PushTerminalLog(const FString& Source, const FString& Message, EAOSHudLogSeverity Severity)
{
	if (CockpitHUD && Cast<APlayerController>(GetController()))
	{
		CockpitHUD->PushLog(Source, Message, Severity);
	}
}

// ==================================================================================================
// Telemetry
// ==================================================================================================
float AShellPawn::GetOceanSurfaceZ() const
{
	return FluidPhysics ? FluidPhysics->GetOceanSurfaceZ() : 0.f;
}

float AShellPawn::GetDepthMeters() const
{
	return FMath::Max(0.f, float(GetOceanSurfaceZ() - GetActorLocation().Z) / 100.f);
}

float AShellPawn::GetHeadingDegrees() const
{
	const FVector Forward = GetActorForwardVector();
	float Heading = FMath::RadiansToDegrees(float(FMath::Atan2(Forward.Y, Forward.X)));
	return Heading < 0.f ? Heading + 360.f : Heading;
}

float AShellPawn::GetPitchDegrees() const
{
	return float(GetActorRotation().Pitch);
}

float AShellPawn::GetCameraFieldOfView() const
{
	return FPCamera ? FPCamera->FieldOfView : 90.f;
}

float AShellPawn::GetRecoveryProgress() const
{
	if (!bSystemsHalted)
	{
		return 0.f;
	}
	return FMath::Clamp(HaltElapsed / FMath::Max(PanicHoldTime + RecoveryFadeOutTime, 0.1f), 0.f, 1.f);
}

// ==================================================================================================
// Kernel Panic -> surface recovery
// ==================================================================================================
AShellDock* AShellPawn::ResolveHomeDock()
{
	if (!HomeDock.IsValid())
	{
		TArray<AActor*> Docks;
		UGameplayStatics::GetAllActorsOfClass(this, AShellDock::StaticClass(), Docks);
		for (AActor* Actor : Docks)
		{
			AShellDock* Dock = Cast<AShellDock>(Actor);
			if (Dock && (Dock->GetLinkedSubmarine() == this || !HomeDock.IsValid()))
			{
				HomeDock = Dock;
			}
		}
	}
	return HomeDock.Get();
}

void AShellPawn::HandleEnergyDepleted()
{
	if (bSystemsHalted)
	{
		return;
	}
	bSystemsHalted = true;
	bRecoveryFading = false;
	HaltElapsed = 0.f;
	bBoostHeld = false;
	bIsStabilizing = false;
	MoveAxisRaw = FVector2D::ZeroVector;
	CurrentMoveInput = FVector::ZeroVector;
	TargetThrustScalar = 0.f;
	TargetBallastForce = 0.f;
	CameraGlitch = 1.f;

	if (DroneBay)
	{
		DroneBay->SetPrimaryActionHeld(false);
		DroneBay->RecallAllDrones();
	}

	APlayerController* PC = Cast<APlayerController>(GetController());
	RecoveryController = PC;
	if (AAdminPlayerController* AdminPC = Cast<AAdminPlayerController>(PC))
	{
		AdminPC->SetInteractLocked(true);
	}
	GetWorldTimerManager().SetTimer(RecoveryTimer, this, &AShellPawn::BeginRecoveryFade, FMath::Max(PanicHoldTime, 0.01f), false);
}

void AShellPawn::BeginRecoveryFade()
{
	bRecoveryFading = true;
	if (APlayerController* PC = RecoveryController.Get())
	{
		if (PC->PlayerCameraManager)
		{
			PC->PlayerCameraManager->StartCameraFade(0.f, 1.f, RecoveryFadeOutTime, FLinearColor::Black, true, true);
		}
	}
	GetWorldTimerManager().SetTimer(RecoveryTimer, this, &AShellPawn::ExecuteRecovery, RecoveryFadeOutTime + 0.05f, false);
}

void AShellPawn::ExecuteRecovery()
{
	APlayerController* PC = RecoveryController.Get();
	if (AShellDock* Dock = ResolveHomeDock())
	{
		// Pilot -> surface dock on foot, Shell -> its berth (calls FinishRecovery).
		Dock->RecoverShell(this);
	}
	else
	{
		FinishRecovery(GetActorTransform());
	}
	if (PC && PC->PlayerCameraManager)
	{
		PC->PlayerCameraManager->StartCameraFade(1.f, 0.f, RecoveryFadeInTime, FLinearColor::Black, true, false);
	}
	RecoveryController.Reset();
}

void AShellPawn::FinishRecovery(const FTransform& ParkingTransform)
{
	GetWorldTimerManager().ClearTimer(RecoveryTimer);
	if (BoxRoot)
	{
		BoxRoot->SetPhysicsLinearVelocity(FVector::ZeroVector);
		BoxRoot->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
	}
	SetActorTransform(ParkingTransform, false, nullptr, ETeleportType::TeleportPhysics);

	bSystemsHalted = false;
	bRecoveryFading = false;
	HaltElapsed = 0.f;
	ResetCameraPostProcess();
	CurrentThrustScalar = 0.f;
	CurrentBallastForce = 0.f;
	if (Energy)
	{
		Energy->RestoreEnergy(RecoveryEnergyFraction);
	}
	SetLightsLevel(Cast<APlayerController>(GetController()) ? 1.f : 0.f, false);
}

// ==================================================================================================
// LARS cradle
// ==================================================================================================
void AShellPawn::EnterLARSCradle()
{
	bInLARSCradle = true;
	if (BoxRoot)
	{
		if (BoxRoot->IsSimulatingPhysics())
		{
			BoxRoot->SetPhysicsLinearVelocity(FVector::ZeroVector);
			BoxRoot->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
		}
		BoxRoot->SetSimulatePhysics(false);
	}
	CurrentThrustScalar = 0.f;
	CurrentBallastForce = 0.f;
	SetBlockControls(true);
}

void AShellPawn::LeaveLARSCradle()
{
	bInLARSCradle = false;
	if (BoxRoot && !BoxRoot->IsSimulatingPhysics())
	{
		BoxRoot->SetSimulatePhysics(true);
		BoxRoot->SetPhysicsLinearVelocity(FVector::ZeroVector);
		BoxRoot->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
	}
}

void AShellPawn::GrantPilotControl()
{
	if (bInLARSCradle)
	{
		LeaveLARSCradle();
	}
	SetBlockControls(false);
	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		ShowCockpitHUD(PC);
		PushTerminalLog(TEXT("lars"), TEXT("cradle clear - 6DOF control online"), EAOSHudLogSeverity::Info);
	}
}
