#include "AOSHudPainter.h"

#include "Rendering/DrawElements.h"
#include "Rendering/SlateRenderer.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Styling/CoreStyle.h"

// ------------------------------------------------------------------------------------------- mesh
int32 FAOSHudMesh::AddVertex(const FVector2f& Position, const FLinearColor& Color)
{
	Colors.Add(Color);
	return Positions.Add(Position);
}

void FAOSHudMesh::AddTriangle(int32 A, int32 B, int32 C)
{
	Indices.Add(uint32(A));
	Indices.Add(uint32(B));
	Indices.Add(uint32(C));
}

void FAOSHudMesh::AddQuad(const FVector2f& Min, const FVector2f& Max, const FLinearColor& Color)
{
	AddQuadGradientV(Min, Max, Color, Color);
}

void FAOSHudMesh::AddQuadGradientV(const FVector2f& Min, const FVector2f& Max, const FLinearColor& Top, const FLinearColor& Bottom)
{
	const int32 I0 = AddVertex(FVector2f(Min.X, Min.Y), Top);
	const int32 I1 = AddVertex(FVector2f(Max.X, Min.Y), Top);
	const int32 I2 = AddVertex(FVector2f(Max.X, Max.Y), Bottom);
	const int32 I3 = AddVertex(FVector2f(Min.X, Max.Y), Bottom);
	AddTriangle(I0, I1, I2);
	AddTriangle(I0, I2, I3);
}

void FAOSHudMesh::AddConvex(TConstArrayView<FVector2f> Points, const FLinearColor& Color)
{
	if (Points.Num() < 3)
	{
		return;
	}
	const int32 Base = Positions.Num();
	for (const FVector2f& P : Points)
	{
		AddVertex(P, Color);
	}
	for (int32 i = 1; i + 1 < Points.Num(); ++i)
	{
		AddTriangle(Base, Base + i, Base + i + 1);
	}
}

void FAOSHudMesh::AddConvex(TConstArrayView<FVector2f> Points, TConstArrayView<FLinearColor> PointColors)
{
	if (Points.Num() < 3 || PointColors.Num() != Points.Num())
	{
		return;
	}
	const int32 Base = Positions.Num();
	for (int32 i = 0; i < Points.Num(); ++i)
	{
		AddVertex(Points[i], PointColors[i]);
	}
	for (int32 i = 1; i + 1 < Points.Num(); ++i)
	{
		AddTriangle(Base, Base + i, Base + i + 1);
	}
}

void FAOSHudMesh::AddBand(TConstArrayView<FVector2f> Outer, TConstArrayView<FVector2f> Inner,
	TConstArrayView<FLinearColor> OuterColors, TConstArrayView<FLinearColor> InnerColors, bool bClosed)
{
	const int32 N = Outer.Num();
	if (N < 2 || Inner.Num() != N || OuterColors.Num() != N || InnerColors.Num() != N)
	{
		return;
	}
	const int32 Base = Positions.Num();
	for (int32 i = 0; i < N; ++i)
	{
		AddVertex(Outer[i], OuterColors[i]);
		AddVertex(Inner[i], InnerColors[i]);
	}
	const int32 Segments = bClosed ? N : N - 1;
	for (int32 i = 0; i < Segments; ++i)
	{
		const int32 j = (i + 1) % N;
		const int32 O0 = Base + i * 2, I0 = O0 + 1;
		const int32 O1 = Base + j * 2, I1 = O1 + 1;
		AddTriangle(O0, O1, I1);
		AddTriangle(O0, I1, I0);
	}
}

void FAOSHudMesh::Reset()
{
	Positions.Reset();
	Colors.Reset();
	Indices.Reset();
}

