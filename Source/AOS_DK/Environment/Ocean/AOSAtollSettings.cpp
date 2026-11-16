#include "AOS_DK/Environment/Ocean/AOSAtollSettings.h"

float UAOSAtollSettings::WaveScaleAt(double X, double Y) const
{
	const double Dist = FMath::Sqrt(FMath::Square(X - Center.X) + FMath::Square(Y - Center.Y));
	return FMath::SmoothStep(RCalm, FMath::Max(RFull, RCalm + 1.f), float(Dist));
}

float AOSAtoll::WaveScale(const FVector& WorldPosition)
{
	return UAOSAtollSettings::Get()->WaveScaleAt(WorldPosition.X, WorldPosition.Y);
}
