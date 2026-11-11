#include "AOS_RSSPageMapComponent.h"
#include "AOS_DK/Core/UI/AOSDraculaPalette.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/TextRenderComponent.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"

namespace
{
	constexpr float CellSize = 10.f;
	constexpr float CellGap = 2.5f;
	constexpr float CellDepth = 3.f;
	constexpr float CellPitch = CellSize + CellGap;
	constexpr float PlateHalf = 26.f;
	constexpr float BorderHalf = 26.6f;
	constexpr float BorderWidth = 1.2f;
	constexpr float PipZ = -31.f;
	constexpr float PipPitch = 8.f;
	constexpr float PipRadius = 2.5f;
	constexpr float PipDepth = 2.f;
	constexpr float PlateX = -2.f;

	/** Position on the square ring (clockwise from the top-left corner as seen by the viewer). Returns (u, v) in viewer space: u right, v up. */
	FVector2D RingPoint(float Alpha, FVector2D& OutNormal)
	{
		const float P = FMath::Frac(Alpha) * 4.f;
		const int32 Side = FMath::Clamp(FMath::FloorToInt(P), 0, 3);
		const float T = P - Side;
		const float H = BorderHalf;
		switch (Side)
		{
		case 0: OutNormal = FVector2D(0, 1);  return FVector2D(-H + 2 * H * T, H);   // top, left -> right
		case 1: OutNormal = FVector2D(1, 0);  return FVector2D(H, H - 2 * H * T);    // right, top -> bottom
		case 2: OutNormal = FVector2D(0, -1); return FVector2D(H - 2 * H * T, -H);   // bottom, right -> left
		default: OutNormal = FVector2D(-1, 0); return FVector2D(-H, -H + 2 * H * T); // left, bottom -> top
		}
	}
}

UAOS_RSSPageMapComponent::UAOS_RSSPageMapComponent(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.f; // every frame: the billboard must never lag behind the camera
	SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SetCastShadow(false);
	bUseAsyncCooking = false;
	SetAbsolute(true, true, true);
	SetHiddenInGame(false);
	SetVisibility(true);
	SetBoundsScale(4.f);
}

void UAOS_RSSPageMapComponent::OnRegister()
{
	Super::OnRegister();
	if (!GetWorld() || !GetWorld()->IsGameWorld())
	{
		return;
	}
	if (!LabelText)
	{
		LabelText = NewObject<UTextRenderComponent>(GetOwner(), TEXT("PageMapLabel"));
		LabelText->SetupAttachment(this);
		LabelText->SetRelativeLocation(FVector(4.f, 0.f, 31.f));
		LabelText->SetWorldSize(3.5f);
		LabelText->SetHorizontalAlignment(EHTA_Center);
		LabelText->SetVerticalAlignment(EVRTA_TextCenter);
		LabelText->SetCastShadow(false);
		LabelText->SetTextRenderColor(AOSDracula::Cyan().ToFColor(true));
		LabelText->RegisterComponent();
	}
	if (!CountText)
	{
		CountText = NewObject<UTextRenderComponent>(GetOwner(), TEXT("PageMapCount"));
		CountText->SetupAttachment(this);
		CountText->SetRelativeLocation(FVector(4.f, 15.f, PipZ));
		CountText->SetWorldSize(3.f);
		CountText->SetHorizontalAlignment(EHTA_Center);
		CountText->SetVerticalAlignment(EVRTA_TextCenter);
		CountText->SetCastShadow(false);
		CountText->SetTextRenderColor(AOSDracula::Foreground().ToFColor(true));
		CountText->RegisterComponent();
	}
	BuildTopology();
	UpdateTexts();
}

void UAOS_RSSPageMapComponent::BeginPlay()
{
	Super::BeginPlay();
	UMaterialInterface* Mat = PageMaterial.IsNull() ? nullptr : PageMaterial.LoadSynchronous();
	if (!Mat)
	{
		Mat = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/AOS_DK_Game/Enemies/Reaper/Materials/M_RPR_PageMap.M_RPR_PageMap"), nullptr, LOAD_NoWarn);
	}
	if (!Mat)
	{
		Mat = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"), nullptr, LOAD_NoWarn);
	}
	if (Mat)
	{
		SetMaterial(0, Mat);
	}
	SetHiddenInGame(false);
	SetVisibility(true, true);
	bShown = true;
	bDirty = true;
}

