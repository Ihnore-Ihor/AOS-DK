# -*- coding: utf-8 -*-
"""
AOS-DK | Генератор звіту до лабораторної роботи № 6 «Реалізація ігрових анімацій» (варіант № 10 «Підводний світ»).

Движок верстки (поля 25/10/20/20 мм, Times New Roman 14, інтервал 1,5, абзацний відступ 1,25 см, рамки лістингів
Courier New 10, таблиці, формули, колонтитул з номером сторінки) – без змін із Tools/generate_lab_report.py
(клас Report, як і в Tools/generate_lab5_report.py). Тут перевизначено змінні поля титульного аркуша та тіло звіту.
Титульний аркуш береться з Docs/Templates/Шаблон_звіту_ПРІ_2026.docx.

Джерела даних: Docs/AOS_Lab6_Animations_Specification_EN.md, Docs/Lab6/*.md, claude/AOS_Lab6_RainShadowFix_Report,
claude/AOS_Lab6_ShadowMoonFix_Report, Saved/Lab6_Verify/*.json, Saved/Lab6_Posture_PIE.json, Saved/Lab6_*_Verify/;
фрагменти коду – з Source/AOS_DK/ та Tools/max_build_SK_WindGen.py. Усі скриншоти реальні (PIE та 3ds Max).

Запуск:  python Tools/generate_lab6_report.py [--root <AOS_DK>] [--template <.docx>] [--out <.docx>]
Результат: Docs/Звіт_ЛР6_Анімації_Ігор_Брайченко.docx
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_lab_report as base                       # noqa: E402  (движок верстки)

from docx.enum.text import WD_ALIGN_PARAGRAPH            # noqa: E402
from docx.shared import Cm                               # noqa: E402
from PIL import Image, ImageDraw, ImageFont              # noqa: E402

# =====================================================================================================================
# 1. Метадані (підміна констант движка до створення документа)
# =====================================================================================================================
TARGET_REL = Path("Docs") / "Звіт_ЛР6_Анімації_Ігор_Брайченко.docx"
base.LAB_NUMBER = 6
base.TOPIC = "Реалізація ігрових анімацій"
base.GOAL = ("Навчитися створювати ігрові анімації: покадрові, процедурні та керовані з коду для зброї персонажів, "
             "анімувати об’єкти сцени засобами 3D-моделювання й Unreal Engine та налаштовувати природні явища гри")
base.TARGET_REL = TARGET_REL

C = WD_ALIGN_PARAGRAPH.CENTER

# =====================================================================================================================
# 2. Допоміжні засоби для рисунків (композиції зі справжніх скриншотів)
# =====================================================================================================================
FONT_CANDIDATES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
                   "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]


def _font(size):
    for p in FONT_CANDIDATES:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _panel(path, width, crop=None):
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def compose(paths, out, *, cols=1, width=1600, crops=None, labels=None, gap=12):
    """Склеює кадри в сітку cols стовпців; labels – літери (а), (б) … у кутку кожного кадру."""
    panels = [_panel(p, width, (crops or [None] * len(paths))[i]) for i, p in enumerate(paths)]
    rows = (len(panels) + cols - 1) // cols
    ph = max(p.height for p in panels)
    sheet = Image.new("RGB", (cols * width + (cols - 1) * gap, rows * ph + (rows - 1) * gap), (255, 255, 255))
    dr = ImageDraw.Draw(sheet)
    fnt = _font(max(18, width // 22))
    for i, pn in enumerate(panels):
        x, y = (i % cols) * (width + gap), (i // cols) * (ph + gap)
        sheet.paste(pn, (x, y))
        if labels:
            t = labels[i]
            w = dr.textlength(t, font=fnt)
            dr.rectangle((x + 8, y + 8, x + 8 + w + 16, y + 8 + fnt.size + 12), fill=(255, 255, 255))
            dr.text((x + 16, y + 12), t, fill=(0, 0, 0), font=fnt)
    if sheet.width > 2000:
        sheet = sheet.resize((2000, round(sheet.height * 2000 / sheet.width)), Image.LANCZOS)
    sheet.save(out, "JPEG", quality=88)
    return out


# =====================================================================================================================
# 3. Зміст
# =====================================================================================================================
THEORY = [
    "У комп’ютерних іграх розрізняють кілька способів задання руху. Скелетна (покадрова) анімація зберігає "
    "ключові кадри кісток у ресурсі UAnimSequence, який записано для конкретного скелета USkeleton з "
    "фіксованою частотою вибірки (30 кадрів на секунду); під час гри рушій знаходить позу для заданого часу "
    "відтворення й інтерполює сусідні ключі. Такий кліп створюють у DCC-пакеті, наприклад у 3ds Max, "
    "експортують у FBX і імпортують у Unreal Engine. Процедурна анімація, навпаки, не містить збережених ключів: "
    "поза обчислюється кожного кадру за станом гри (відстань до цілі, швидкість вітру, прогрес перезарядки), "
    "як-от обернена кінематика ніг або зв’язок «кут нахилу – функція часу». На практиці обидва підходи "
    "поєднують: кліп задає характер руху, а код змінює його темп, фазу та пропорції.",

    "Центральним класом скелетної анімації в Unreal Engine 5 є UAnimInstance, який належить компоненту "
    "USkeletalMeshComponent і щокадрово оновлює змінні (NativeUpdateAnimation) у потоці гри. Обчислення пози "
    "виконує робочий потік через структуру FAnimInstanceProxy: проксі копіює потрібні змінні у PreUpdate, "
    "а в Evaluate формує FPoseContext, тому логіка пози не блокує основний потік. Граф анімації (AnimGraph) "
    "складається з вузлів: Sequence Player відтворює кліп із заданою швидкістю, Sequence Evaluator бере позу "
    "в явно вказаний момент часу (корисно, коли час визначає не годинник, а ігровий параметр, наприклад ступінь "
    "складання лопатей), Layered Blend per Bone накладає одну позу на іншу лише для гілки кісток (Branch Filter, "
    "глибина змішування), а Blend змішує два потоки за ваговим коефіцієнтом. Ваговий коефіцієнт для обертань "
    "обчислюється як сферична інтерполяція кватерніонів, що дає постійну кутову швидкість між позами A та B",

]
THEORY_AFTER_SLERP = (
    "де Ω – кут між кватерніонами q_{A} і q_{B}, а α ∈ [0, 1] – вага. Саме так у формулі (1) поєднуються кліпи "
    "обертання, розгойдування та складання лопатей вітрогенератора, а в Evaluate власного проксі змішування "
    "виконано вручну для кожної кістки.")
THEORY2 = [
    "Окрім скелетних анімацій, у рушії широко застосовують анімацію компонентів і таймлайнів. Компонент "
    "URotatingMovementComponent обертає частину актора з заданою швидкістю без жодної анімаційної послідовності; "
    "Timeline (UTimelineComponent у C++ або вузол Timeline у Blueprint) відтворює криві UCurveFloat, якими "
    "керують інтенсивністю світла чи нахилом; матеріальна анімація обчислюється на графічному процесорі за "
    "вузлами Time, Panner та World Position Offset. Для детермінованих, заздалегідь поставлених рухів "
    "призначено Level Sequencer: ресурс ULevelSequence містить доріжки Transform, подій та параметрів, а "
    "актор ALevelSequenceActor відтворює їх за налаштуваннями Auto Play, Loop та Restore State. Секвенсор "
    "зручний, коли рух задано часом і має фіксовану тривалість (проліт катера по колу), тоді як код і таймлайни "
    "ліпше підходять для реактивної поведінки, що залежить від стану гри (маяк вмикається вночі та у шторм).",

    "Динамічне освітлення й атмосфера в Unreal Engine 5 складаються з кількох взаємопов’язаних актор-компонентів. "
    "DirectionalLight із прапорцем Atmosphere Sun Light та індексом 0 є Сонцем, а другий DirectionalLight з "
    "індексом 1 – Місяцем; кутовий розмір диска задає LightSourceAngle. SkyAtmosphere розраховує розсіювання "
    "Релея та Мі, SkyLight із Real Time Capture переносить кольори неба в навколишнє освітлення, "
    "VolumetricCloud відтворює хмари матеріалом з параметрами покриття та густини, а ExponentialHeightFog додає "
    "туман. Для зміни дня і ночі достатньо обертати світила за законами небесної механіки: висота Сонця h над "
    "горизонтом на широті φ за схилення δ залежить від годинного кута H = 15°·(t − 12), де t – час доби в годинах",
]
THEORY2_FORMULA_TAIL = (
    "Глобальні скалярні величини (ніч, вологість, вітер, шторм) зручно передавати матеріалам через Material "
    "Parameter Collection (MPC): один записувач оновлює колекцію, а всі матеріали Атолу читають її без "
    "додаткових посилань. Автоекспозиція камери, яку Epic розраховує за середньою яскравістю кадру, при "
    "цьому треба обмежувати ефектом Post Process, інакше місячна ніч автоматично підсвітиться до денної.")
THEORY3 = (
    "Для погодних ефектів застосовують Niagara – систему частинок, яка працює на GPU. Ефект складається з "
    "емітерів (тут: смуги дощу й бризки на поверхні), параметрів користувача User.* (інтенсивність дощу, "
    "висота води), які C++ задає під час гри через SetVariableFloat, та рендерерів спрайтів, орієнтованих "
    "вздовж швидкості. Матеріал частинки додатково переміщує вершини (World Position Offset), тому поле "
    "дощу можна обгортати навколо камери без створення нових частинок. Дощ повинен зникати під дахами й під "
    "водою, тому використовують карту висот дахів і примусову деактивацію під час занурення камери. "
    "Перемикання станів погоди й пози зброї реалізують скінченним автоматом із гістерезисом: порогові "
    "значення входу й виходу відрізняються, щоб стан не мерехтів при коливаннях вимірюваної величини.")

TASK_INTRO = "Відповідно до методичних вказівок до лабораторної роботи необхідно виконати такі завдання:"
TASK_ITEMS = [
    ("1.", "Створити анімацію перезарядки зброї для головного персонажа: опускання зброї вниз перед перезарядкою, "
           "вкладання набоїв, підняття зброї у вихідне положення (або ідентичну по складності анімацію для інших "
           "видів зброї).", []),
    ("2.", "Створити анімацію взаємодії із зброєю для NPC ворога: за замовчуванням його зброя має бути опущена "
           "вертикально вниз у руці (або схована за спиною чи на поясі); при знаходженні головного персонажа і "
           "наближенні до нього на радіус виконання пострілу – ворог повинен підняти зброю і зафіксувати її "
           "положення у руках для подальшого використання; при віддаленні від головного персонажа ворог повинен "
           "знову опустити зброю (або приховати).", []),
    ("3.", "Створити анімацію для 2+ об’єктів сцени, як мінімум 1 з яких створено самостійно та анімовано за "
           "допомогою засобів 3D моделювання (рух води в річці, колихання гілок дерев, переліт птахів, тощо), а "
           "інші – анімовано засобами UE.", []),
    ("4.", "Налаштувати 2 природні явища для гри (зміна дня/ночі, виникнення опадів з певною випадковою "
           "періодичністю, тощо).", []),
]
VARIANT_VERBATIM = "Варіант №10 «Підводний світ»"
VARIANT_TEXT = (
    "Відповідно до варіанта дія відбувається на станції AOS-DK. Зброєю головного персонажа є торпедне кільце "
    "дрона-атакера ASubDrone_Attacker (перезарядка за правою кнопкою миші), а NPC ворога – дорсальний пік "
    "SM_WPN_SigkillPike шестилапого ходока BP_OOMReaper з лабораторної роботи № 5, який у стані спокою "
    "прикріплено уздовж спини («схована за спиною»). Анімованими об’єктами сцени Lvl_FirstPerson є власноруч "
    "змодельований у 3ds Max вітрогенератор SK_Agro_WindGen, три маяки воріт, катер у Level Sequencer і рідина "
    "ємностей з водоростями; природними явищами – 12-хвилинна зміна дня й ночі та випадкові шторми з дощем.")

# ---------------------------------------------------------------------------------------------------------------------
# Фрагменти коду (скорочено, логіка збережена; рядки ≤ 78 символів)
# ---------------------------------------------------------------------------------------------------------------------
CODE_RELOAD_POSE = r"""
// SubDrone_Attacker.cpp: ApplyReloadPose() – поза «Safe» для VisualRoot
const FRotator PoseRot(ReloadNosePitchDeg * PoseAlpha,
                       YawSign * ReloadInboardYawDeg * PoseAlpha, 0.f);