// ---------------------------------------------------------------------------------------- painter
FAOSHudPainter::FAOSHudPainter(const FGeometry& InGeometry, FSlateWindowElementList& InElements, int32 InLayer,
	const FWidgetStyle& InStyle, const FVector2f& InDesignSize, bool bInStretch)
	: Geometry(InGeometry)
	, Elements(InElements)
	, Layer(InLayer)
	, Tint(InStyle.GetColorAndOpacityTint())
	, DesignSize(InDesignSize)
{
	LocalSize = FVector2f(InGeometry.GetLocalSize());
	const FVector2f SafeDesign(FMath::Max(DesignSize.X, 1.f), FMath::Max(DesignSize.Y, 1.f));
	if (bInStretch)
	{
		// Stretch: thickness/fonts follow the height (DPI-normalised layout units), width = aspect.
		Scale = LocalSize.Y / SafeDesign.Y;
		Origin = FVector2f::ZeroVector;
		Extent2D = Scale > KINDA_SMALL_NUMBER ? LocalSize / Scale : SafeDesign;
	}
	else
	{
		Scale = FMath::Min(LocalSize.X / SafeDesign.X, LocalSize.Y / SafeDesign.Y);
		Origin = (LocalSize - SafeDesign * Scale) * 0.5f;
		Extent2D = SafeDesign;
	}
}

const FSlateBrush* FAOSHudPainter::GetWhiteBrush()
{
	return FCoreStyle::Get().GetBrush(TEXT("GenericWhiteBox"));
}

FColor FAOSHudPainter::ToVertexColor(const FLinearColor& Color) const
{
	return Apply(Color).ToFColorSRGB();
}

void FAOSHudPainter::Line(const FVector2f& A, const FVector2f& B, const FLinearColor& Color, float Thickness) const
{
	TArray<FVector2f> Points;
	Points.Add(ToLocal(A));
	Points.Add(ToLocal(B));
	FSlateDrawElement::MakeLines(Elements, NextLayer(), Geometry.ToPaintGeometry(), MoveTemp(Points),
		ESlateDrawEffect::None, Apply(Color), true, FMath::Max(ToLocal(Thickness), 0.75f));
}

void FAOSHudPainter::Polyline(TConstArrayView<FVector2f> InPoints, const FLinearColor& Color, float Thickness, bool bClosed) const
{
	if (InPoints.Num() < 2)
	{
		return;
	}
	TArray<FVector2f> Points;
	Points.Reserve(InPoints.Num() + 1);
	for (const FVector2f& P : InPoints)
	{
		Points.Add(ToLocal(P));
	}
	if (bClosed)
	{
		const FVector2f First = Points[0]; // copy first: Add() must not alias its own storage
		Points.Add(First);
	}
	FSlateDrawElement::MakeLines(Elements, NextLayer(), Geometry.ToPaintGeometry(), MoveTemp(Points),
		ESlateDrawEffect::None, Apply(Color), true, FMath::Max(ToLocal(Thickness), 0.75f));
}

void FAOSHudPainter::Polyline(TConstArrayView<FVector2f> InPoints, TConstArrayView<FLinearColor> PointColors, float Thickness) const
{
	if (InPoints.Num() < 2 || PointColors.Num() != InPoints.Num())
	{
		return;
	}
	TArray<FVector2f> Points;
	TArray<FLinearColor> Colors;
	Points.Reserve(InPoints.Num());
	Colors.Reserve(InPoints.Num());
	for (int32 i = 0; i < InPoints.Num(); ++i)
	{
		Points.Add(ToLocal(InPoints[i]));
		Colors.Add(Apply(PointColors[i]));
	}
	FSlateDrawElement::MakeLines(Elements, NextLayer(), Geometry.ToPaintGeometry(), MoveTemp(Points), MoveTemp(Colors),
		ESlateDrawEffect::None, FLinearColor::White, true, FMath::Max(ToLocal(Thickness), 0.75f));
}

