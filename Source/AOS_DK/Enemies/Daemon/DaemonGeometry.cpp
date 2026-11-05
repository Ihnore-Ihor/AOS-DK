#include "DaemonGeometry.h"

// ---------------------------------------------------------------------------------------- buffers
void FDaemonMeshData::Reset()
{
	Vertices.Reset();
	Triangles.Reset();
	Normals.Reset();
	UV0.Reset();
	Colors.Reset();
	Tangents.Reset();
}

int32 FDaemonMeshData::AddVertex(const FVector& Position, const FVector& Normal, const FVector2D& UV, const FLinearColor& Color)
{
	Normals.Add(Normal);
	UV0.Add(UV);
	Colors.Add(Color);
	FVector TangentX = FVector::CrossProduct(FVector::UpVector, Normal);
	if (TangentX.SizeSquared() < 1e-4)
	{
		TangentX = FVector::CrossProduct(FVector::ForwardVector, Normal);
	}
	Tangents.Add(FProcMeshTangent(TangentX.GetSafeNormal(), false));
	return Vertices.Add(Position);
}

void FDaemonMeshData::AddTriangleFacing(int32 A, int32 B, int32 C, const FVector& OutwardNormal)
{
	const FVector Cross = FVector::CrossProduct(Vertices[B] - Vertices[A], Vertices[C] - Vertices[A]);
	Triangles.Add(A);
	if (FVector::DotProduct(Cross, OutwardNormal) > 0.0)
	{
		Triangles.Add(C);
		Triangles.Add(B);
	}
	else
	{
		Triangles.Add(B);
		Triangles.Add(C);
	}
}

void FDaemonMeshData::AddQuadFacing(int32 A, int32 B, int32 C, int32 D, const FVector& OutwardNormal)
{
	AddTriangleFacing(A, B, C, OutwardNormal);
	AddTriangleFacing(A, C, D, OutwardNormal);
}

void FDaemonMeshData::AddFlatTriangle(const FVector& A, const FVector& B, const FVector& C, const FVector& OutwardNormal, const FLinearColor& Color)
{
	const FVector N = OutwardNormal.GetSafeNormal();
	const int32 IA = AddVertex(A, N, FVector2D(0.0, 0.0), Color);
	const int32 IB = AddVertex(B, N, FVector2D(1.0, 0.0), Color);
	const int32 IC = AddVertex(C, N, FVector2D(0.5, 1.0), Color);
	AddTriangleFacing(IA, IB, IC, N);
}

void FDaemonMeshData::AddFlatQuad(const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FVector& OutwardNormal, const FLinearColor& Color)
{
	const FVector N = OutwardNormal.GetSafeNormal();
	const int32 IA = AddVertex(A, N, FVector2D(0.0, 0.0), Color);
	const int32 IB = AddVertex(B, N, FVector2D(1.0, 0.0), Color);
	const int32 IC = AddVertex(C, N, FVector2D(1.0, 1.0), Color);
	const int32 ID = AddVertex(D, N, FVector2D(0.0, 1.0), Color);
	AddQuadFacing(IA, IB, IC, ID, N);
}

void FDaemonMeshData::CreateSection(UProceduralMeshComponent* Mesh, int32 SectionIndex) const
{
	if (Mesh)
	{
		Mesh->CreateMeshSection_LinearColor(SectionIndex, Vertices, Triangles, Normals, UV0, Colors, Tangents, false);
	}
}

void FDaemonMeshData::UpdateSection(UProceduralMeshComponent* Mesh, int32 SectionIndex) const
{
	if (Mesh)
	{
		Mesh->UpdateMeshSection_LinearColor(SectionIndex, Vertices, Normals, UV0, Colors, Tangents);
	}
}

