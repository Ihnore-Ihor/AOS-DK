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

FGerstnerHarmonic::FGerstnerHarmonic(float InA, float InWavelength, float AngleDeg, float InPhase)
{
	Amplitude = InA;
	K = 2.0f * PI / FMath::Max(1.0f, InWavelength);
	// Deep water dispersion relation: omega = sqrt(g * k), assuming g = 981 cm/s^2
	Omega = FMath::Sqrt(981.0f * K);
	float Rad = FMath::DegreesToRadians(AngleDeg);
	Direction = FVector2D(FMath::Cos(Rad), FMath::Sin(Rad));
	PhaseOffset = InPhase;
}

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
		Light->SetInnerConeAngle(13.f);
		Light->SetOuterConeAngle(27.f);
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

	InitializeWaves();

	CacheLights();
	SetLightsLevel(GetController() ? 1.f : 0.f, false);

	if (Energy)
	{
		Energy->OnSubmarineEnergyDepleted.AddDynamic(this, &AShellPawn::HandleEnergyDepleted);
	}
	ResolveHomeDock();
}

void AShellPawn::InitializeWaves()
{
	// Construct analytical spectrum based on user's Gerstner Water parameters
	// (Amplitudes: 10-200, Wavelengths: 800-14000, Dominant Angle: 35)
	WaveHarmonics.Empty();
	WaveHarmonics.Emplace(200.0f, 14000.0f, 35.0f,  0.0f);   // Dominant long wave
	WaveHarmonics.Emplace(80.0f,   6000.0f, 55.0f,  1.5f);   // Mid-range crossing wave
	WaveHarmonics.Emplace(30.0f,   2000.0f, 15.0f,  3.14f);  // Shorter chop
	WaveHarmonics.Emplace(10.0f,   800.0f,  45.0f,  0.7f);   // Capillary/small waves
}

void AShellPawn::EvaluateWaveKinematics(const FVector& Location, float Time, float& OutSurfaceZ, FVector& OutFluidVel, FVector& OutWaveNormal)
{
	OutSurfaceZ = OceanSurfaceZ;
	OutFluidVel = FVector::ZeroVector;
	
	// Depth below standard ocean level (capped at 0 for surface calculations)
	float ZDepth = FMath::Min(0.0f, Location.Z - OceanSurfaceZ);
	FVector2D Pos2D(Location.X, Location.Y);

	float GradX = 0.0f;
	float GradY = 0.0f;

	for (const FGerstnerHarmonic& H : WaveHarmonics)
	{
		float Phase = FVector2D::DotProduct(H.Direction, Pos2D) * H.K - H.Omega * Time + H.PhaseOffset;
		float CosP = FMath::Cos(Phase);
		float SinP = FMath::Sin(Phase);

		// Accumulate Surface Elevation
		OutSurfaceZ += H.Amplitude * CosP;

		// Kinematics Exponential Decay e^(k*z)
		float DepthDecay = FMath::Exp(H.K * ZDepth);

		// Orbital Velocity field
		float VelMag = H.Amplitude * H.Omega * DepthDecay;
		OutFluidVel.X += H.Direction.X * VelMag * CosP;
		OutFluidVel.Y += H.Direction.Y * VelMag * CosP;
		OutFluidVel.Z += VelMag * SinP;

		// Wave surface gradient (derivative of elevation) for normal vector
		float D = -H.Amplitude * H.K * SinP;
		GradX += H.Direction.X * D;
		GradY += H.Direction.Y * D;
	}

	// Normal aligns with global Z far underwater, but tilts with wave surface near the top
	OutWaveNormal = FVector(-GradX, -GradY, 1.0f).GetSafeNormal();
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
		ShowCockpitHUD(NewPC);
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
	if (bSystemsHalted)
	{
		return;
	}
	if (AAdminPlayerController* PC = Cast<AAdminPlayerController>(GetController()))
	{
		PC->TryInteract();
	}
}