void FAOSHudPainter::DrawMesh(const FAOSHudMesh& Mesh) const
{
	if (Mesh.IsEmpty() || !FSlateApplication::IsInitialized())
	{
		return;
	}
	const FSlateBrush* Brush = GetWhiteBrush();
	auto Renderer = FSlateApplication::Get().GetRenderer();
	if (!Brush || !Renderer)
	{
		return;
	}
	const FSlateResourceHandle Handle = Renderer->GetResourceHandle(*Brush);
	const FSlateRenderTransform& RenderTransform = Geometry.GetAccumulatedRenderTransform();

	TArray<FSlateVertex> Vertices;
	Vertices.Reserve(Mesh.Positions.Num());
	for (int32 i = 0; i < Mesh.Positions.Num(); ++i)
	{
		Vertices.Add(FSlateVertex::Make(RenderTransform, ToLocal(Mesh.Positions[i]), FVector2f(0.5f, 0.5f), ToVertexColor(Mesh.Colors[i])));
	}
	TArray<SlateIndex> Indices;
	Indices.Reserve(Mesh.Indices.Num());
	for (const uint32 Index : Mesh.Indices)
	{
		Indices.Add(SlateIndex(Index));
	}
	FSlateDrawElement::MakeCustomVerts(Elements, NextLayer(), Handle, Vertices, Indices, nullptr, 0, 0);
}

void FAOSHudPainter::FillConvex(TConstArrayView<FVector2f> Points, const FLinearColor& Color) const
{
	FAOSHudMesh Mesh;
	Mesh.AddConvex(Points, Color);
	DrawMesh(Mesh);
}

void FAOSHudPainter::FillConvex(TConstArrayView<FVector2f> Points, TConstArrayView<FLinearColor> PointColors) const
{
	FAOSHudMesh Mesh;
	Mesh.AddConvex(Points, PointColors);
	DrawMesh(Mesh);
}

void FAOSHudPainter::FillRect(const FVector2f& Min, const FVector2f& Max, const FLinearColor& Color) const
{
	FAOSHudMesh Mesh;
	Mesh.AddQuad(Min, Max, Color);
	DrawMesh(Mesh);
}

void FAOSHudPainter::StrokeRect(const FVector2f& Min, const FVector2f& Max, const FLinearColor& Color, float Thickness) const
{
	const FVector2f Points[4] = { Min, FVector2f(Max.X, Min.Y), Max, FVector2f(Min.X, Max.Y) };
	Polyline(MakeArrayView(Points, 4), Color, Thickness, true);
}

void FAOSHudPainter::FillCircle(const FVector2f& Center, float Radius, const FLinearColor& Color, int32 Segments) const
{
	TArray<FVector2f> Points;
	Segments = FMath::Max(Segments, 6);
	Points.Reserve(Segments);
	for (int32 i = 0; i < Segments; ++i)
	{
		const float A = 2.f * PI * float(i) / float(Segments);
		Points.Add(Center + FVector2f(FMath::Cos(A), FMath::Sin(A)) * Radius);
	}
	FillConvex(Points, Color);
}

void FAOSHudPainter::StrokeCircle(const FVector2f& Center, float Radius, const FLinearColor& Color, float Thickness, int32 Segments) const
{
	TArray<FVector2f> Points;
	Segments = FMath::Max(Segments, 6);
	Points.Reserve(Segments);
	for (int32 i = 0; i < Segments; ++i)
	{
		const float A = 2.f * PI * float(i) / float(Segments);
		Points.Add(Center + FVector2f(FMath::Cos(A), FMath::Sin(A)) * Radius);
	}
	Polyline(Points, Color, Thickness, true);
}

FSlateFontInfo FAOSHudPainter::MakeFont(const FSlateFontInfo& Base, float DesignPoints) const
{
	FSlateFontInfo Font = Base;
	Font.Size = FMath::Max(1.f, DesignPoints * Scale);
	return Font;
}

FVector2f FAOSHudPainter::MeasureText(const FString& InText, const FSlateFontInfo& Base, float DesignPoints) const
{
	if (InText.IsEmpty() || !FSlateApplication::IsInitialized() || Scale <= KINDA_SMALL_NUMBER)
	{
		return FVector2f::ZeroVector;
	}
	const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
	const FVector2D Size = Measure->Measure(InText, MakeFont(Base, DesignPoints));
	return FVector2f(Size) / Scale;
}