VisualRoot->SetRelativeTransform(VisualRootBase *
    FTransform(PoseRot, FVector(0.f, 0.f, -ReloadDropCm * PoseAlpha)));
// казенник: лише зсув, обертання корпусу веде TickSpin()
HullRear->SetRelativeLocation(HullRearBase.GetLocation() +
    FVector(-ReloadBreechTravelCm * BreechAlpha, 0.f, 0.f));
"""
CODE_RELOAD_TICK = r"""
// TickReloadAnim(): фаза Lower (0,35 с) -> Feed -> Raise (0,40 с)
case EAttackerReloadPhase::Lower:
{
    const float X = FMath::Clamp(ReloadPhaseTime /
        FMath::Max(ReloadLowerTime, 0.01f), 0.f, 1.f);
    // казенник відкривається в останні 40 % фази
    ApplyReloadPose(EaseInOutCubic(X), FMath::SmoothStep(0.6f, 1.f, X));
    if (X >= 1.f) { SetReloadPhase(EAttackerReloadPhase::Feed); }
    break;
}
case EAttackerReloadPhase::Raise:   // повернення з перельотом EaseOutBack
    Pose = FromPose * (1.f - EaseOutBack(U, ReloadRaiseOvershoot * 10.f));
    break;
"""
CODE_RELOAD_FLIGHT = r"""
// Політ однієї торпеди: казенник -> слот, масштаб 0,35 -> 1 за 0,14 с
const float E = AttackerFx::EaseOutBack(X, 1.f);
TorpedoRing->UpdateInstanceTransform(Flight.Slot,
    FTransform(FQuat::Identity,
        FMath::Lerp(StartPos, SlotPos, static_cast<double>(E)),
        FVector(FMath::Lerp(0.35f, 1.f, FMath::Clamp(E, 0.f, 1.f)))),
    false, false, true);
// EndFeed(): у Raise лише після останньої торпеди й мінімального часу
if (ReloadPhase != EAttackerReloadPhase::Feed || !RoundFlights.IsEmpty()
    || ReloadFeedTime < ReloadMinFeedTime) { return; }
SetReloadPhase(EAttackerReloadPhase::Raise);
"""
CODE_POSTURE = r"""
// AAOS_AIEnemyCharacter::UpdateWeaponPosture(): автомат постави піка
const bool bHostile = RangeLevel == EAOSThreatLevel::Hostile;
const bool bDrawCond = bHostile && RangeCm <= DrawRange;       // 1500 см
switch (WeaponPosture)
{
case EAOSWeaponPosture::Stowed:
    if (bDrawCond) { SetWeaponPosture(EAOSWeaponPosture::Drawing); }
    break;
case EAOSWeaponPosture::Drawing:                               // 1,10 с
    PostureS = FMath::Min(1.f, PostureS + Dt / DrawTime);
    if (PostureS >= 1.f) { SetWeaponPosture(EAOSWeaponPosture::Ready); }
    break;
case EAOSWeaponPosture::Ready:
    if ((!bHostile || RangeCm > StowRange) && !IsStriking()    // 1900 см
        && Phase != EAOSReaperPhase::Evading)
    {
        OutOfRangeTime += Dt;                                  // гістерезис
        if (OutOfRangeTime >= StowGraceTime)                   // 1,5 с
            { SetWeaponPosture(EAOSWeaponPosture::Stowing); }
    }
    else { OutOfRangeTime = 0.f; }
    break;
case EAOSWeaponPosture::Stowing:                               // 1,40 с
    if (bDrawCond) { SetWeaponPosture(EAOSWeaponPosture::Drawing); break; }
    PostureS = FMath::Max(0.f, PostureS - Dt / StowTime);
    if (PostureS <= 0.f) { SetWeaponPosture(EAOSWeaponPosture::Stowed); }
    break;
}
"""
CODE_LANCE = r"""
// EvalLancePose(): три такти підняття. S – прогрес 0..1
if (S < kBeatUnlatch)            // 1. розфіксація: кінець виходить із гнізда
    ThetaDeg = Lerp(StowPitchDeg, kUnlatchPitchDeg,
                    SmoothStep(S / kBeatUnlatch));
