#pragma once

#include "CoreMinimal.h"
#include "Layout/Geometry.h"
#include "Rendering/RenderingCommon.h"
#include "Fonts/SlateFontInfo.h"
#include "Styling/WidgetStyle.h"

class FSlateWindowElementList;
struct FSlateBrush;

/**
 * Batched triangle list in DESIGN space, flushed as ONE Slate custom-verts draw element
 * (used for fills, gradients, vignettes and glitch bands - thousands of quads, one draw call).
 */
struct AOS_DK_API FAOSHudMesh
{
	TArray<FVector2f> Positions;
	TArray<FLinearColor> Colors;
	TArray<uint32> Indices;

	int32 AddVertex(const FVector2f& Position, const FLinearColor& Color);
	void AddTriangle(int32 A, int32 B, int32 C);
	void AddQuad(const FVector2f& Min, const FVector2f& Max, const FLinearColor& Color);
	void AddQuadGradientV(const FVector2f& Min, const FVector2f& Max, const FLinearColor& Top, const FLinearColor& Bottom);
	/** Convex polygon, triangle fan. */
	void AddConvex(TConstArrayView<FVector2f> Points, const FLinearColor& Color);
	void AddConvex(TConstArrayView<FVector2f> Points, TConstArrayView<FLinearColor> PointColors);
	/** Strip between two polylines with the same point count (closed loop if bClosed). */
	void AddBand(TConstArrayView<FVector2f> Outer, TConstArrayView<FVector2f> Inner,
		TConstArrayView<FLinearColor> OuterColors, TConstArrayView<FLinearColor> InnerColors, bool bClosed);
	bool IsEmpty() const { return Indices.Num() == 0; }
	void Reset();
};

/**
 * Immediate-mode vector painter for AOS_DK HUD elements (thin wrapper over FSlateDrawElement).
 * Every coordinate, thickness and font size is given in the element's DESIGN space and mapped
 * to local space with a uniform Scale, so the HUD stays crisp and proportional at any
 * resolution, aspect ratio or DPI. Fit mode: DesignSize is fitted (centred) into the slot.
 * Stretch mode: Scale follows the slot height, Extent() widens with the aspect ratio.
 */
struct AOS_DK_API FAOSHudPainter
{
	FAOSHudPainter(const FGeometry& InGeometry, FSlateWindowElementList& InElements, int32 InLayer,
		const FWidgetStyle& InStyle, const FVector2f& InDesignSize, bool bInStretch);

	const FGeometry& Geometry;
	FSlateWindowElementList& Elements;
	/** Every primitive takes its own layer (Slate batches per layer, so painter order == draw order). */
	mutable int32 Layer = 0;
	FLinearColor Tint = FLinearColor::White;
	FVector2f LocalSize = FVector2f::ZeroVector;
	FVector2f DesignSize = FVector2f(100.f, 100.f);
	float Scale = 1.f;
	FVector2f Origin = FVector2f::ZeroVector;

	bool IsValid() const { return LocalSize.X > 1.f && LocalSize.Y > 1.f && Scale > KINDA_SMALL_NUMBER; }

	/** Drawable size in design units (== DesignSize in fit mode). */
	FVector2f Extent() const { return Extent2D; }

	/** Design -> local. */
	FVector2f ToLocal(const FVector2f& Design) const { return Origin + Design * Scale; }
	float ToLocal(float DesignLength) const { return DesignLength * Scale; }

	// --- Primitives (design space) ----------------------------------------------------------------
	void Line(const FVector2f& A, const FVector2f& B, const FLinearColor& Color, float Thickness = 1.f) const;
	void Polyline(TConstArrayView<FVector2f> Points, const FLinearColor& Color, float Thickness = 1.f, bool bClosed = false) const;
	void Polyline(TConstArrayView<FVector2f> Points, TConstArrayView<FLinearColor> PointColors, float Thickness = 1.f) const;
	void FillConvex(TConstArrayView<FVector2f> Points, const FLinearColor& Color) const;
	void FillConvex(TConstArrayView<FVector2f> Points, TConstArrayView<FLinearColor> PointColors) const;
	void FillRect(const FVector2f& Min, const FVector2f& Max, const FLinearColor& Color) const;
	void StrokeRect(const FVector2f& Min, const FVector2f& Max, const FLinearColor& Color, float Thickness = 1.f) const;
	void FillCircle(const FVector2f& Center, float Radius, const FLinearColor& Color, int32 Segments = 18) const;
	void StrokeCircle(const FVector2f& Center, float Radius, const FLinearColor& Color, float Thickness = 1.f, int32 Segments = 32) const;
	void DrawMesh(const FAOSHudMesh& Mesh) const;

	// --- Text -------------------------------------------------------------------------------------
	/** Copy of Base with the size scaled from design points. */
	FSlateFontInfo MakeFont(const FSlateFontInfo& Base, float DesignPoints) const;
	/** Text size in DESIGN units. */
	FVector2f MeasureText(const FString& Text, const FSlateFontInfo& Base, float DesignPoints) const;
	/**
	 * Draws Text anchored at Pos: Align (0,0) = Pos is the top-left corner, (0.5,0.5) = centred,
	 * (1,0.5) = right-middle. Returns the text size in design units.
	 */
	FVector2f Text(const FString& Text, const FSlateFontInfo& Base, float DesignPoints, const FVector2f& Pos,
		const FVector2f& Align, const FLinearColor& Color) const;