FVector2f FAOSHudPainter::Text(const FString& InText, const FSlateFontInfo& Base, float DesignPoints, const FVector2f& Pos,
	const FVector2f& Align, const FLinearColor& Color) const
{
	if (InText.IsEmpty() || !FSlateApplication::IsInitialized() || Scale <= KINDA_SMALL_NUMBER)
	{
		return FVector2f::ZeroVector;
	}
	const FSlateFontInfo Font = MakeFont(Base, DesignPoints);
	const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
	const FVector2f LocalTextSize(FVector2D(Measure->Measure(InText, Font)));
	const FVector2f TopLeft = ToLocal(Pos) - LocalTextSize * Align;
	FSlateDrawElement::MakeText(Elements, NextLayer(), Geometry.ToPaintGeometry(LocalTextSize, FSlateLayoutTransform(TopLeft)),
		InText, Font, ESlateDrawEffect::None, Apply(Color));
	return LocalTextSize / Scale;
}

FVector2f FAOSHudPainter::TextOutlined(const FString& InText, const FSlateFontInfo& Base, float DesignPoints, const FVector2f& Pos,
	const FVector2f& Align, const FLinearColor& Color, const FLinearColor& OutlineColor, float OutlineSize) const
{
	if (InText.IsEmpty() || !FSlateApplication::IsInitialized() || Scale <= KINDA_SMALL_NUMBER)
	{
		return FVector2f::ZeroVector;
	}
	FSlateFontInfo Font = MakeFont(Base, DesignPoints);
	Font.OutlineSettings.OutlineSize = FMath::Max(1, FMath::RoundToInt(OutlineSize * Scale));
	Font.OutlineSettings.OutlineColor = Apply(OutlineColor);
	const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
	const FVector2f LocalTextSize(FVector2D(Measure->Measure(InText, Font)));
	const FVector2f TopLeft = ToLocal(Pos) - LocalTextSize * Align;
	FSlateDrawElement::MakeText(Elements, NextLayer(), Geometry.ToPaintGeometry(LocalTextSize, FSlateLayoutTransform(TopLeft)),
		InText, Font, ESlateDrawEffect::None, Apply(Color));
	return LocalTextSize / Scale;
}

// ------------------------------------------------------------------------------------------- math
namespace AOSHudMath
{
	void ClipConvexBelow(TConstArrayView<FVector2f> In, float LevelY, TArray<FVector2f>& Out)
	{
		Out.Reset();
		const int32 N = In.Num();
		for (int32 i = 0; i < N; ++i)
		{
			const FVector2f& A = In[i];
			const FVector2f& B = In[(i + 1) % N];
			const bool bAIn = A.Y >= LevelY;
			const bool bBIn = B.Y >= LevelY;
			if (bAIn)
			{
				Out.Add(A);
			}
			if (bAIn != bBIn)
			{
				const float T = (LevelY - A.Y) / (B.Y - A.Y);
				Out.Add(FVector2f(FMath::Lerp(A.X, B.X, T), LevelY));
			}
		}
	}

	void InsetConvex(TConstArrayView<FVector2f> In, float Distance, TArray<FVector2f>& Out)
	{
		Out.Reset();
		const int32 N = In.Num();
		if (N < 3)
		{
			Out.Append(In.GetData(), N);
			return;
		}
		FVector2f Centroid = FVector2f::ZeroVector;
		for (const FVector2f& P : In)
		{
			Centroid += P;
		}
		Centroid /= float(N);

		// Offset every edge towards the centroid, then intersect neighbouring offset edges.
		TArray<FVector2f> LinePoint, LineDir;
		LinePoint.SetNum(N);
		LineDir.SetNum(N);
		for (int32 i = 0; i < N; ++i)
		{
			const FVector2f A = In[i];
			const FVector2f B = In[(i + 1) % N];
			const FVector2f Dir = (B - A).GetSafeNormal();
			FVector2f Normal(-Dir.Y, Dir.X);
			if (FVector2f::DotProduct(Centroid - A, Normal) < 0.f)
			{
				Normal = -Normal;
			}
			LinePoint[i] = A + Normal * Distance;
			LineDir[i] = Dir;
		}
		for (int32 i = 0; i < N; ++i)
		{
			const int32 Prev = (i + N - 1) % N;
			const FVector2f P1 = LinePoint[Prev], D1 = LineDir[Prev];
			const FVector2f P2 = LinePoint[i], D2 = LineDir[i];
			const float Cross = D1.X * D2.Y - D1.Y * D2.X;
			if (FMath::Abs(Cross) < 1e-5f)
			{
				Out.Add(P2);
				continue;
			}
			const FVector2f Delta = P2 - P1;
			const float T = (Delta.X * D2.Y - Delta.Y * D2.X) / Cross;
			Out.Add(P1 + D1 * T);
		}
	}