else if (S < kBeatSwing)         // 2. змах над спиною, пізній поворот
{
    const float U = (S - kBeatUnlatch) / (kBeatSwing - kBeatUnlatch);
    ThetaDeg = Lerp(kUnlatchPitchDeg, ElevDeg, SmoothStep(U));
    KappaDeg = DrawCantDeg * FMath::Sin(PI * U);   // відхил назовні 20°
    PsiDeg   = YawTgtDeg * U * U;
}
else                             // 3. фіксація: згасаюче перерегулювання 6°
{
    const float V = (S - kBeatSwing) / (1.f - kBeatSwing);
    ThetaDeg = ElevDeg + LockOvershootDeg * 6.75f * V * Square(1.f - V);
    PsiDeg = YawTgtDeg;
}
// вісь піка d = Rz(psi) * (cos t, sin t * sin k, sin t * cos k)
Tip = Shoulder + DirW * (LanceWristRadius + kSocketOffset + PikeTipDistance);
// удар дозволено лише у поставі Ready
return !bDead && Weapon && WeaponPosture == EAOSWeaponPosture::Ready && ...;
"""
CODE_MAX = r"""
# Tools/max_build_SK_WindGen.py (pymxs): ключі A_WindGen_Spin, 30 кадр/с
def take_spin(bones, f0=0, clear=True):
    if clear: clear_anim(bones)
    for i in range(4):   # 0 / 120 / 240 / 360 градусів, ключ кожні 30 кадрів
        key_delta(bones, "WG_Rotor_Hub", 0, UE_SIGN * 360.0 * i / 3.0,
                  f0 + 30 * i, True)
    finish(bones, BONE_ORDER[5:], "linear", f0, f0 + 90)  # лінійні дотичні

def take_hunt(bones, f0=0, clear=True):   # A_WindGen_Hunt, 240 кадрів
    for f in range(0, 241, 20):
        a = 2 * math.pi * f / 240.0
        key_delta(bones, "WG_Nacelle_Yaw", 2,
                  UE_SIGN * 10.0 * math.sin(a), f0 + f, True)
        b = 2 * math.pi * (f - 20.0) / 240.0          # відставання 20 кадрів
        key_delta(bones, "WG_TailVane", 2,
                  UE_SIGN * 15.0 * math.sin(b), f0 + f, True)
"""
CODE_WG_PROXY = r"""
// AOSWindGenAnimInstance.cpp: FAOSWindGenAnimProxy::Evaluate()
const bool bSpin = Sample(SpinAnim, FMath::Fmod(SpinTime, SpinLen), Spin);
const bool bHunt = Sample(HuntAnim, FMath::Fmod(HuntTime, HuntLen), Hunt);
const bool bFurl = Sample(FurlAnim, FurlAlpha * FurlLen, Furl);  // Evaluator
// WG_Rotor_Hub: лише кліп Spin (аналог Layered Blend per Bone, depth 0)
if (Hub.IsValid() && bSpin) { Pose[Hub] = Spin.Pose[Hub]; }
// гондола й хвостове оперення: Hunt -> Furl за вагою FurlAlpha
for (const FName& Name : { Bones.NacelleYaw, Bones.TailVane })
{
    const FTransform Base = bHunt ? Hunt.Pose[I] : Pose[I];
    Pose[I] = bFurl ? Blend(Base, Furl.Pose[I], FurlAlpha) : Base;
}
// AAOSWindGenerator (10 Гц): швидкість і складання залежать від вітру
TargetSpinRate = (SpinBase + SpinPerWind * Wind) * RateJitter;
TargetFurlAlpha = FMath::SmoothStep(FurlStartWind, FurlFullWind, Wind);
"""
CODE_BEACON = r"""
// AOSGateBeacon.cpp: Tick() – маяк вмикається вночі та в шторм
OnAlpha = FMath::FInterpConstantTo(OnAlpha, bBeaconOn ? 1.f : 0.f,
    DeltaSeconds, 1.f / FMath::Max(RampTime, 0.05f));
if (OnAlpha > 0.f)                      // 4-секундний цикл спалаху
    PulseTime = FMath::Fmod(PulseTime + DeltaSeconds, PulsePeriod);
CurrentFlash = FMath::Clamp(FlashCurve.Eval(PulseTime), 0.f, 1.f);
CurrentTiltDeg = TiltAmplitudeDeg
    * FMath::Sin(2.f * UE_PI * PulseTime / PulsePeriod) * OnAlpha;
Rotation->RotationRate = FRotator(0.f,                // 20 -> 90 град/с
    FMath::Lerp(IdleYawRateDegPerSec, OnYawRateDegPerSec, OnAlpha), 0.f);
LensHead->SetRelativeRotation(FRotator(CurrentTiltDeg, 0.f, 0.f));
ApplyLights(CurrentFlash);
"""
CODE_SUN = r"""
// AOSDayNightCycle.cpp: SolveSun() – висота й азимут Сонця
const float H = Radians(15.f * (Hour - 12.f));            // годинний кут
const float SinEl = Sin(Phi) * Sin(Delta)
                  + Cos(Phi) * Cos(Delta) * Cos(H);
OutElevationDeg = Degrees(Asin(Clamp(SinEl, -1.f, 1.f)));
OutAzimuthDeg = Degrees(Atan2(-Sin(H),
    Tan(Delta) * Cos(Phi) - Sin(Phi) * Cos(H)));
// Step(): Місяць протилежний Сонцю й зникає в шторм
const float StormFade = 1.f - SmoothStep(MoonStormFadeStartAlpha,
                                         MoonStormFadeEndAlpha, StormAlpha);
const float Target = MoonIntensity * SmoothStep(0.f, 10.f, -El)
                     * Surface * StormFade;
MoonLight->SetIntensity(Target);
MoonLight->SetVisibility(Target > KINDA_SMALL_NUMBER);
// NightExposure: не дає автоекспозиції підсвітити ніч до денної яскравості
NightExposure->BlendWeight = bClampNightExposure ? NightFactor : 0.f;
"""
CODE_WEATHER = r"""
// AOSWeatherDirector::StepFsm(): Clear -> Building -> Raining -> Clearing
case EAOSWeatherState::Clear:
    if (ForcedMode == -1 && StateTime >= StateDuration)
    {
        Peak = RandRange(PeakRange);                      // 0,55 .. 1,0
        SetState(EAOSWeatherState::Building, RandRange(BuildingDuration));
    }
    break;
case EAOSWeatherState::Building:
    StormAlpha = Lerp(BuildStartAlpha, Peak, SmoothStep(0.f, 1.f, U));
    break;
// порив вітру: шум Перлина 0,15 Гц; дощ вмикається при StormAlpha >= 0,35
const float Gust = 0.5f
    + 0.5f * PerlinNoise1D(ElapsedTime * 0.15f + GustOffset);
Wind01 = Clamp(WindBase + 0.7f * StormAlpha + 0.1f * Gust, 0.f, 1.f);
RainRate01 = bRaining ? Clamp(Pow(StormAlpha, 1.5f) * (1.f + 0.25f * Gust),
                              0.f, 1.f) : 0.f;
// вологість: +1 за 25 с під дощем, -1 за 120 с під час сушіння
if (RainRate01 > 0.1f) Wetness += Dt / WetRiseSeconds;
else                   Wetness -= Dt / DryFallSeconds;
"""
CODE_RAIN = r"""
// AAOSWeatherDirector::UpdateRain(): Niagara NS_AOS_Rain
const bool bUnderwater = OceanController->IsCameraUnderwater();
const bool bWanted = RainRate01 > 0.01f && !bUnderwater;
if (bWanted)
{
    // компонент «стрибає» лише на цілі періоди решітки (15000 x 2000 см)
    const FVector Target = SnapRainOrigin(View, Current);
    if (!Target.Equals(Current, 1.0))
        { RainComponent->SetWorldLocation(Target); }
    RainComponent->SetVariableFloat(TEXT("User.RainRate"),
                                    12000.f * RainRate01);
    RainComponent->SetVariableFloat(TEXT("User.WaterZ"), WaterSurfaceZ);
    if (!RainComponent->IsActive()) { RainComponent->Activate(true); }
}
else if (bUnderwater)           // краплі зникають одразу
    { RainComponent->DeactivateImmediate(); }
"""
CODE_SHADOW = r"""
// AOSOceanDepthController: у шторм тіні Сонця м'якшають (VSM)
const float Soft = SmoothStep(StormShadowStartAlpha, StormShadowFullAlpha, S);
Sun->SetLightSourceAngle(Lerp(BaseAngle, StormSunSourceAngle, Soft)); // 25°
Sun->SetShadowAmount(Lerp(1.f, StormShadowAmount, Soft));             // 0,10
// інакше VSM обрізає півтінь до ~1,7 град.: піднімаємо CVar разом із кутом
CVar->Set(Lerp(BaseRayAngle, StormShadowMaxRayAngleRad, Soft),
          ECVF_SetByCode);                             // 0,03 -> 0,5 рад
