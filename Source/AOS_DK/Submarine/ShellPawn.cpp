#include "ShellPawn.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Camera/CameraComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "AOS_DK/Player/AdminCharacter.h"
#include "AOS_DK/Player/PlayerController/AdminPlayerController.h"
#include "Engine/Engine.h"
#include "GameFramework/PhysicsVolume.h"
#include "GameFramework/CharacterMovementComponent.h"

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
}

void AShellPawn::BeginPlay()
{
	Super::BeginPlay();
	TargetBallastForce = 0.f;
	CurrentBallastForce = 0.f;
	bIsStabilizing = false;

	InitializeWaves();
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
	}
	else
	{
		TargetBallastForce = 0.f;
		CurrentBallastForce = 0.f;
		bIsStabilizing = false;
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
	if (AAdminPlayerController* PC = Cast<AAdminPlayerController>(GetController()))
	{
		PC->TryInteract();
	}
}

void AShellPawn::ApplyThrust(const FInputActionValue& Value)
{
	FVector RawInput = Value.Get<FVector>();
	// Mapping: X is Forward/Back (W/S), Y is Strafing (A/D)
	CurrentMoveInput = FVector(RawInput.X * ForwardThrust, RawInput.Y * LateralThrust, 0.f);
	TargetThrustScalar = 1.0f;
}

void AShellPawn::ResetThrust(const FInputActionValue& Value)
{
	CurrentMoveInput = FVector::ZeroVector;
	TargetThrustScalar = 0.f;
}

void AShellPawn::ApplyRotation(const FInputActionValue& Value)
{
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
	bIsStabilizing = true;
	if (GEngine) GEngine->AddOnScreenDebugMessage(7, 2.0f, FColor::Green, TEXT("[STABILIZER] ALIGNING"));
}

void AShellPawn::UpdateHydrodynamics(float DeltaTime)
{
	const FVector SubLocation = BoxRoot->GetComponentLocation();
	const FVector CurrentVelocity = BoxRoot->GetComponentVelocity();
	
	const bool bHasDriver = (GetController() != nullptr); 
	
	float LocalWaveZ = OceanSurfaceZ;
	FVector FluidVelocity = FVector::ZeroVector;
	FVector TargetNormal = FVector::UpVector;
	
	// Evaluates absolute fluid velocity at the current depth (exponentially decays to 0 underwater)
	EvaluateWaveKinematics(SubLocation, GetWorld()->GetTimeSeconds(), LocalWaveZ, FluidVelocity, TargetNormal);

	bool bInWater = (SubLocation.Z <= LocalWaveZ);
	BoxRoot->SetEnableGravity(!bInWater);

	if (bInWater)
	{
		// Morison Equation: The wave's physical movement pushes the submarine
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
			// EMPTY BOAT MODE: Uses Archimedes spring to stay afloat like a balloon
			if (SubLocation.Z > LocalWaveZ - 500.0f)
			{
				float TargetZ = LocalWaveZ - 25.0f; 
				float ZError = TargetZ - SubLocation.Z;
				float BuoyancyAccelZ = (ZError * DockFlotationStiffness) - (CurrentVelocity.Z * DockFlotationDamping);
				BoxRoot->AddForce(FVector(0.f, 0.f, BuoyancyAccelZ), NAME_None, true);
			}
			else
			{
				BoxRoot->AddForce(FVector(0.f, 0.f, -CurrentVelocity.Z * 4.0f), NAME_None, true);
			}

			FVector SubUp = BoxRoot->GetUpVector();
			FVector RestoringTorqueAxis = FVector::CrossProduct(SubUp, TargetNormal);
			BoxRoot->AddTorqueInRadians(RestoringTorqueAxis * RestoringStiffness, NAME_None, true);
		}
		else
		{
			// MANNED 6DOF MODE: Pure Neutral Buoyancy. NO surface-seeking mechanics.
			
			// Zero out passenger buoyancy influence
			TArray<AActor*> AttachedActors;
			GetAttachedActors(AttachedActors);
			for (AActor* Attached : AttachedActors)
			{
				if (ACharacter* AttachedChar = Cast<ACharacter>(Attached))
				{
					if (UCharacterMovementComponent* CMC = AttachedChar->GetCharacterMovement())
					{
						CMC->Buoyancy = 0.0f;
					}
				}
			}

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

			// Player-controlled Gyrostabilizer
			if (bIsStabilizing)
			{
				FVector SubUp = BoxRoot->GetUpVector();
				FVector RestoringTorqueAxis = FVector::CrossProduct(SubUp, FVector::UpVector);
				BoxRoot->AddTorqueInRadians(RestoringTorqueAxis * (RestoringStiffness * 3.0f), NAME_None, true);

				if (FVector::DotProduct(SubUp, FVector::UpVector) > 0.995f && AngularVel.Size() < 0.1f)
				{
					bIsStabilizing = false;
				}
			}
		}
	}
	else
	{
		// Air State
		CurrentThrustScalar = 0.f;
		TargetThrustScalar = 0.f;
		CurrentBallastForce = 0.f;
		bIsStabilizing = false;
	}
}

void AShellPawn::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	UpdateHydrodynamics(DeltaTime);
}