	bool ConvexSpanAtY(TConstArrayView<FVector2f> Poly, float Y, float& OutMinX, float& OutMaxX)
	{
		OutMinX = TNumericLimits<float>::Max();
		OutMaxX = -TNumericLimits<float>::Max();
		const int32 N = Poly.Num();
		for (int32 i = 0; i < N; ++i)
		{
			const FVector2f& A = Poly[i];
			const FVector2f& B = Poly[(i + 1) % N];
			if ((Y < FMath::Min(A.Y, B.Y)) || (Y > FMath::Max(A.Y, B.Y)))
			{
				continue;
			}
			const float Dy = B.Y - A.Y;
			if (FMath::Abs(Dy) < 1e-5f)
			{
				OutMinX = FMath::Min(OutMinX, FMath::Min(A.X, B.X));
				OutMaxX = FMath::Max(OutMaxX, FMath::Max(A.X, B.X));
				continue;
			}
			const float X = FMath::Lerp(A.X, B.X, (Y - A.Y) / Dy);
			OutMinX = FMath::Min(OutMinX, X);
			OutMaxX = FMath::Max(OutMaxX, X);
		}
		return OutMaxX >= OutMinX;
	}

	void Hexagon(const FVector2f& Center, float Radius, TArray<FVector2f>& Out)
	{
		Out.Reset();
		for (int32 i = 0; i < 6; ++i)
		{
			const float A = FMath::DegreesToRadians(60.f * float(i));
			Out.Add(Center + FVector2f(FMath::Cos(A), FMath::Sin(A)) * Radius);
		}
	}

	void ClipConvexAxis(TConstArrayView<FVector2f> In, int32 Axis, float Value, bool bKeepLess, TArray<FVector2f>& Out)
	{
		Out.Reset();
		const int32 N = In.Num();
		auto Coord = [Axis](const FVector2f& P) { return Axis == 0 ? P.X : P.Y; };
		auto Inside = [&](const FVector2f& P) { return bKeepLess ? Coord(P) <= Value : Coord(P) >= Value; };
		for (int32 i = 0; i < N; ++i)
		{
			const FVector2f& A = In[i];
			const FVector2f& B = In[(i + 1) % N];
			const bool bAIn = Inside(A);
			if (bAIn)
			{
				Out.Add(A);
			}
			if (bAIn != Inside(B))
			{
				const float T = (Value - Coord(A)) / (Coord(B) - Coord(A));
				Out.Add(FMath::Lerp(A, B, T));
			}
		}
	}

	void HorizontalSlice(TConstArrayView<FVector2f> Convex, float Y0, float Y1, TArray<FVector2f>& Out)
	{
		TArray<FVector2f> Upper;
		ClipConvexAxis(Convex, 1, FMath::Min(Y0, Y1), false, Upper);
		ClipConvexAxis(Upper, 1, FMath::Max(Y0, Y1), true, Out);
	}

	void RoundedRect(const FVector2f& Min, const FVector2f& Max, float CornerRadius, int32 CornerSegments, TArray<FVector2f>& Out)
	{
		Out.Reset();
		const float R = FMath::Clamp(CornerRadius, 0.f, 0.5f * FMath::Min(Max.X - Min.X, Max.Y - Min.Y));
		const int32 Segments = FMath::Max(CornerSegments, 1);
		// Corner centres clockwise in screen space (y down): top-left, top-right, bottom-right, bottom-left.
		const FVector2f Centres[4] =
		{
			FVector2f(Min.X + R, Min.Y + R), FVector2f(Max.X - R, Min.Y + R), FVector2f(Max.X - R, Max.Y - R), FVector2f(Min.X + R, Max.Y - R)
		};
		const float StartDeg[4] = { 180.f, 270.f, 0.f, 90.f };
		for (int32 Corner = 0; Corner < 4; ++Corner)
		{
			for (int32 i = 0; i <= Segments; ++i)
			{
				Out.Add(Polar(Centres[Corner], R, StartDeg[Corner] + 90.f * float(i) / float(Segments)));
			}
		}
	}