"""

# ---------------------------------------------------------------------------------------------------------------------
# Таблиці виправлень та підсумків
# ---------------------------------------------------------------------------------------------------------------------
FIXES = [
    ["1", "Опівночі небо як удень", "автоекспозиція підсвічує ніч; SM_SkySphere – незмінний денний купол",
     "UPostProcessComponent NightExposure; матеріал M_AOS_NightStars"],
    ["2", "Зорі вдень у шторм", "NightFactor підсилено штормом для ламп",
     "окремий параметр MPC StarVisibility"],
    ["3", "Хмари з’являються після дощу", "матеріал хмар немонотонний: покриття 0,3 – повна хмарність",
     "покриття = 0,3 уже при S = 0,5; густина ×1,5"],
    ["4", "Краплі нахилені, падають прямо", "WPO зсував смуги, а швидкість була вертикальною",
     "WPO прибрано; X = 110…150 у швидкості емітера"],
    ["5", "Попередження про кілька Directional Light", "Сонце й Місяць мали однаковий пріоритет",
     "пріоритет у яскравішого світила в Step()"],
    ["6", "Сонце рухається ривками", "оновлення обертання лише 10 Гц", "обертання щокадрово, публікація 10 Гц"],
    ["7", "Дрібний Місяць", "диск Місяця мав розмір Сонця 0,536°", "DL_Moon.LightSourceAngle 4,5°"],
    ["8", "Дощ зникає біля камери", "відсікання за відстанню до камери в рендерерах Niagara",
     "відсікання вимкнено; стрибки по решітці"],
    ["9", "Різкі тіні у шторм", "VSM обмежує півтінь CVar 0,03 рад", "кут Сонця 25°, ShadowAmount 0,10, CVar 0,5"],
    ["10", "Місяць просвічує крізь шторм", "у Місяця не було штормового множника",
     "StormFade: інтенсивність → 0, світло приховано"],
]

BATCHES = [
    ["A1", "Перезарядка Attacker (завдання 1)", "pie_test_lab6_reload.py", "13 з 13", "1"],
    ["A2", "Постава піка Reaper (завдання 2)", "pie_test_lab6_posture.py", "14 з 14", "2, 3"],
    ["B", "Сонце, Місяць, погода: ядро C++", "pie_test_lab6_env_core.py", "14 з 14", "10, 11"],
    ["C1", "Матеріали, дощ Niagara, водорості", "перевірка в PIE за скриншотами", "виконано", "9, 12"],
    ["C2", "Маяки воріт і катер у Sequencer", "pie_test_lab6_c2.py", "8 з 8", "7, 8"],
    ["D", "Вітрогенератор з 3ds Max", "pie_test_lab6_windgen.py", "7 з 7", "4–6"],
    ["Нічне небо", "Експозиція та зоряний купол", "PIE за скриншотами", "виправлено", "10"],
    ["Env Polish", "Шість зауважень до погоди", "env_core + pie_test_atoll_lagoon.py", "14 з 14, лагуна ціла", "–"],
    ["Rain/Shadow", "Покриття дощу, м’які тіні", "PIE за скриншотами", "виправлено", "11, 12"],
    ["Shadow/Moon", "Тіні шторму, Місяць у шторм", "env_core + 8 станів PIE", "14 з 14, 8 з 8", "13, 14"],
]
MEASURED = [
    ["Перезарядка 32 набої (Lower + Feed + Raise)", "≈ 1,6 с", "1,538 с (0,359 + 0,778 + 0,401)"],
    ["Нахил, осідання, хід казенника", "−34°, 18 см, 11 см", "−34,0°, 18,0 см, 11,0 см; похибка кінця 0"],
    ["Енергія за перезарядку", "1,5 % один раз", "1,5 %; 0 пострілів під час анімації"],
    ["Підняття піка (DrawTime)", "1,10 с від ≤ 15 м", "1,11 с, старт на 9,4 м; без ударів"],
    ["Опускання піка (StowTime / грація)", "1,40 с / 1,5 с", "1,40 с / 1,59 с"],
    ["Швидкість ротора за SpinRate 1", "120°/с", "116–136°/с, 2–3 оберти за 8 с"],
    ["Розгойдування гондоли", "±10°", "від −10° до +10°, оперення 30°"],
    ["Шторм: SpinRate / FurlAlpha", "≈ 2,5 / > 0,95", "2,5–3,0 / 0,997; лопаті +79,7°"],
    ["Обертання маяка вночі", "90°/с", "89,5°/с; цикл спалаху 4,0 с"],
    ["Катер: радіус / швидкість", "9700 см / 507,9 см/с", "9700 ± 6 см / 507,6 см/с"],
    ["Сонце ясно / шторм (кут, амплітуда тіні)", "0,736° / 1,0", "25° / 0,10 при StormAlpha ≈ 1"],
]


# =====================================================================================================================
# 4. Звіт
# =====================================================================================================================
class Lab6Report(base.Report):
    def __init__(self, root, template):
        super().__init__(root, template)
        self.tmp = Path(tempfile.mkdtemp(prefix="lab6_fig_"))

    # ------------------------------------------------------------------ рисунки
    def shot(self, expected_no, path, title, width_cm=16.0):
        """Реальний скріншот (або композиція кадрів) + підпис «Рис. N. Назва» без крапки (п. 14)."""
        assert not title.endswith("."), title
        p = Path(path)
        if not p.is_file():
            self.missing.append(str(path))
            raise SystemExit(f"Немає зображення: {path}")
        if self.tmp not in p.parents:      # одиночні PNG стискаємо в JPEG (розмір .docx)
            p = compose([p], self.tmp / f"single_{expected_no}.jpg", width=1800)
        self.fig_no += 1
        assert self.fig_no == expected_no, (self.fig_no, expected_no, title)
        pic = base.fmt(self.doc.add_paragraph(), align=C, first=Cm(0), line=1.0, keep_next=True)
        pic.add_run().add_picture(str(p), width=Cm(width_cm))
        cap = base.fmt(self.doc.add_paragraph(), align=C, first=Cm(0))
        base.set_run_font(cap.add_run(f"Рис. {self.fig_no}. {title}"))
        self.last_blank = False
        return self.fig_no

    def expect_table(self, n):
        assert self.tab_no + 1 == n, (self.tab_no + 1, n)

    def S(self, *parts):
        return self.root.joinpath("Saved", *parts)

    def make_figures(self):
        s, t = self.S, self.tmp
        f = {}
        f["reload"] = compose(
            [s("Lab6_Verify", f"lab6_reload_{n}.png") for n in ("1_t020", "2_t075", "3_t145")],
            t / "reload.jpg", cols=3, width=640, crops=[(770, 290, 1330, 605)] * 3,
            labels=["(а)", "(б)", "(в)"])
        f["stowed"] = s("Lab6_Verify", "reaper_posture_stowed.png")
        f["ready"] = s("Lab6_Verify", "reaper_posture_ready.png")
        f["max"] = compose([s("Lab6_D_Verify", f"max_viewport_f{n}.png") for n in (0, 20, 160, 410)],
                           t / "max.jpg", cols=2, width=900, labels=["(а)", "(б)", "(в)", "(г)"])
        f["calm"] = s("Lab6_D_Verify", "D_calm_day.png")
        f["wg_night"] = s("Lab6_D_Verify", "D_night_closeup.png")
        f["beacon"] = compose(
            [s("Lab6_C2_Verify", n) for n in ("c2_noon_gate1_beacon.png", "c2_night_gate1_beam_a.png",
                                              "c2_storm_gate1_beam.png")],
            t / "beacon.jpg", cols=3, width=640, labels=["(а)", "(б)", "(в)"])
        f["skiff"] = s("Lab6_C2_Verify", "c2_skiff_1.png")
        f["algae"] = compose([s("Lab6_NightFix_Verify", "20_algae_vat_tod12.png"),
                              s("Lab6_NightFix_Verify", "21_algae_vat_tod0.png")],
                             t / "algae.jpg", cols=2, width=900, labels=["(а)", "(б)"])
        f["daynight"] = compose([s("Lab6_NightFix_Verify", "10_fixed_tod12.png"),
                                 s("Lab6_NightFix_Verify", "11_fixed_tod0.png")],
                                t / "daynight.jpg", cols=2, width=900, labels=["(а)", "(б)"])
        f["storm"] = compose([s("Lab6_NightFix_Verify", "30_storm_above_water_rain_on.png"),
                              s("Lab6_NightFix_Verify", "31_storm_underwater_rain_off.png")],
                             t / "storm.jpg", cols=2, width=900, labels=["(а)", "(б)"])
        f["market"] = s("Lab6_RainShadowFix_Verify", "RSF_D_S1_market.png")
        f["shadow"] = s("Lab6_ShadowMoonFix_Verify", "montage_shadow_before_after.png")
        f["moon"] = s("Lab6_ShadowMoonFix_Verify", "montage_moon_before_after.png")
        return f

    # ------------------------------------------------------------------ тіло звіту
    def build(self):
        self.section("Теоретичні відомості")
        self.para(THEORY[0])
        self.para(THEORY[1] + ":")
        n_slerp = self.formula("q = slerp(q_{A}, q_{B}, α) = [sin((1 − α)Ω)·q_{A} + sin(αΩ)·q_{B}] / sin Ω,")
        self.para(THEORY_AFTER_SLERP.replace("(1)", f"({n_slerp})"))
        self.para(THEORY2[0])
        self.para(THEORY2[1] + ":")
        n_sun = self.formula("sin h = sin φ · sin δ + cos φ · cos δ · cos H.")
        self.para(f"За формулою ({n_sun}) вночі h < 0, і Сонце вимикають, а Місяць, що стоїть у протилежній "
                  "точці неба, вмикають. " + THEORY2_FORMULA_TAIL)
        self.para(THEORY3)

        self.section("Завдання")
        self.para(TASK_INTRO)
        for marker, text, bullets in TASK_ITEMS:
            self.list_item(marker, text)
        self.para(VARIANT_VERBATIM)
        self.para(VARIANT_TEXT)

        self.section("Хід виконання")
        self.step_1()
        self.step_2()
        self.step_3()
        self.step_4()

        self.section("Результати")
        self.results()

        self.section("Висновки")
        self.conclusions()

    # ------------------------------------------------------------------ 1
    def step_1(self):
        self.subsection("1. Реалізація трифазної анімації перезарядки зброї головного персонажа")
        self.para(
            "Зброєю головного персонажа за варіантом є торпедне кільце дрона-атакера ASubDrone_Attacker: 32 "
            "мікроторпеди розташовано в інстансованому статичному меші TorpedoRing, а перезарядка запускається "
            "правою кнопкою миші (дія IA_Sub_DroneReload). До лабораторної роботи перезарядка не мала жодної "
            "пози: слоти кільця просто змінювали масштаб від 0,001 до 1 за 0,7 с. Додано скінченний автомат "
            "EAttackerReloadPhase { None, Lower, Feed, Raise } і три анімовані частини: поза корпусу, відкривання "
            "казенника та політ торпед. Підхід процедурний: SetRelativeTransform для VisualRoot, HullRear і "
            "елементів TorpedoRing, тому колізія, навігація та напрямок огляду апарата не змінюються.")
        self.para(
            "Послідовність відповідає завданню: опускання зброї перед перезарядкою (фаза Lower), вкладання набоїв "
            "(Feed) та підняття у вихідне положення (Raise). Тривалості та параметри кожної фази наведено в "
            "таблиці 1; всі вони є властивостями EditAnywhere, тому їх можна налаштовувати без перекомпіляції.")
        self.expect_table(1)
        self.table(
            "Фази анімації перезарядки ASubDrone_Attacker",
            ["Фаза", "Тривалість", "Що бачить гравець", "Параметри"],
            [
                ["Lower", "0,35 с", "ніс опускається й повертається від прицілу, апарат осідає, корпуси гальмують "
                                   "(τ = 0,12 с), кільце ставить слот 0 на 12 годин; наприкінці відкривається казенник",
                 "−34°, 16° усередину, 18 см, 11 см"],
                ["Feed", "max(N · 0,022; 0,30) + 0,14 с", "торпеди одна за одною вилітають із казенника у свої слоти, "
                                                          "кільце заповнюється за годинниковою стрілкою, наприкінці "
                                                          "продування бульбашками",
                 "EaseOutBack, масштаб 0,35 → 1"],
                ["Raise", "0,40 с", "казенник зачиняється з перельотом 1,5 см, ніс повертається на приціл "
                                   "з перельотом, свічення спалахує вдвічі яскравіше; вогонь розблоковується лише "
                                   "в кінці фази", "EaseOutBack, Glow × 2 на 0,15 с"],
            ],
            [2.0, 3.5, 8.0, 4.0],
            {0: C, 1: C},
        )
        self.para(
            "Поза корпусу задається коефіцієнтом α від 0 до 1: у фазі Lower α = EaseInOutCubic(t / 0,35), під час "
            "Feed α = 1, у Raise α = 1 − EaseOutBack(t / 0,40). Бічний нахил береться з протилежним знаком до "
            "зсуву слота (CombatOffset.Y), тому дрон завжди відвертається до осі Shell-1. Реалізацію пози та фази "
            "Lower наведено нижче; послідовність функцій узгоджено з частиною Tick апарата (TickReloadAnim "
            "викликається після TickCombat і перед TickSpin).")
        self.code(CODE_RELOAD_POSE)
        self.code(CODE_RELOAD_TICK)
        self.para(
            "Політ кожної торпеди є твіном між точкою казенника (X = −30 см, радіус 0,15 від радіуса кільця, "
            "масштаб 0,35) і її слотом з кривою EaseOutBack за 0,14 с; в одному кадрі в польоті може перебувати "
            "до 17 торпед. Перехід у фазу Raise дозволено лише тоді, коли літають нуль торпед і минув "
            "мінімальний час подачі 0,30 с (потрібний, щоб при 1–3 наборах анімація була помітною). Якщо під час "
            "анімації апарат заходить у док чи його обслуговує станція, послідовність пропускає Feed і швидко "
            "повертається в Raise без повернення енергії.")
        self.code(CODE_RELOAD_FLIGHT)
        self.para(
            "Перевірку виконує Tools/pie_test_lab6_reload.py: апарат розгортається, кільце частково спустошується "
            "пострілами, після чого надсилається команда перезарядки та фіксуються фази, телеметрія пози й "
            "кадри кокпіта (рис. 1). Результати зведено в розділі «Результати».")

    # ------------------------------------------------------------------ 2
    def step_2(self):
        self.subsection("2. Реалізація дистанційної взаємодії зі зброєю NPC ворога")
        self.para(
            "Як NPC ворога використано шестилапого ходока BP_OOMReaper (клас AAOS_AIEnemyCharacter) з лабораторної "
            "роботи № 5, а зброєю є дорсальний пік SM_WPN_SigkillPike на кістці Arm_Wrist_Bone. У стані спокою "
            "пік «схований за спиною»: рука відкинута назад уздовж спини, кінчик нижче горизонталі на 12° "
            "(StowPitchDeg = 192°). Раніше рука розкладалася лише за фазою ШІ (Chase, Shadow, Evading), "
            "а не за відстанню, тому додано явний автомат постави EAOSWeaponPosture { Stowed, Drawing, Ready, "
            "Stowing } з гістерезисом. Умови переходів наведено в таблиці 2.")
        self.expect_table(2)
        self.table(
            "Автомат постави зброї NPC ворога",
            ["Перехід", "Умова"],
            [
                ["Stowed → Drawing", "рівень загрози Hostile й відстань D ≤ DrawRange = 1500 см (15 м) "
                                      "від турелі руки до найближчої точки корпусу Shell-1; також отримання шкоди"],
                ["Drawing → Ready", "прогрес PostureS досяг 1 за DrawTime = 1,10 с"],
                ["Ready → Stowing", "D > StowRange = 1900 см (19 м) або загроза нижча за Hostile, безперервно "
                                     "StowGraceTime = 1,5 с; не триває удар; фаза не Evading"],
                ["Stowing → Drawing", "знову виконано умову підняття; рух розвертається з поточного прогресу, "
                                       "без стрибка пози"],
                ["Stowing → Stowed", "PostureS = 0 за StowTime = 1,40 с"],
            ],
            [3.8, 13.7],
        )
        self.para(
            "Діапазон 15 м – 19 м утворює гістерезис шириною 4 м, а додаткова затримка 1,5 с унеможливлює "
            "мерехтіння постави, коли відстань коливається біля порогу. Відстань для автомата надає сервіс "
            "BTService_AOS_ReaperSense, що викликає SetCombatRangeInfo (єдиний доданий рядок у дереві поведінки). "
            "Перевірка часу: Scuttle зі швидкістю 620 см/с долає шлях від 1500 до 430 см (StrikeReach) приблизно "
            "за 1,7 с, що більше за DrawTime 1,10 с, тому пік завжди встигає піднятися до першого удару. "
            "Додатково CanStrike() вимагає WeaponPosture == Ready, тож під час підняття вузол удару просто "
            "не виконується. Нижче наведено реалізацію автомата.")
        self.code(CODE_POSTURE)
        self.para(
            "Поза піка обчислюється кінематично. Рука й пік розглядаються як єдиний жорсткий «спис», що "
            "обертається навколо плеча (Arm_Pitch1_Bone) у вертикальній площині, відхиленій назовні на кут κ. "
            "Вісь піка задає вектор d(θ, κ, ψ) = R_{z}(ψ)·(cos θ, sin θ · sin κ, sin θ · cos κ), де θ – кут "
            "підйому від осі +X, а ψ – рискання до цілі. Кінець піка відстоїть від плеча на LanceWristRadius = 110 см "
            "плюс 15 см сокета й 262 см піка. Двокісткова IK руки та вирівнювання зап’ястка вже були в проєкті, "
            "тому PostureS лише задає ціль і напрямок (OutTipSpeed = 0, інтерполяцію вимкнено).")
        self.para(
            "Підняття складається з трьох явних тактів (табл. 3). Опускання виконується повільніше (1,40 с) "
            "і теж має три такти: розфіксація з відкотом на 20 см, зворотний змах і посадка з невеликим "
            "перельотом. Для втраченої цілі напрямок береться з кешу LastReadyDir, оскільки ShellTarget "
            "на той момент уже нульовий. На момент фіксації в логу терміналу Shell-1 з’являється рядок "
            "«SIGKILL pike ARMED», а після опускання – «pike stowed».")
        self.expect_table(3)
        self.table(
            "Такти підняття піка Reaper (DrawTime = 1,10 с)",
            ["Такт", "Час, с", "Рух", "Щелепи"],  # час за Draw: 0,20 / 0,85 / 1,10 с
            [
                ["1. Розфіксація", "0–0,20", "θ: 192° → 200°, кінець виходить із гнізда", "15°"],
                ["2. Змах", "0,20–0,85", "θ → ε за SmoothStep; κ = 20°·sin(πu); ψ = ψ_{ц}·u²",
                 "25°"],
                ["3. Фіксація", "0,85–1,10", "згасаюче перерегулювання 6° за законом 6,75·V·(1 − V)²",
                 "0° («клац»)"],
            ],
            [3.4, 2.4, 8.7, 3.0],
            {1: C, 3: C},
        )
        self.code(CODE_LANCE)
        self.para(
            "Перевірку виконує Tools/pie_test_lab6_posture.py: апарат Shell-1 телепортується на 25 м, потім на 12 м "
            "і знову на 25 м від Reaper; очікувана послідовність Stowed → Drawing → Ready → Stowing → Stowed, "
            "далі повторне підняття. Кадри двох постав подано на рис. 2 та 3.")

    # ------------------------------------------------------------------ 3
    def step_3(self):
        self.subsection("3. Створення анімованих об’єктів сцени")
        self.para(
            "Завдання вимагає щонайменше два анімованих об’єкти, один з яких створено самостійно й анімовано "
            "засобами 3D-моделювання. У роботі виконано обидві умови: вітрогенератор SK_Agro_WindGen "
            "змодельовано й анімовано в 3ds Max, а інші об’єкти (три маяки воріт, катер і рідина ємностей з "
            "водоростями) анімовано засобами Unreal Engine.")
        self.para(
            "3.1. Самостійне 3D-моделювання та ключова анімація вітрогенератора SK_Agro_WindGen у 3ds Max 2027. "
            "Початковий вітрогенератор (Bible M-15) був статичним інстансом SM_Agro_WindGen з нерухомим трироторним "
            "гвинтом (габарити 200 × 200 × 993 см), що є очевидним кандидатом на анімацію. Скрипт "
            "Tools/max_build_SK_WindGen.py (pymxs) будує закриті твердотільні елементи (0 відкритих ребер, до "
            "3500 трикутників) і розподіляє їх по дев’яти кістках із жорсткою вагою 1,0: WG_Root, WG_Tower, "
            "WG_Nacelle_Yaw (рискання гондоли), WG_TailVane (хвостове оперення), WG_Light_Obstr (хост сокета "
            "сигнального вогню), WG_Rotor_Hub (кочення втулки) і три лопаті WG_Blade_0…2 з поворотом кроку "
            "вздовж радіальної осі. Анімацію записано в часовій шкалі Max (30 кадрів на секунду) трьома "
            "кліпами, наведеними в таблиці 4; кожен кліп експортується окремим FBX (Bake Animation, "
            "точний діапазон кадрів), а меш із скелетом – без анімації.")
        self.expect_table(4)
        self.table(
            "Кліпи SK_Agro_WindGen (3ds Max, 30 кадр/с)",
            ["Кліп", "Кадри", "Ключі", "Режим"],
            [
                ["A_WindGen_Spin", "0–90 (3 с)", "втулка: 0°, 120°, 240°, 360° кожні 30 кадрів, лінійні дотичні; "
                                               "лопаті лишаються на 8°", "цикл"],
                ["A_WindGen_Hunt", "0–240 (8 с)", "гондола ±10° за синусом (Bezier), оперення ±15° із "
                                                 "відставанням 20 кадрів", "цикл"],
                ["A_WindGen_Furl", "0–60 (2 с)", "лопаті 8° → 88°, гондола +55°, оперення −35°, плавний вхід і "
                                                "вихід", "один раз"],
            ],
            [4.6, 2.6, 7.6, 2.7],
            {1: C, 3: C},
        )
        self.code(CODE_MAX)
        self.para(
            "Помітне ускладнення стосується знаків кутів: меш у Max дзеркалено (y → −y), щоб після імпорту "
            "системи координат Max (права) → UE (ліва) він опинився без віддзеркалення, а дзеркало змінює напрям "
            "кожного обертання. Тому всі кути в скрипті задано в «просторі UE», а константа UE_SIGN = −1 "
            "перетворює їх у значення ключів Max. Для обертання втулки кути записуються прямо в канал Euler, "
            "інакше quatToEuler згорне 240° у −120°, і лінійний сегмент піде у зворотний бік. Кліп Spin "
            "проходить повний оберт за 3 с, тобто 120°/с, що відповідає значенню з Bible для швидкості 1; "
            "кадр 90 ідентичний кадру 0, тому цикл безшовний. На рис. 4 показано чотири кадри кліпів у вікні "
            "перегляду 3ds Max.")
        self.para(
            "Імпорт у UE виконали скрипти Tools/ue_import_SK_WindGen.py та Tools/ue_deploy_WindGen_assets.py: "
            "створено SK_Agro_WindGen, SKEL_Agro_WindGen і три UAnimSequence у теці Environment/Atoll/WindGen "
            "(Remove Redundant Keys вимкнено, частота 30 кадр/с). Замість ручного складання AnimGraph "
            "анімацію виконує нативний клас UAOSWindGenAnimInstance із власним FAnimInstanceProxy. Блок "
            "Evaluate реалізує те саме, що описано в теоретичних відомостях: Spin застосовується лише до "
            "WG_Rotor_Hub (аналог Layered Blend per Bone із глибиною 0), Hunt – до гондоли й оперення, а Furl "
            "береться як Sequence Evaluator із часом FurlAlpha · 2,0 с і змішується з Hunt за "
            "вагою FurlAlpha. Швидкість обертання задає SpinRate, а положення складання – FurlAlpha, які щокадрово "
            "ставить актор AAOSWindGenerator (10 Гц, з випадковим зсувом фази та ±10 % темпу кожного екземпляра).")
        self.code(CODE_WG_PROXY)
        self.para(
            "У рівні статичний інстанс WindGenerators приховано (SetActorHiddenInGame, колізію вимкнено, об’єкт "
            "не видалено), а на його три трансформації поставлено BP_AOS_WindGen_0…2. Швидкість вітру Wind01 "
            "береться з підсистеми середовища (розділ 4): у штиль SpinRate ≈ 1, у шторм він зростає до 2,5–3,0, "
            "а понад Wind01 = 0,8 лопаті встановлюються флюгером (FurlAlpha → 1). Пульсуюче червоне "
            "сигнальне світло та емісивний слот MS_Beacon вмикаються вночі та в шторм.")
        self.para(
            "3.2. Анімація об’єктів засобами UE5. Три маяки воріт, катер і рідина ємностей створено без "
            "DCC-анімації; використані технології та параметри наведено в таблиці 5.")
        self.expect_table(5)
        self.table(
            "Об’єкти, анімовані засобами Unreal Engine",
            ["Об’єкт", "Засіб UE", "Параметри"],
            [
                ["Маяки воріт × 3 (AAOSGateBeacon)", "C++: URotatingMovementComponent, крива спалаху, "
                                                    "нахил головки",
                 "20 → 90°/с; два зустрічні SpotLight 2°/8° до 200 000 кд; спалах 4 с; нахил ±2°; "
                 "кожні 0,5 с читає NightFactor і StormAlpha"],
                ["Катер BP_AOS_HarbourSkiff", "Level Sequencer: LS_Atoll_HarbourSkiff, ALevelSequenceActor",
                 "120 с, 30 кадр/с; коло R 9700 см навколо (−1000; 700); 53 ключі на вісь; адитивна секція "
                 "Z ±12 см, крен ±3°, тангаж ±2°; Auto Play, Loop"],
                ["Рідина ємностей M_AOS_AlgaeLiquid", "матеріальна анімація: Panner, Time, MPC",
                 "дві шумові текстури зі швидкостями (0,02; 0,01) і (−0,015; 0,025); пульсація 0,08 Гц; "
                 "NightIntensity 2,2"],
            ],
            [4.0, 5.2, 8.3],
        )
        self.para(
            "Маяк AAOSGateBeacon (три екземпляри на опорах воріт хвилерізу) складається з корпусу, лінзової "
            "головки на осі обертання й двох зустрічних прожекторів, що створюють об’ємні промені у вологому "
            "повітрі. Раз на 0,5 с актор опитує UAOSEnvironmentStateSubsystem; якщо max(NightFactor, StormAlpha) "
            "> 0,3, маяк вмикається з рампою 1 с, інакше повертається в режим очікування (20°/с, світло 5 %). "
            "Гістерезис вимкнення становить 0,27, тому в сутінках маяк не мерехтить.")
        self.code(CODE_BEACON)
        self.para(
            "Катер збирається з шести елементів SM_Path_FloatNode, огородження, рубки, щогли з ліхтарем на "
            "90 кд і трьох реквізитних ящиків; усі 30 компонентів без колізії. Базова доріжка Transform в "
            "LS_Atoll_HarbourSkiff описує коло з поворотом уздовж руху (рискання = азимут + 90°), а друга, "
            "адитивна, секція додає хитавицю з періодами 3,243; 4,8 та 3,871 с, які вкладаються в 120 с цілим "
            "числом циклів (37, 25 та 31), тому шов циклу невидимий. До рівня додано лише п’ять "
            "акторів у теці Environment/Atoll/Animated. Матеріал M_AOS_AlgaeLiquid додає на ємності з "
            "водоростями світіння, що вночі зростає, а вдень приглушене (рис. 9).")

    # ------------------------------------------------------------------ 4
    def step_4(self):
        self.subsection("4. Реалізація двох природних явищ: зміна дня й ночі та періодичні шторми")
        self.para(
            "Обидва явища реалізовано в C++ в одному модулі Source/AOS_DK/Environment/Sky. Центральний елемент – "
            "UAOSEnvironmentStateSubsystem (UWorldSubsystem): AAOSDayNightCycle та AAOSWeatherDirector лише "
            "публікують у нього час доби, шторм, вітер і вологість, а підсистема сама складає множники Сонця, "
            "неба й туману та є єдиним записувачем Material Parameter Collection MPC_AOS_Atoll (NightFactor, "
            "StarVisibility, Wetness, StormAlpha, Wind01). Яскравість Сонця й неба пише лише "
            "AAOSOceanDepthController, який множить закеровані базові значення на ці коефіцієнти; тому глибинне "
            "послаблення Бера–Ламберта автоматично накладається на день, ніч і шторм.")
        self.para(
            "Явище 1: зміна дня й ночі. AAOSDayNightCycle крутить Сонце та протилежний Місяць за формулою (2): "
            "широта 8°, схилення 0°, доба триває 12 хв, старт о 15:00 (азимут за цієї години збігається "
            "з авторським −10,3°). Вночі автоекспозицію обмежує UPostProcessComponent NightExposure з пріоритетом "
            "−100 (під водою вищий пріоритет має постобробка води), а небо отримує зоряний купол "
            "M_AOS_NightStars, що множить текстуру зірок на StarVisibility та вимикається під водою. Значення "
            "величин у ключові моменти доби наведено в таблиці 6; консольні команди aos.env.TimeOfDay, "
            "aos.env.DayLengthMin та aos.env.Pause дають змогу прискорити цикл.")
        self.expect_table(6)
        self.table(
            "Стан середовища в ключові години (ясна погода)",
            ["Час", "NightFactor", "Сонце, інтенсивність", "Небо, множник", "Місяць"],
            [
                ["12:00", "0,00", "6,0", "1,00", "0"],
                ["15:00", "0,00", "6,0 (рискання −10,31°)", "1,00", "0"],
                ["18:00", "0,35", "2,11", "0,43", "0"],
                ["00:00", "1,00", "0 (приховано)", "0,12", "0,6"],
            ],
            [2.4, 3.2, 5.2, 3.4, 3.3],
            {i: C for i in range(5)},
        )
        self.code(CODE_SUN)
        self.para(
            "Явище 2: випадкові шторми. AAOSWeatherDirector реалізує автомат із чотирьох станів з випадковими "
            "тривалостями (FRandomStream; Seed = 0 означає час, фіксований Seed дає відтворювані демонстрації). "
            "Параметри станів наведено в таблиці 7. Перший шторм починається за 60–120 с після старту PIE, "
            "тому явище видно без жодних команд; команда aos.env.Storm 0|1|auto примусово вмикає, вимикає "
            "чи повертає випадковий режим.")
        self.expect_table(7)
        self.table(
            "Автомат погоди AAOSWeatherDirector",
            ["Стан", "Тривалість, с", "StormAlpha", "Що відбувається"],
            [
                ["Clear", "150–330 (перший 60–120)", "0", "ясно, вітер 0,15–0,3, поле хмар базове"],
                ["Building", "25–40", "0 → Peak", "хмари змикаються, вітер зростає"],
                ["Raining", "90–180", "Peak 0,55–1,0", "дощ, вологість росте, лампи Атолу вмикаються"],
                ["Clearing", "30–50", "Peak → 0", "дощ припиняється при StormAlpha < 0,35; сушіння"],
            ],
            [2.6, 4.3, 3.6, 7.0],
            {0: C, 1: C, 2: C},
        )
        self.code(CODE_WEATHER)
        self.para(
            "Дощ відтворює GPU-система Niagara NS_AOS_Rain з двома емітерами: смуги (спрайти вздовж швидкості "
            "1,2 × 70 см, матеріал M_AOS_RainStreak) і бризки на поверхні (M_AOS_RainSplash). Система не має "
            "станових модулів, тому колізії з дахами неможливі; замість них матеріал читає запечену карту висот "
            "дахів T_AOS_RainHeight (1024², 16 біт, запечена трасуванням з Z = 1600 см) і гасить краплі під "
            "навісами. Обгортання поля навколо камери виконує WPO матеріалу, а компонент AAOSWeatherDirector "
            "лише стрибає цілими періодами решітки, щоб краплі були прив’язані до світу. Під водою компонент "
            "вимикається миттєво (DeactivateImmediate), що забезпечує синхронізацію з AAOSOceanDepthController.")
        self.code(CODE_RAIN)
        self.para(
            "Шторм також змінює оточення: множники Сонця й неба (×0,25 і ×0,60), густина туману повітря ×4, "
            "покриття хмар, вологість MPC (матеріали Атолу темнішають і блищать) і вітер (вітрогенератори). "
            "Під час тестування в живому PIE виявлено десять дефектів, усі виправлено й підтверджено. "
            "Зведення наведено в таблиці 8, а код м’яких штормових тіней – нижче.")
        self.expect_table(8)
        self.table(
            "Виправлення за результатами живого тестування явищ",
            ["№", "Симптом", "Причина", "Виправлення"],
            FIXES,
            [0.9, 4.0, 6.0, 6.6],
            {0: C},
        )
        self.code(CODE_SHADOW)

    # ------------------------------------------------------------------ результати
    def results(self):
        f = self.make_figures()
        self.para(
            "Усі тести виконано в режимі PIE: автоматизовані скрипти Tools/pie_test_lab6_*.py пишуть "
            "телеметрію у файли Saved/Lab6_*.json, а скриншоти зроблено з тієї ж сесії. Для кожного пакета "
            "робіт (A1, A2, B, C1, C2, D) та подальших виправлень підсумки наведено в таблиці 9; скриптові "
            "перевірки пройдено повністю: 13 + 14 + 14 + 8 + 7 = 56 перевірок. Ключові виміри порівняно із "
            "заданими значеннями зведено в таблиці 10.")
        self.expect_table(9)
        self.table(
            "Підсумок перевірок за пакетами робіт",
            ["Пакет", "Що перевірено", "Тест", "Результат", "Рис."],
            BATCHES,
            [1.9, 4.2, 6.2, 3.3, 1.9],
            {0: C, 3: C, 4: C},
        )
        self.expect_table(10)
        self.table(
            "Ключові виміри PIE",
            ["Параметр", "Задано", "Виміряно"],
            MEASURED,
            [6.5, 4.0, 7.0],
        )

        self.para(
            "1) Перезарядка (завдання 1). Три кадри кокпітного огляду з тестового запуску показано на рис. 1: "
            "нос опущено й відхилено від прицілу, казенник відкрито (а, t = 0,20 с), торпеди летять у "
            "слоти (б, t = 0,75 с) і дрон знову дивиться на приціл (в, t = 1,45 с). Порядок фаз LOWER → FEED → "
            "RAISE → NONE збігається з очікуваним, а стрільба заблокована весь цикл.")
        self.shot(1, f["reload"], "Перезарядка дрона-атакера в кокпітному вигляді: (а) Lower, t = 0,20 с; "
                                  "(б) Feed, t = 0,75 с; (в) завершення Raise, t = 1,45 с", 17.0)
        self.para(
            "2) Зброя NPC ворога (завдання 2). На рис. 2 пік сховано за спиною (Stowed, s = 0), а на рис. 3 "
            "він піднятий і спрямований уперед (Ready, s = 1). Над ворогом видно тривимірну шкалу здоров’я 4 × 4. "
            "Кадри зроблено збоку з тимчасовим підсвічуванням; тимчасові джерела світла після зйомки "
            "видалено з рівня.")
        self.shot(2, f["stowed"], "Reaper зі схованим піком: поза Stowed, пік уздовж спини", 15.0)
        self.shot(3, f["ready"], "Reaper з піднятим піком: поза Ready після підняття за 1,10 с", 15.0)
        self.para(
            "3) Об’єкти сцени (завдання 3). Рис. 4 містить кадри кліпів вітрогенератора в 3ds Max: початкова "
            "поза (а), обертання (б, в) та гондола у повороті (г). У PIE ті ж вітрогенератори видно на рис. 5 та 6; "
            "ротор обертається зі швидкістю 116–136°/с, гондола розгойдується на ±10°, а вночі вмикається "
            "червоне сигнальне світло.")
        self.shot(4, f["max"], "Кадри анімації вітрогенератора SK_Agro_WindGen у вікні перегляду 3ds Max: "
                               "(а) кадр 0, (б) кадр 20, (в) кадр 160, (г) кадр 410", 16.0)
        self.shot(5, f["calm"], "Сцена Atoll у PIE за спокійної денної погоди (Storm 0, TimeOfDay 12)", 16.0)
        self.shot(6, f["wg_night"], "Нічна сцена: сигнальні вогні вітрогенераторів і світіння ємностей з "
                                    "водоростями", 16.0)
        self.para(
            "Маяки, катер і рідина водоростей (рис. 7–9) підтверджують роботу засобів UE. На рис. 7 маяк "
            "вимкнено вдень (а), увімкнено вночі зі спалахом (б) і в штормі з променем крізь дощ (в); "
            "виміряна кутова швидкість обертання вночі становить 89,5°/с. Катер рухається по колу радіусом "
            "9700 см зі швидкістю 507,6 см/с (рис. 8), а рідина в ємностях вдень світить помірно, а вночі "
            "інтенсивно, без пересвічування (рис. 9).")
        self.shot(7, f["beacon"], "Маяк воріт: (а) день, режим очікування; (б) ніч, спалах і промінь; "
                                  "(в) шторм, промінь крізь дощ", 17.0)
        self.shot(8, f["skiff"], "Катер BP_AOS_HarbourSkiff на траєкторії LS_Atoll_HarbourSkiff у лагуні", 15.0)
        self.shot(9, f["algae"], "Ємність із водоростями M_AOS_AlgaeLiquid: (а) день, TimeOfDay 12; "
                                 "(б) ніч, TimeOfDay 0", 16.0)
        self.para(
            "4) Природні явища (завдання 4). На рис. 10 показано той самий ракурс опівдні (а) та опівночі (б): "
            "вночі видно зорі, підсвічені вікна й неонові кільця, а автоекспозиція не підсвічує сцену. Рис. 11 "
            "відображає шторм над водою з дощем (а) та під водою (б), де дощ повністю вимкнено без витоку зір. "
            "Рис. 12 демонструє дощ і мокрі палуби на ринку (Wetness = 1,0), а на рис. 13 – різкі тіні до "
            "виправлення, їх зникнення в шторм після нього та повернення різких тіней за ясної погоди. "
            "На рис. 14 Місяць у шторм приховано (так усунено ореол у хмарах), а за ясної ночі диск Місяця видно.")
        self.shot(10, f["daynight"], "Цикл дня й ночі: (а) 12:00, (б) 00:00 з зорями та освітленими вікнами", 16.0)
        self.shot(11, f["storm"], "Шторм: (а) дощ над водою, (б) під водою дощ вимкнено, глибина 31,3 м", 16.0)
        self.shot(12, f["market"], "Дощ і мокрі палуби на ринку Атолу під час шторму", 15.0)
        self.shot(13, f["shadow"], "Тіні Сонця о 17:24: шторм до виправлення, шторм після виправлення "
                                   "та ясна погода (зліва направо)", 16.0)
        self.shot(14, f["moon"], "Місяць у нічній сцені: до виправлення (шторм, ореол у хмарах), після "
                                 "виправлення (шторм, Місяць прихований) і за ясної погоди", 16.0)

    # ------------------------------------------------------------------ висновки
    def conclusions(self):
        self.para(
            "У лабораторній роботі реалізовано два види ігрових анімацій для сцени AOS-DK: процедурні, "
            "що обчислюються в C++ (трифазна перезарядка дрона-атакера за 1,54 с та автомат постави піка Reaper "
            "з гістерезисом 15/19 м і трьома тактами підняття), і ключові, створені в 3ds Max 2027 "
            "(дев’ятикістковий вітрогенератор SK_Agro_WindGen із кліпами Spin, Hunt та Furl, які в Unreal Engine "
            "поєднуються власним FAnimInstanceProxy за аналогом Layered Blend per Bone). Анімацію об’єктів "
            "засобами UE показано трьома способами: компонентна й крива анімація маяків воріт, Level Sequencer "
            "для замкненого руху катера та матеріальна анімація рідини водоростей. Два природні явища – "
            "12-хвилинний цикл дня й ночі та випадкові шторми з дощем Niagara – інтегровано через єдину "
            "підсистему середовища та MPC, що синхронізує освітлення, матеріали, вітрогенератори, маяки "
            "й AAOSOceanDepthController, зокрема вимикає дощ під водою. Усі скриптові перевірки PIE пройдено "
            "(13 + 14 + 14 + 8 + 7 = 56), а десять дефектів, виявлених у живому тестуванні, виправлено з "
            "підтвердженням скриншотами. Отже, поєднання процедурних, покадрових і керованих секвенсором анімацій "
            "з єдиною моделлю середовища дає змогу створювати відчутну, реагуючу на стан гри сцену без жодної "
            "ручної збірки AnimGraph.")

    # ------------------------------------------------------------------ документ
    def finalize_properties(self):
        cp = self.doc.core_properties
        cp.keywords = ("Unreal Engine 5, AOS_DK, UAnimSequence, FAnimInstanceProxy, Level Sequencer, 3ds Max, "
                       "Niagara, день і ніч, дощ")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=HERE.parent, help="корінь проєкту AOS_DK")
    ap.add_argument("--template", type=Path, default=None, help="шаблон звіту кафедри (.docx)")
    ap.add_argument("--out", type=Path, default=None, help="шлях до вихідного .docx")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    template = args.template or (root / base.TEMPLATE_REL)
    out = args.out or (root / TARGET_REL)

    rep = Lab6Report(root, template)
    rep.build()
    rep.finalize_properties()
    n_chars = rep.validate()
    rep.save(out)
    print(f"OK: {out}")
    print(f"    рисунків {rep.fig_no}, таблиць {rep.tab_no}, формул {rep.formula_no}, символів {n_chars}")
    if rep.missing:
        print("    УВАГА, відсутні зображення: " + "; ".join(rep.missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