// ------------------------------------------------------------------------------------- icosphere
namespace
{
	void BuildIcosphereFaces(int32 Subdivisions, TArray<FVector>& OutCorners /* 3 per face, unit */)
	{
		const double T = (1.0 + FMath::Sqrt(5.0)) * 0.5;
		const FVector V[12] =
		{
			FVector(-1,  T,  0), FVector( 1,  T,  0), FVector(-1, -T,  0), FVector( 1, -T,  0),
			FVector( 0, -1,  T), FVector( 0,  1,  T), FVector( 0, -1, -T), FVector( 0,  1, -T),
			FVector( T,  0, -1), FVector( T,  0,  1), FVector(-T,  0, -1), FVector(-T,  0,  1)
		};
		const int32 F[20][3] =
		{
			{0, 11, 5}, {0, 5, 1}, {0, 1, 7}, {0, 7, 10}, {0, 10, 11},
			{1, 5, 9}, {5, 11, 4}, {11, 10, 2}, {10, 7, 6}, {7, 1, 8},
			{3, 9, 4}, {3, 4, 2}, {3, 2, 6}, {3, 6, 8}, {3, 8, 9},
			{4, 9, 5}, {2, 4, 11}, {6, 2, 10}, {8, 6, 7}, {9, 8, 1}
		};
		TArray<FVector> Faces;
		for (const auto& Face : F)
		{
			Faces.Add(V[Face[0]].GetSafeNormal());
			Faces.Add(V[Face[1]].GetSafeNormal());
			Faces.Add(V[Face[2]].GetSafeNormal());
		}
		for (int32 Level = 0; Level < Subdivisions; ++Level)
		{
			TArray<FVector> Next;
			Next.Reserve(Faces.Num() * 4);
			for (int32 i = 0; i < Faces.Num(); i += 3)
			{
				const FVector A = Faces[i], B = Faces[i + 1], C = Faces[i + 2];
				const FVector AB = (A + B).GetSafeNormal(), BC = (B + C).GetSafeNormal(), CA = (C + A).GetSafeNormal();
				Next.Append({ A, AB, CA, B, BC, AB, C, CA, BC, AB, BC, CA });
			}
			Faces = MoveTemp(Next);
		}
		OutCorners = MoveTemp(Faces);
	}

	uint32 HashFace(uint32 X)
	{
		X ^= X >> 16; X *= 0x7FEB352Du; X ^= X >> 15; X *= 0x846CA68Bu; X ^= X >> 16;
		return X;
	}
}

namespace AOSDaemonGeometry
{
	void BuildPlatedCore(FDaemonMeshData& Out, float Radius, int32 Subdivisions, float PlateShrink, float FrontOpeningDeg, uint32 Seed)
	{
		TArray<FVector> Corners;
		BuildIcosphereFaces(Subdivisions, Corners);
		const double CosOpening = FMath::Cos(FMath::DegreesToRadians(FrontOpeningDeg));
		for (int32 i = 0; i < Corners.Num(); i += 3)
		{
			const FVector Centre = (Corners[i] + Corners[i + 1] + Corners[i + 2]) / 3.0;
			const FVector Normal = Centre.GetSafeNormal();
			if (FVector::DotProduct(Normal, FVector::ForwardVector) > CosOpening)
			{
				continue; // eye socket
			}
			// Deterministic per-plate lift: a machined, armoured look.
			const float Lift = 1.03f + 0.05f * float(HashFace(Seed + uint32(i)) & 0xFF) / 255.f;
			FVector P[3];
			for (int32 k = 0; k < 3; ++k)
			{
				P[k] = (Centre + (Corners[i + k] - Centre) * PlateShrink) * Radius * Lift;
			}
			Out.AddFlatTriangle(P[0], P[1], P[2], Normal);
			// Plate rim (thickness) so the seams read from grazing angles.
			const FVector Inset = Normal * Radius * 0.05f;
			for (int32 k = 0; k < 3; ++k)
			{
				const FVector A = P[k], B = P[(k + 1) % 3];
				const FVector EdgeOut = (((A + B) * 0.5f) - Centre * Radius * Lift).GetSafeNormal();
				Out.AddFlatQuad(A, B, B - Inset, A - Inset, EdgeOut);
			}
		}
	}

	void BuildFacetedSphere(FDaemonMeshData& Out, float Radius, int32 Subdivisions)
	{
		TArray<FVector> Corners;
		BuildIcosphereFaces(Subdivisions, Corners);
		for (int32 i = 0; i < Corners.Num(); i += 3)
		{
			const FVector Normal = (Corners[i] + Corners[i + 1] + Corners[i + 2]).GetSafeNormal();
			Out.AddFlatTriangle(Corners[i] * Radius, Corners[i + 1] * Radius, Corners[i + 2] * Radius, Normal);
		}
	}