	/** Text with a crisp Slate outline (OutlineSize in design units): legible over light and dark fills alike. */
	FVector2f TextOutlined(const FString& Text, const FSlateFontInfo& Base, float DesignPoints, const FVector2f& Pos,
		const FVector2f& Align, const FLinearColor& Color, const FLinearColor& OutlineColor, float OutlineSize) const;

	/** Bumps the layer (draw later = on top). */
	int32 NextLayer() const { return ++Layer; }

	static const FSlateBrush* GetWhiteBrush();

private:
	FColor ToVertexColor(const FLinearColor& Color) const;
	FLinearColor Apply(const FLinearColor& Color) const { return Color * Tint; }
	FVector2f Extent2D = FVector2f(100.f, 100.f);
};

/** Small deterministic helpers shared by the HUD (no RNG state: same input -> same output). */
namespace AOSHudMath
{
	/** 32-bit integer hash (lowbias32). */
	inline uint32 Hash(uint32 X)
	{
		X ^= X >> 16; X *= 0x7FEB352Du;
		X ^= X >> 15; X *= 0x846CA68Bu;
		X ^= X >> 16;
		return X;
	}
	/** Hash -> [0, 1). */
	inline float Hash01(uint32 X) { return float(Hash(X) & 0x00FFFFFFu) / float(0x01000000u); }
	/** Angle -> [0, 360). */
	inline float ClampDegrees(float Degrees)
	{
		const float Wrapped = FMath::Fmod(Degrees, 360.f);
		return Wrapped < 0.f ? Wrapped + 360.f : Wrapped;
	}
	/** Frame-rate independent exponential approach. */
	inline float Approach(float Current, float Target, float Rate, float Dt)
	{
		return Target + (Current - Target) * FMath::Exp(-Rate * Dt);
	}
	/** Convex polygon clipped to the half plane y >= LevelY (Sutherland-Hodgman, single edge). */
	AOS_DK_API void ClipConvexBelow(TConstArrayView<FVector2f> In, float LevelY, TArray<FVector2f>& Out);
	/** Inward offset of a convex polygon by Distance (either winding). */
	AOS_DK_API void InsetConvex(TConstArrayView<FVector2f> In, float Distance, TArray<FVector2f>& Out);
	/** Horizontal span of a convex polygon at height Y. Returns false if Y is outside. */
	AOS_DK_API bool ConvexSpanAtY(TConstArrayView<FVector2f> Poly, float Y, float& OutMinX, float& OutMaxX);
	/** Regular hexagon (flat-top) vertices. */
	AOS_DK_API void Hexagon(const FVector2f& Center, float Radius, TArray<FVector2f>& Out);

	/** Point on a circle; Degrees in screen space (0 = +X, 90 = down, 180 = left, 270 = up). */
	inline FVector2f Polar(const FVector2f& Center, float Radius, float Degrees)
	{
		const float A = FMath::DegreesToRadians(Degrees);
		return Center + FVector2f(FMath::Cos(A), FMath::Sin(A)) * Radius;
	}

	/**
	 * X of the LEFT half of a circle at height Y (the side faces of the canopy-corner gauges).
	 * Clamped to the circle's vertical extent, so it never returns NaN.
	 */
	inline float CircleLeftX(const FVector2f& Center, float Radius, float Y)
	{
		const float Dy = Y - Center.Y;
		return Center.X - FMath::Sqrt(FMath::Max(Radius * Radius - Dy * Dy, 0.f));
	}

	/** Flat-top regular hexagon whose walls are moved inwards by Distance (parallel walls): R - 2 d / sqrt(3). */
	inline float InsetHexagonRadius(float Radius, float Distance)
	{
		return FMath::Max(0.f, Radius - 2.f * Distance / 1.7320508f);
	}

	/**
	 * Horizontal slice [Y0, Y1] of a convex polygon. For a hexagon this is an isosceles trapezoid (or a
	 * hexagon piece across the middle row) whose ends are cut exactly along the walls.
	 */
	AOS_DK_API void HorizontalSlice(TConstArrayView<FVector2f> Convex, float Y0, float Y1, TArray<FVector2f>& Out);

	/** Rounded rectangle / pill as a convex polygon (CornerSegments per corner; radius clamped to the half size). */
	AOS_DK_API void RoundedRect(const FVector2f& Min, const FVector2f& Max, float CornerRadius, int32 CornerSegments, TArray<FVector2f>& Out);

	/** Convex polygon clipped to an axis-aligned half plane: keeps P[Axis] <= Value (bKeepLess) or >= Value. */
	AOS_DK_API void ClipConvexAxis(TConstArrayView<FVector2f> In, int32 Axis, float Value, bool bKeepLess, TArray<FVector2f>& Out);

	/**
	 * Convex polygon MINUS an axis-aligned rectangle (a clean rectangular aperture): appends up to four
	 * convex pieces (left / right / above / below the hole) to OutPieces. Exact edges, no stair-stepping.
	 */
	AOS_DK_API void SubtractRect(TConstArrayView<FVector2f> In, const FVector2f& HoleMin, const FVector2f& HoleMax, TArray<TArray<FVector2f>>& OutPieces);

	/** Parts of segment AB outside an axis-aligned rectangle (0, 1 or 2 sub-segments, appended as pairs). */
	AOS_DK_API void SegmentOutsideRect(const FVector2f& A, const FVector2f& B, const FVector2f& HoleMin, const FVector2f& HoleMax, TArray<FVector2f>& OutPairs);
}