void UAOS_RSSPageMapComponent::OnComponentDestroyed(bool bDestroyingHierarchy)
{
	if (LabelText) { LabelText->DestroyComponent(); }
	if (CountText) { CountText->DestroyComponent(); }
	Super::OnComponentDestroyed(bDestroyingHierarchy);
}

// ---------------------------------------------------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------------------------------------------------
void UAOS_RSSPageMapComponent::SetOwnerLabel(int32 InPID)
{
	PID = InPID;
	UpdateTexts();
}

void UAOS_RSSPageMapComponent::SetHealth(float Current, float Max)
{
	MaxHealth = FMath::Max(Max, 1.f);
	Health = FMath::Clamp(Current, 0.f, MaxHealth);
	const int32 NewResident = FMath::Clamp(FMath::CeilToInt(NumPages * Health / MaxHealth), 0, NumPages);
	// Pages are freed from the bottom-right backwards (the grid drains like reaped memory).
	for (int32 i = 0; i < NumPages; ++i)
	{
		const bool bShouldBeResident = i < NewResident;
		if (Pages[i].bResident && !bShouldBeResident)
		{
			Pages[i].bResident = false;
			Pages[i].FlashTime = FlashDuration;
			Pages[i].EjectTime = -1.f;
		}
		else if (!Pages[i].bResident && bShouldBeResident)
		{
			Pages[i] = FPageState();
		}
	}
	ResidentPages = NewResident;
	UpdateTexts();
	bDirty = true;
}

void UAOS_RSSPageMapComponent::SetAlert(EAOSPageAlert InAlert)
{
	if (Alert != InAlert)
	{
		Alert = InAlert;
		bDirty = true;
	}
}

void UAOS_RSSPageMapComponent::SetDecoyCharges(int32 Charges, int32 MaxCharges)
{
	if (DecoyCharges != Charges || DecoyMax != MaxCharges)
	{
		DecoyCharges = Charges;
		DecoyMax = MaxCharges;
		bDirty = true;
	}
}

void UAOS_RSSPageMapComponent::SetEvasionReadiness(float InReadiness)
{
	const float R = FMath::Clamp(InReadiness, 0.f, 1.f);
	if (!FMath::IsNearlyEqual(R, Readiness, 1.f / BorderSegments))
	{
		Readiness = R;
		bDirty = true;
	}
}

void UAOS_RSSPageMapComponent::PlayDeathRelease()
{
	if (bReleasing)
	{
		return;
	}
	bReleasing = true;
	ReleaseTime = 0.f;
	for (FPageState& P : Pages)
	{
		if (P.bResident)
		{
			P.FlashTime = FlashDuration;
		}
	}
	if (LabelText)
	{
		LabelText->SetText(FText::FromString(FString::Printf(TEXT("oom_reaper[%d] exit 137"), PID)));
	}
	bDirty = true;
}

void UAOS_RSSPageMapComponent::UpdateTexts()
{
	if (LabelText && !bReleasing)
	{
		LabelText->SetText(FText::FromString(FString::Printf(TEXT("oom_reaper[%d]"), PID)));
	}
	if (CountText)
	{
		CountText->SetText(FText::FromString(FString::Printf(TEXT("RSS %d/%d"), ResidentPages, NumPages)));
	}
}