	void BuildLens(FDaemonMeshData& Out, float Radius, float PolarMaxDeg, int32 Rings, int32 Sides)
	{
		Rings = FMath::Max(Rings, 1);
		Sides = FMath::Max(Sides, 3);
		const int32 Tip = Out.AddVertex(FVector(Radius, 0.f, 0.f), FVector::ForwardVector, FVector2D(0.5, 0.5));
		TArray<int32> Prev;
		for (int32 r = 1; r <= Rings; ++r)
		{
			const float Polar = FMath::DegreesToRadians(PolarMaxDeg * float(r) / float(Rings));
			TArray<int32> Ring;
			for (int32 s = 0; s < Sides; ++s)
			{
				const float Az = 2.f * PI * float(s) / float(Sides);
				const FVector N(FMath::Cos(Polar), FMath::Sin(Polar) * FMath::Cos(Az), FMath::Sin(Polar) * FMath::Sin(Az));
				Ring.Add(Out.AddVertex(N * Radius, N, FVector2D(0.5 + 0.5 * N.Y, 0.5 + 0.5 * N.Z)));
			}
			for (int32 s = 0; s < Sides; ++s)
			{
				const int32 S1 = (s + 1) % Sides;
				if (r == 1)
				{
					const FVector Mid = (Out.Vertices[Ring[s]] + Out.Vertices[Ring[S1]] + Out.Vertices[Tip]).GetSafeNormal();
					Out.AddTriangleFacing(Tip, Ring[s], Ring[S1], Mid);
				}
				else
				{
					const FVector Mid = (Out.Vertices[Prev[s]] + Out.Vertices[Ring[S1]]).GetSafeNormal();
					Out.AddQuadFacing(Prev[s], Prev[S1], Ring[S1], Ring[s], Mid);
				}
			}
			Prev = MoveTemp(Ring);
		}
	}

	void BuildSegmentedRing(FDaemonMeshData& Hull, FDaemonMeshData& Glow, float Radius, float RadialThickness,
		float AxialWidth, int32 Segments, float GapDeg, int32 StepsPerSegment)
	{
		Segments = FMath::Max(Segments, 1);
		StepsPerSegment = FMath::Max(StepsPerSegment, 1);
		const float SegmentDeg = 360.f / float(Segments);
		const float ArcDeg = FMath::Max(SegmentDeg - GapDeg, 1.f);
		const float RIn = Radius - RadialThickness * 0.5f;
		const float ROut = Radius + RadialThickness * 0.5f;
		const float HalfW = AxialWidth * 0.5f;

		auto Radial = [](float Deg) { const float A = FMath::DegreesToRadians(Deg); return FVector(0.f, FMath::Cos(A), FMath::Sin(A)); };

		for (int32 Seg = 0; Seg < Segments; ++Seg)
		{
			const float Start = SegmentDeg * float(Seg) + GapDeg * 0.5f;
			for (int32 k = 0; k < StepsPerSegment; ++k)
			{
				const float A0 = Start + ArcDeg * float(k) / float(StepsPerSegment);
				const float A1 = Start + ArcDeg * float(k + 1) / float(StepsPerSegment);
				const FVector D0 = Radial(A0), D1 = Radial(A1);
				const FVector Fx(HalfW, 0.f, 0.f);
				const FVector MidDir = (D0 + D1).GetSafeNormal();

				const FVector O0f = D0 * ROut + Fx, O0b = D0 * ROut - Fx, O1f = D1 * ROut + Fx, O1b = D1 * ROut - Fx;
				const FVector I0f = D0 * RIn + Fx, I0b = D0 * RIn - Fx, I1f = D1 * RIn + Fx, I1b = D1 * RIn - Fx;

				Hull.AddFlatQuad(O0f, O1f, O1b, O0b, MidDir);                 // outer
				Hull.AddFlatQuad(O0f, O1f, I1f, I0f, FVector::ForwardVector);  // front
				Hull.AddFlatQuad(O0b, O1b, I1b, I0b, -FVector::ForwardVector); // back
				Glow.AddFlatQuad(I0f, I1f, I1b, I0b, -MidDir);                 // inner light strip
			}
			// End caps.
			const float AEnd = Start + ArcDeg;
			for (int32 Cap = 0; Cap < 2; ++Cap)
			{
				const float A = Cap == 0 ? Start : AEnd;
				const FVector D = Radial(A);
				const FVector Tangent = FVector(0.f, -D.Z, D.Y) * (Cap == 0 ? -1.f : 1.f);
				const FVector Fx(HalfW, 0.f, 0.f);
				Hull.AddFlatQuad(D * ROut + Fx, D * ROut - Fx, D * RIn - Fx, D * RIn + Fx, Tangent);
			}
		}
	}