	void SubtractRect(TConstArrayView<FVector2f> In, const FVector2f& HoleMin, const FVector2f& HoleMax, TArray<TArray<FVector2f>>& OutPieces)
	{
		if (In.Num() < 3)
		{
			return;
		}
		FVector2f BoundsMin(TNumericLimits<float>::Max()), BoundsMax(-TNumericLimits<float>::Max());
		for (const FVector2f& P : In)
		{
			BoundsMin.X = FMath::Min(BoundsMin.X, P.X);
			BoundsMin.Y = FMath::Min(BoundsMin.Y, P.Y);
			BoundsMax.X = FMath::Max(BoundsMax.X, P.X);
			BoundsMax.Y = FMath::Max(BoundsMax.Y, P.Y);
		}
		if (BoundsMax.X <= HoleMin.X || BoundsMin.X >= HoleMax.X || BoundsMax.Y <= HoleMin.Y || BoundsMin.Y >= HoleMax.Y)
		{
			OutPieces.Emplace(In.GetData(), In.Num()); // untouched
			return;
		}
		auto Keep = [&OutPieces](TArray<FVector2f>& Piece)
		{
			if (Piece.Num() < 3)
			{
				return;
			}
			float Area2 = 0.f;
			for (int32 i = 0; i < Piece.Num(); ++i)
			{
				const FVector2f& A = Piece[i];
				const FVector2f& B = Piece[(i + 1) % Piece.Num()];
				Area2 += A.X * B.Y - B.X * A.Y;
			}
			if (FMath::Abs(Area2) > 1e-3f)
			{
				OutPieces.Add(MoveTemp(Piece));
			}
		};
		TArray<FVector2f> Piece, Middle, Tmp;
		ClipConvexAxis(In, 0, HoleMin.X, true, Piece);   Keep(Piece);   // left of the hole
		ClipConvexAxis(In, 0, HoleMax.X, false, Piece);  Keep(Piece);   // right of the hole
		ClipConvexAxis(In, 0, HoleMin.X, false, Tmp);                   // vertical slab of the hole
		ClipConvexAxis(Tmp, 0, HoleMax.X, true, Middle);
		ClipConvexAxis(Middle, 1, HoleMin.Y, true, Piece);  Keep(Piece); // above
		ClipConvexAxis(Middle, 1, HoleMax.Y, false, Piece); Keep(Piece); // below
	}

	void SegmentOutsideRect(const FVector2f& A, const FVector2f& B, const FVector2f& HoleMin, const FVector2f& HoleMax, TArray<FVector2f>& OutPairs)
	{
		// Liang-Barsky: parametric interval [T0, T1] of AB inside the rectangle.
		const FVector2f D = B - A;
		float T0 = 0.f, T1 = 1.f;
		const float P[4] = { -D.X, D.X, -D.Y, D.Y };
		const float Q[4] = { A.X - HoleMin.X, HoleMax.X - A.X, A.Y - HoleMin.Y, HoleMax.Y - A.Y };
		bool bInside = true;
		for (int32 i = 0; i < 4 && bInside; ++i)
		{
			if (FMath::Abs(P[i]) < 1e-6f)
			{
				bInside = Q[i] >= 0.f;
				continue;
			}
			const float T = Q[i] / P[i];
			if (P[i] < 0.f) { T0 = FMath::Max(T0, T); }
			else            { T1 = FMath::Min(T1, T); }
			bInside = T0 < T1;
		}
		if (!bInside)
		{
			OutPairs.Add(A);
			OutPairs.Add(B);
			return;
		}
		if (T0 > 1e-4f)
		{
			OutPairs.Add(A);
			OutPairs.Add(A + D * T0);
		}
		if (T1 < 1.f - 1e-4f)
		{
			OutPairs.Add(A + D * T1);
			OutPairs.Add(B);
		}
	}
}
