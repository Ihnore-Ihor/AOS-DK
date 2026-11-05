#pragma once

#include "CoreMinimal.h"
#include "ProceduralMeshComponent.h"

/**
 * CPU mesh buffer for UProceduralMeshComponent sections + triangle helpers that pick the winding
 * from the intended outward normal (UE front faces: cross(B-A, C-A) points AWAY from the normal).
 */
struct AOS_DK_API FDaemonMeshData
{
	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UV0;
	TArray<FLinearColor> Colors;
	TArray<FProcMeshTangent> Tangents;

	void Reset();
	int32 AddVertex(const FVector& Position, const FVector& Normal, const FVector2D& UV, const FLinearColor& Color = FLinearColor::White);
	void AddTriangleFacing(int32 A, int32 B, int32 C, const FVector& OutwardNormal);
	/** A-B-C-D is a loop (either direction). */
	void AddQuadFacing(int32 A, int32 B, int32 C, int32 D, const FVector& OutwardNormal);
	/** Flat-shaded triangle (own vertices, face normal). */
	void AddFlatTriangle(const FVector& A, const FVector& B, const FVector& C, const FVector& OutwardNormal, const FLinearColor& Color = FLinearColor::White);
	void AddFlatQuad(const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FVector& OutwardNormal, const FLinearColor& Color = FLinearColor::White);

	void CreateSection(UProceduralMeshComponent* Mesh, int32 SectionIndex) const;
	void UpdateSection(UProceduralMeshComponent* Mesh, int32 SectionIndex) const;
};

/**
 * Procedural model of the "system daemon" (an underwater security process): plated faceted core
 * with glowing seams, a lens eye, two segmented gyroscopic halos and data-cable tendrils.
 * Everything is generated deterministically in C++ - no imported mesh is required.
 * Local frame: +X = forward (eye), the halos spin around X.
 */
namespace AOSDaemonGeometry
{
	/** Faceted plated sphere: every icosphere face becomes a slightly lifted, shrunk plate (seams show the glow core). Plates within FrontOpeningDeg of +X are skipped (eye socket). */
	AOS_DK_API void BuildPlatedCore(FDaemonMeshData& Out, float Radius, int32 Subdivisions, float PlateShrink, float FrontOpeningDeg, uint32 Seed);

	/** Inner faceted sphere (glow material) visible through the plate seams. */
	AOS_DK_API void BuildFacetedSphere(FDaemonMeshData& Out, float Radius, int32 Subdivisions);

	/** Smooth dome facing +X (the eye lens), polar angle 0..PolarMaxDeg. */
	AOS_DK_API void BuildLens(FDaemonMeshData& Out, float Radius, float PolarMaxDeg, int32 Rings, int32 Sides);

	/** Ring in the YZ plane around X, split into Segments arcs with gaps. Inner face -> Glow. */
	AOS_DK_API void BuildSegmentedRing(FDaemonMeshData& Hull, FDaemonMeshData& Glow, float Radius, float RadialThickness,
		float AxialWidth, int32 Segments, float GapDeg, int32 StepsPerSegment);

	/** Smooth tapered tube along a spine (+ tip cap). Vertex colour R = glow mask (brighter towards the tip). */
	AOS_DK_API void BuildTube(FDaemonMeshData& Out, TConstArrayView<FVector> Spine, TConstArrayView<float> Radii, int32 Sides);

	/** Tube positions/normals only (same topology as BuildTube) - for per-frame UpdateSection. */
	AOS_DK_API void UpdateTube(FDaemonMeshData& InOut, TConstArrayView<FVector> Spine, TConstArrayView<float> Radii, int32 Sides);
}