FLinearColor UAOS_RSSPageMapComponent::ResidentColor() const
{
	const bool bCritical = MaxHealth > 0.f && Health / MaxHealth <= 0.25f;
	if (Alert == EAOSPageAlert::Brine)
	{
		return AOSDracula::Purple();
	}
	if (bCritical)
	{
		// 7 Hz error flicker between Red and a darker Red.
		const bool bOn = FMath::Frac(Clock * 7.f) < 0.5f;
		return bOn ? AOSDracula::Red() : AOSDracula::Mix(AOSDracula::Red(), AOSDracula::Background(), 0.6f);
	}
	switch (Alert)
	{
	case EAOSPageAlert::Investigate: return AOSDracula::Yellow();
	case EAOSPageAlert::Combat:      return AOSDracula::Orange();
	case EAOSPageAlert::Critical:    return AOSDracula::Red();
	case EAOSPageAlert::Patrol:
	default:                         return AOSDracula::Cyan();
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Visibility / tick
// ---------------------------------------------------------------------------------------------------------------------
bool UAOS_RSSPageMapComponent::ShouldBeVisible(const FVector& CameraLocation, const FVector& CameraForward, float& OutDistance) const
{
	const FVector Here = GetComponentLocation();
	OutDistance = FVector::Dist(CameraLocation, Here);
	if (bAlwaysVisible)
	{
		return true;
	}
	if (OutDistance > MaxVisibleDistance || bReleasing)
	{
		return bReleasing && OutDistance <= MaxVisibleDistance;
	}
	const bool bHurt = Health < MaxHealth - KINDA_SMALL_NUMBER;
	const bool bAlerted = Alert != EAOSPageAlert::Patrol;
	const bool bAimed = FVector::DotProduct(CameraForward, (Here - CameraLocation).GetSafeNormal()) >= FMath::Cos(FMath::DegreesToRadians(20.f));
	return bHurt || bAlerted || bAimed;
}

void UAOS_RSSPageMapComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	UWorld* World = GetWorld();
	if (!World || !World->IsGameWorld())
	{
		return;
	}
	Clock += DeltaTime;

	// Shown for whatever the player's camera is (Shell cockpit, free-fly, on foot, even while the Shell flag says "docked in LARS"):
	// the only gate is the distance check in ShouldBeVisible. (It used to require an AShellPawn that is NOT in the LARS cradle, so a
	// normal PIE start -- BP_AdminCharacter -- or a Shell whose cradle flag is set never saw the display.)
	APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0);
	bool bWantShown = false;
	float Dist = 0.f;
	if (Cam)
	{
		bWantShown = ShouldBeVisible(Cam->GetCameraLocation(), Cam->GetActorForwardVector(), Dist);
	}
	if (bWantShown != bShown)
	{
		bShown = bWantShown;
		SetVisibility(bShown, true);
		if (LabelText) { LabelText->SetVisibility(bShown); }
		if (CountText) { CountText->SetVisibility(bShown); }
		if (bShown) { bDirty = true; }
	}
	if (!bShown)
	{
		return;
	}

	// Follow the socket with a critically damped spring; billboard to the camera (no pitch clamp).
	FVector Target = GetComponentLocation();
	if (const USceneComponent* Parent = GetAttachParent())
	{
		Target = Parent->GetSocketLocation(GetAttachSocketName());
	}
	Target.Z += HeightAboveSocket;
	if (!bHaveSmoothed || SmoothedLocation.ContainsNaN() || SmoothedVelocity.ContainsNaN() || FVector::DistSquared(SmoothedLocation, Target) > FMath::Square(600.f))
	{
		// First frame, a teleport (Reaper respawn / Shell moved) or a numeric blow-up: snap instead of springing across the map.
		SmoothedLocation = Target;
		SmoothedVelocity = FVector::ZeroVector;
		bHaveSmoothed = true;
	}
	else
	{
		// Semi-implicit Euler is only stable for W*dt < ~2: integrate in fixed sub-steps so a long frame cannot make the spring diverge.
		const float W = FollowOmega;
		float Remaining = FMath::Min(DeltaTime, 0.25f);
		while (Remaining > KINDA_SMALL_NUMBER)
		{
			const float Dt = FMath::Min(Remaining, 1.f / 60.f);
			const FVector Delta = SmoothedLocation - Target;
			const FVector Accel = -2.f * W * SmoothedVelocity - W * W * Delta;
			SmoothedVelocity += Accel * Dt;
			SmoothedLocation += SmoothedVelocity * Dt;
			Remaining -= Dt;
		}
	}
	FRotator Facing = FRotationMatrix::MakeFromX(Cam->GetCameraLocation() - SmoothedLocation).Rotator();
	SetWorldLocationAndRotation(SmoothedLocation, Facing);
	SetWorldScale3D(FVector(DisplayScale)); // never 0

	// Page animations.
	bool bAnimating = false;
	for (FPageState& P : Pages)
	{
		if (P.FlashTime > 0.f)
		{
			P.FlashTime -= DeltaTime;
			bAnimating = true;
			if (P.FlashTime <= 0.f && !P.bResident)
			{
				P.EjectTime = 0.f;
			}
		}
		else if (P.EjectTime >= 0.f && !P.bGone)
		{
			P.EjectTime += DeltaTime;
			bAnimating = true;
			if (P.EjectTime >= EjectDuration && !bReleasing)
			{
				P.bGone = true;
			}
		}
	}
	if (bReleasing)
	{
		ReleaseTime += DeltaTime;
		bAnimating = true;
		if (ReleaseTime > 1.2f)
		{
			DestroyComponent();
			return;
		}
	}
	const bool bFlicker = MaxHealth > 0.f && Health / MaxHealth <= 0.25f;
	if (bDirty || bAnimating || bFlicker || Alert == EAOSPageAlert::Brine)
	{
		RebuildMesh();
		bDirty = false;
	}
}