void AShellPawn::ApplyThrust(const FInputActionValue& Value)
{
	if (bSystemsHalted)
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
	if (bSystemsHalted)
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
	if (bSystemsHalted)
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
	if (bIsStabilizing)
	{
		return;
	}
	bIsStabilizing = true;
	const float TiltDeg = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(BoxRoot->GetUpVector(), FVector::UpVector), -1.f, 1.f)));
	PushTerminalLog(TEXT("gyro"), FString::Printf(TEXT("stabilizer engaged - aligning, tilt %.1f deg"), TiltDeg), EAOSHudLogSeverity::System);
}

void AShellPawn::UpdateHydrodynamics(float DeltaTime)
{
	const FVector SubLocation = BoxRoot->GetComponentLocation();
	const FVector CurrentVelocity = BoxRoot->GetComponentVelocity();
	
	const bool bHasDriver = (GetController() != nullptr); 
	
	float LocalWaveZ = OceanSurfaceZ;
	FVector FluidVelocity = FVector::ZeroVector;
	FVector TargetNormal = FVector::UpVector;
	
	// Evaluates absolute fluid velocity at the current depth
	EvaluateWaveKinematics(SubLocation, GetWorld()->GetTimeSeconds(), LocalWaveZ, FluidVelocity, TargetNormal);

	bool bInWater = (SubLocation.Z <= LocalWaveZ);

	if (bInWater)
	{
		// Disable native engine gravity to handle buoyancy and penetration manually
		BoxRoot->SetEnableGravity(false);

		// Archimedes volume penetration: Gravity smoothly transitions to 0 as the hull sinks (first 150 cm)
		float SubmergedDepth = LocalWaveZ - SubLocation.Z;
		float EntryGravityFraction = FMath::Clamp(1.0f - (SubmergedDepth / 150.0f), 0.0f, 1.0f);
		if (EntryGravityFraction > 0.01f)
		{
			// Pull down with residual gravity during surface piercing to create a heavy physical splash
			BoxRoot->AddForce(FVector(0.f, 0.f, -980.0f * EntryGravityFraction), NAME_None, true);
		}

		// Morison Equation: Hydrodynamic drag opposing relative velocity
		FVector RelativeVelocity = CurrentVelocity - FluidVelocity;
		float RelSpeed = RelativeVelocity.Size();
		float DragCoeff = LinearDrag + (QuadraticDrag * RelSpeed);
		
		float MaxSafeDrag = 0.5f / FMath::Max(DeltaTime, 0.0001f);
		DragCoeff = FMath::Min(DragCoeff, MaxSafeDrag);

		FVector DragAccel = -RelativeVelocity * DragCoeff;
		BoxRoot->AddForce(DragAccel, NAME_None, true);

		// Angular Hydrodynamic Damping
		FVector AngularVel = BoxRoot->GetPhysicsAngularVelocityInRadians();
		float SafeAngularDrag = FMath::Min(AngularDrag, MaxSafeDrag);
		BoxRoot->AddTorqueInRadians(-AngularVel * SafeAngularDrag, NAME_None, true);

		if (!bHasDriver)
		{
			// EMPTY BOAT MODE: Uses Archimedes spring to stay afloat at the dock
			if (SubLocation.Z > LocalWaveZ - 500.0f)
			{
				float TargetZ = LocalWaveZ - 25.0f; 
				float ZError = TargetZ - SubLocation.Z;
				float BuoyancyAccelZ = (ZError * DockFlotationStiffness) - (CurrentVelocity.Z * DockFlotationDamping);
				BoxRoot->AddForce(FVector(0.f, 0.f, BuoyancyAccelZ), NAME_None, true);
			}
			else
			{
				// Deep underwater parking brake
				BoxRoot->AddForce(FVector(0.f, 0.f, -CurrentVelocity.Z * 4.0f), NAME_None, true);
			}

			// Automatically align empty boat with waves
			FVector SubUp = BoxRoot->GetUpVector();
			FVector RestoringTorqueAxis = FVector::CrossProduct(SubUp, TargetNormal);
			BoxRoot->AddTorqueInRadians(RestoringTorqueAxis * RestoringStiffness, NAME_None, true);
		}
		else if (bSystemsHalted)
		{
			// HALTED: engines and gyro offline - the dead hull settles slowly.
			CurrentBallastForce = FMath::FInterpTo(CurrentBallastForce, 0.f, DeltaTime, BallastChangeSpeed);
			CurrentThrustScalar = FMath::FInterpTo(CurrentThrustScalar, 0.f, DeltaTime, ThrustRampSpeed);
			BoxRoot->AddForce(FVector(0.f, 0.f, -HaltedSinkAcceleration), NAME_None, true);
		}
		else
		{
			// MANNED 6DOF MODE: Pure Neutral Buoyancy underwater

			// Apply vertical engines only
			CurrentBallastForce = FMath::FInterpTo(CurrentBallastForce, TargetBallastForce, DeltaTime, BallastChangeSpeed);
			BoxRoot->AddForce(FVector(0.f, 0.f, CurrentBallastForce), NAME_None, true);

			// Apply directional engines only
			CurrentThrustScalar = FMath::FInterpTo(CurrentThrustScalar, TargetThrustScalar, DeltaTime, ThrustRampSpeed);
			if (CurrentThrustScalar > 0.05f)
			{
				FVector LocalAccel = BoxRoot->GetComponentTransform().TransformVector(CurrentMoveInput * CurrentThrustScalar);
				BoxRoot->AddForce(LocalAccel, NAME_None, true);
			}

			// Manual Gyrostabilizer (Only active when key is pressed)
			if (bIsStabilizing)
			{
				FVector SubUp = BoxRoot->GetUpVector();
				FVector RestoringTorqueAxis = FVector::CrossProduct(SubUp, FVector::UpVector);
				BoxRoot->AddTorqueInRadians(RestoringTorqueAxis * (RestoringStiffness * 3.0f), NAME_None, true);

				// Auto-disable when horizon alignment is reached
				if (FVector::DotProduct(SubUp, FVector::UpVector) > 0.995f && AngularVel.Size() < 0.1f)
				{
					bIsStabilizing = false;
					PushTerminalLog(TEXT("gyro"), TEXT("horizon locked - stabilizer idle"), EAOSHudLogSeverity::Info);
				}
			}
		}
	}
	else
	{
		// AIR STATE: Full engine gravity, propulsion disabled
		BoxRoot->SetEnableGravity(true);
		CurrentThrustScalar = 0.f;
		TargetThrustScalar = 0.f;
		CurrentBallastForce = 0.f;
		if (bIsStabilizing)
		{
			PushTerminalLog(TEXT("gyro"), TEXT("no water contact - stabilizer off"), EAOSHudLogSeverity::Warning);
		}
		bIsStabilizing = false;
	}
}

void AShellPawn::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	UpdateHydrodynamics(DeltaTime);
	UpdateEnergyLoads();
	UpdateLights(DeltaTime);
	UpdateCameraGlitch(DeltaTime);
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
	bBoostHeld = !bSystemsHalted;
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
			Light->SetIntensity(Cached.BaseIntensity * Level);
		}
		Light->SetVisibility(Level > 0.001f);
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
void AShellPawn::ShowCockpitHUD(APlayerController* PC)
{
	if (!PC || !PC->IsLocalController())
	{
		return;
	}
	if (!CockpitHUD)
	{
		UClass* WidgetClass = HUDWidgetClass ? HUDWidgetClass.Get() : UPlayerSubmarineHUDWidget::StaticClass();
		CockpitHUD = CreateWidget<UPlayerSubmarineHUDWidget>(PC, WidgetClass);
		if (!CockpitHUD)
		{
			return;
		}
		CockpitHUD->AddToViewport(HUDZOrder);
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
float AShellPawn::GetDepthMeters() const
{
	return FMath::Max(0.f, float(OceanSurfaceZ - GetActorLocation().Z) / 100.f);
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