	namespace
	{
		void TubeFrame(TConstArrayView<FVector> Spine, int32 i, FVector& OutN, FVector& OutB)
		{
			const int32 Count = Spine.Num();
			const FVector Prev = Spine[FMath::Max(i - 1, 0)];
			const FVector Next = Spine[FMath::Min(i + 1, Count - 1)];
			const FVector T = (Next - Prev).GetSafeNormal();
			FVector Ref = FVector::UpVector;
			if (FMath::Abs(FVector::DotProduct(T, Ref)) > 0.95)
			{
				Ref = FVector::RightVector;
			}
			OutB = FVector::CrossProduct(T, Ref).GetSafeNormal();
			OutN = FVector::CrossProduct(OutB, T).GetSafeNormal();
		}

		void WriteTube(FDaemonMeshData& Out, TConstArrayView<FVector> Spine, TConstArrayView<float> Radii, int32 Sides, bool bCreate)
		{
			const int32 Count = Spine.Num();
			int32 V = 0;
			for (int32 i = 0; i < Count; ++i)
			{
				FVector N, B;
				TubeFrame(Spine, i, N, B);
				const float S = Count > 1 ? float(i) / float(Count - 1) : 0.f;
				const FLinearColor Mask(FMath::Lerp(0.12f, 1.f, S * S), 0.f, 0.f, 1.f);
				for (int32 s = 0; s < Sides; ++s)
				{
					const float A = 2.f * PI * float(s) / float(Sides);
					const FVector Dir = N * FMath::Cos(A) + B * FMath::Sin(A);
					const FVector P = Spine[i] + Dir * Radii[i];
					if (bCreate)
					{
						Out.AddVertex(P, Dir, FVector2D(float(s) / Sides, S), Mask);
					}
					else
					{
						Out.Vertices[V] = P;
						Out.Normals[V] = Dir;
						++V;
					}
				}
			}
			// Tip cap vertex.
			const FVector TipDir = (Spine[Count - 1] - Spine[FMath::Max(Count - 2, 0)]).GetSafeNormal();
			const FVector TipPos = Spine[Count - 1] + TipDir * Radii[Count - 1];
			if (bCreate)
			{
				Out.AddVertex(TipPos, TipDir, FVector2D(0.5, 1.0), FLinearColor(1.f, 0.f, 0.f, 1.f));
			}
			else
			{
				Out.Vertices[V] = TipPos;
				Out.Normals[V] = TipDir;
			}
		}
	}

	void BuildTube(FDaemonMeshData& Out, TConstArrayView<FVector> Spine, TConstArrayView<float> Radii, int32 Sides)
	{
		Out.Reset();
		const int32 Count = Spine.Num();
		if (Count < 2 || Radii.Num() != Count)
		{
			return;
		}
		Sides = FMath::Max(Sides, 3);
		WriteTube(Out, Spine, Radii, Sides, true);
		for (int32 i = 0; i + 1 < Count; ++i)
		{
			for (int32 s = 0; s < Sides; ++s)
			{
				const int32 S1 = (s + 1) % Sides;
				const int32 A = i * Sides + s, B = i * Sides + S1, C = (i + 1) * Sides + S1, D = (i + 1) * Sides + s;
				const FVector Outward = (Out.Normals[A] + Out.Normals[C]).GetSafeNormal();
				Out.AddQuadFacing(A, B, C, D, Outward);
			}
		}
		const int32 Tip = Out.Vertices.Num() - 1;
		const int32 Last = (Count - 1) * Sides;
		for (int32 s = 0; s < Sides; ++s)
		{
			Out.AddTriangleFacing(Last + s, Last + (s + 1) % Sides, Tip, Out.Normals[Tip]);
		}
	}

	void UpdateTube(FDaemonMeshData& InOut, TConstArrayView<FVector> Spine, TConstArrayView<float> Radii, int32 Sides)
	{
		const int32 Expected = Spine.Num() * FMath::Max(Sides, 3) + 1;
		if (InOut.Vertices.Num() != Expected || Radii.Num() != Spine.Num())
		{
			BuildTube(InOut, Spine, Radii, Sides);
			return;
		}
		WriteTube(InOut, Spine, Radii, FMath::Max(Sides, 3), false);
	}
}