// ---------------------------------------------------------------------------------------------------------------------
// Geometry
// ---------------------------------------------------------------------------------------------------------------------
void UAOS_RSSPageMapComponent::BuildTopology()
{
	// Vertex count is constant; the topology is emitted once by a first (dummy) rebuild.
	Triangles.Reset();
	bSectionCreated = false;
	bDirty = true;
}

void UAOS_RSSPageMapComponent::RebuildMesh()
{
	const bool bFirst = Triangles.Num() == 0;
	Vertices.Reset();
	Colors.Reset();
	if (bFirst)
	{
		Triangles.Reset();
	}

	// (u, v) = viewer right / up; local Y = -u because the viewer looks along -X.
	auto V = [](float X, float U, float Vv) { return FVector(X, -U, Vv); };
	auto AddQuad = [&](const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FLinearColor& Col)
	{
		const int32 Base = Vertices.Num();
		Vertices.Add(A); Vertices.Add(B); Vertices.Add(C); Vertices.Add(D);
		for (int32 i = 0; i < 4; ++i) { Colors.Add(Col); }
		if (bFirst)
		{
			// Both windings: the unlit vertex-colour material is single sided and the PMC winding convention is easy to get wrong.
			for (const int32 Idx : { 0, 1, 2, 0, 2, 3, 0, 2, 1, 0, 3, 2 })
			{
				Triangles.Add(Base + Idx);
			}
		}
	};
	auto AddPrism = [&](float X0, float UC, float VC, float Half, float Depth, const FLinearColor& Col)
	{
		const float XF = X0 + Depth * 0.5f;   // front face (towards the viewer)
		const float XB = X0 - Depth * 0.5f;
		const float L = UC - Half, R = UC + Half, B = VC - Half, T = VC + Half;
		AddQuad(V(XF, L, T), V(XF, R, T), V(XF, R, B), V(XF, L, B), Col);                                   // front
		const FLinearColor Side = Col * 0.55f;
		AddQuad(V(XB, L, T), V(XB, R, T), V(XF, R, T), V(XF, L, T), FLinearColor(Side.R, Side.G, Side.B, Col.A)); // top
		AddQuad(V(XB, L, B), V(XB, R, B), V(XF, R, B), V(XF, L, B), FLinearColor(Side.R, Side.G, Side.B, Col.A)); // bottom
		AddQuad(V(XB, L, T), V(XF, L, T), V(XF, L, B), V(XB, L, B), FLinearColor(Side.R, Side.G, Side.B, Col.A)); // left
		AddQuad(V(XB, R, T), V(XF, R, T), V(XF, R, B), V(XB, R, B), FLinearColor(Side.R, Side.G, Side.B, Col.A)); // right
	};

	// Backplate.
	AddQuad(V(PlateX, -PlateHalf, PlateHalf), V(PlateX, PlateHalf, PlateHalf), V(PlateX, PlateHalf, -PlateHalf), V(PlateX, -PlateHalf, -PlateHalf),
		AOSDracula::Background() * 0.3f);

	// Border: clockwise fill from the top-left corner by Readiness.
	const FLinearColor BorderReady = AOSDracula::Purple();
	const FLinearColor BorderFilling = FLinearColor(0.1221f, 0.1683f, 0.3712f);
	const FLinearColor BorderEmpty = AOSDracula::Background() * 0.15f;
	const int32 Filled = FMath::RoundToInt(Readiness * BorderSegments);
	for (int32 i = 0; i < BorderSegments; ++i)
	{
		FVector2D N0, N1;
		const FVector2D P0 = RingPoint(static_cast<float>(i) / BorderSegments, N0);
		const FVector2D P1 = RingPoint(static_cast<float>(i + 1) / BorderSegments - 1e-4f, N1);
		const float Hw = BorderWidth * 0.5f;
		const FLinearColor Col = i < Filled ? (Readiness >= 0.999f ? BorderReady : BorderFilling) : BorderEmpty;
		AddQuad(V(0.f, P0.X - N0.X * Hw, P0.Y - N0.Y * Hw), V(0.f, P0.X + N0.X * Hw, P0.Y + N0.Y * Hw),
			V(0.f, P1.X + N1.X * Hw, P1.Y + N1.Y * Hw), V(0.f, P1.X - N1.X * Hw, P1.Y - N1.Y * Hw), Col);
	}

	// Pages (slot + prism per cell, constant vertex count).
	const FLinearColor Resident = ResidentColor();
	const FLinearColor FreedSlot = AOSDracula::Background() * 0.08f;
	for (int32 Index = 0; Index < NumPages; ++Index)
	{
		const int32 Row = Index / GridDim;
		const int32 Col = Index % GridDim;
		const float U = (Col - 1.5f) * CellPitch;
		const float Vv = (1.5f - Row) * CellPitch;
		const FPageState& P = Pages[Index];
		const float Half = CellSize * 0.5f;

		AddQuad(V(0.f, U - Half, Vv + Half), V(0.f, U + Half, Vv + Half), V(0.f, U + Half, Vv - Half), V(0.f, U - Half, Vv - Half), FreedSlot);

		FLinearColor PageColor = Resident;
		float Scale = 1.f;
		float OffsetX = 0.f;
		float OffsetU = 0.f, OffsetV = 0.f;
		if (!P.bResident || bReleasing)
		{
			if (P.FlashTime > 0.f)
			{
				PageColor = AOSDracula::Foreground();
			}
			else if (P.EjectTime >= 0.f && !bReleasing)
			{
				const float E = FMath::Clamp(P.EjectTime / EjectDuration, 0.f, 1.f);
				OffsetX = 25.f * E;
				Scale = 1.f - E;
				PageColor = AOSDracula::Mix(AOSDracula::Foreground(), Resident, E);
			}
			else if (!bReleasing)
			{
				Scale = 0.f;
			}
		}
		if (bReleasing)
		{
			if (P.FlashTime > 0.f && ReleaseTime < FlashDuration)
			{
				PageColor = AOSDracula::Foreground();
			}
			else if (P.bResident || P.EjectTime >= 0.f)
			{
				const float T = FMath::Max(0.f, ReleaseTime - FlashDuration);
				FVector2D Radial(U, Vv);
				Radial = Radial.GetSafeNormal();
				OffsetU = Radial.X * 150.f * T;
				OffsetV = Radial.Y * 150.f * T - 0.5f * 60.f * T * T;
				OffsetX = 10.f * T;
				Scale = FMath::Clamp(1.f - T / 1.0f, 0.f, 1.f);
			}
			else
			{
				Scale = 0.f;
			}
		}
		if (P.bGone && !bReleasing)
		{
			Scale = 0.f;
		}
		AddPrism(CellDepth * 0.5f + OffsetX, U + OffsetU, Vv + OffsetV, FMath::Max(Half * Scale, 0.001f), CellDepth * FMath::Max(Scale, 0.001f), PageColor);
	}

	// Decoy pips (hex discs under the grid).
	for (int32 k = 0; k < NumPips; ++k)
	{
		const float U = (k - 1) * PipPitch;
		const bool bReady = k < DecoyCharges;
		const FLinearColor Col = bReady ? AOSDracula::Purple() : AOSDracula::Background() * 0.2f;
		const float XF = PipDepth;
		// Hex as 2 quads (a rectangle plus a rotated one) keeps the constant-quad topology: three rhombi.
		const float R = PipRadius;
		const float Hx = R * 0.5f, Hy = R * 0.866f;
		AddQuad(V(XF, U - R, PipZ), V(XF, U - Hx, PipZ + Hy), V(XF, U + Hx, PipZ + Hy), V(XF, U + R, PipZ), Col);
		AddQuad(V(XF, U - R, PipZ), V(XF, U + R, PipZ), V(XF, U + Hx, PipZ - Hy), V(XF, U - Hx, PipZ - Hy), Col);
	}

	if (Normals.Num() != Vertices.Num())
	{
		Normals.Init(FVector::ForwardVector, Vertices.Num());
		UVs.Init(FVector2D::ZeroVector, Vertices.Num());
		Tangents.Init(FProcMeshTangent(0.f, 1.f, 0.f), Vertices.Num());
	}

	if (!bSectionCreated)
	{
		CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors, Tangents, false);
		bSectionCreated = true;
	}
	else
	{
		UpdateMeshSection_LinearColor(0, Vertices, Normals, UVs, Colors, Tangents);
	}
}
