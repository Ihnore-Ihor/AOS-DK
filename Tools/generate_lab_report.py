# -*- coding: utf-8 -*-
"""
AOS-DK | Генератор звіту до лабораторної роботи № 4 «Взаємодія з Акторами сцени» (варіант № 10 «Підводний світ»).

Звіт будується на основі офіційного шаблону кафедри ПЗ (Docs/Templates/Шаблон_звіту_ПРІ_2026.docx):
титульний аркуш, стилі, колонтитул із номером сторінки та параметри розділу беруться з шаблону без змін,
змінюються лише змінні поля титульного аркуша (номер роботи, тема, виконавець, викладач), а тіло
звіту (від абзацу «Тема роботи» до кінця) генерується заново.

Запуск із кореня проєкту (або будь-звідки):
    python Tools/generate_lab_report.py [--root <AOS_DK>] [--template <.docx>] [--out <.docx>]

Результат: Docs/Звіт_ЛР_Взаємодія_з_Акторами_Ігор_Брайченко.docx

Вимоги шаблону, які виконує скрипт:
  1) поля: ліве 25 мм, праве 10 мм, верхнє і нижнє 20 мм;
  2) титульний аркуш – як у шаблоні;
  3) номер сторінки вгорі праворуч, титульна сторінка не нумерується;
  4) текст – Times New Roman 14, інтервал 1,5; код – Courier New 10, інтервал 1; без курсиву;
  5) абзацний відступ 1,25 см усюди; 6) вирівнювання за шириною;
  7) без інтервалів до/після абзацу і без порожніх рядків усередині тексту;
  8) списки: відступ ліворуч 1,25 см, навислий 1 см;
  9) розділи – ВЕЛИКИМИ, жирним, порожній рядок до (якщо не нова сторінка) і після, на сторінці з
     назвою – хоча б 1 рядок тексту;
  10) підрозділи – «N. Назва» жирним, абзацний відступ, порожній рядок перед, без крапки в кінці;
  14) «Рис. N. Назва» посередині, без крапки;
  15) «Таблиця N.» праворуч, назва посередині наступного рядка, шрифт як у тексті, інтервал ≥ 1,2;
  16) таблиці не розриваються між сторінками (рядки та вся таблиця тримаються разом), рядок
      заголовків повторюється;
  17) формули посередині, номер у круглих дужках праворуч;
  18) тире «–», без довгого тире (перевіряється перед збереженням).

Залежності: python-docx >= 1.1 (pip install python-docx).
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

# =====================================================================================================================
# 1. Метадані
# =====================================================================================================================
TEMPLATE_REL = Path("Docs") / "Templates" / "Шаблон_звіту_ПРІ_2026.docx"
TARGET_REL = Path("Docs") / "Звіт_ЛР_Взаємодія_з_Акторами_Ігор_Брайченко.docx"

LAB_NUMBER = 4
COURSE = "Проектування та розробка ігор"
TOPIC = "Взаємодія з Акторами сцени"
GOAL = "Навчитися створювати та налаштовувати різні типи Акторів ігрової сцени"
VARIANT_NO, VARIANT_NAME = 10, "Підводний світ"
STUDENT = ("ст. гр. ПЗ-43", "Ігор БРАЙЧЕНКО")
LECTURER = ("ст. викл. каф. ПЗ", "Тетяна ЦИМБАЛЮК")
EVALUATOR = ("асист. каф. ПЗ", "Олександр БАУСК")
CITY_YEAR = "Львів – 2026"

BODY_FONT, CODE_FONT = "Times New Roman", "Courier New"
BODY_PT, CODE_PT = 14, 10
TABLE_LINE = 1.2                           # п. 15 шаблону: інтервал у таблиці не менше 1,2
INDENT = Cm(1.25)
LIST_LEFT, LIST_HANG = Cm(2.25), Cm(1.0)   # п. 8: відступ 1,25 см + навислий 1 см (як у шаблоні)
TEXT_WIDTH = Mm(210 - 25 - 10)             # 175 мм
CODE_MAX_COLS = 78                         # Courier New 10 pt ≈ 2,12 мм/символ у рамці ~168 мм
CODE_BG, CODE_BORDER = "F3F4F6", "BFBFBF"

# Рисунки: ключ -> (відносний шлях, ширина в см, назва без крапки)
FIGURES = {
    "soma":      ("Claude outputs/SomaLock_front34.png", 15.5,
                  "Модель SM_Breach_SomaLock у вікні перегляду 3ds Max: заклинена стулка, кишеня та гідроциліндри"),
    "scene":     ("Saved/Screenshots/WindowsEditor/lars_editor_hold.png", 16.0,
                  "Оформлена надводна частина сцени: пірс, причал апарата Shell-1, кран LARS "
                  "та станція телепортації A"),
    "lars":      ("Saved/Screenshots/LARS_cinematic_collision_PIE.jpg", 16.0,
                  "Власна модель SK_LARS_RoboticArm у PIE: колізія з персонажем, спуск, захоплення "
                  "та підйом Shell-1"),
    "prompts":   ("Saved/ClaudeExport/optics/prompt_crops.png", 9.5,
                  "Підказки під прицілом: [F] SALVAGE ENERGY (+25%), [F] FULL та [F] SALVAGE AMMO (+32)"),
    "cell":      ("Saved/ClaudeExport/optics/prompt_full.png", 16.0,
                  "Енергоелемент BP_Pickup_EnergyCell у серверному вузлі R5 кластера C-01 під час PIE"),
    "tp_a":      ("Saved/ClaudeExport/optics/start_view_1.png", 16.0,
                  "Станція телепортації A: рамка SomaLock і транзитна шахта зі стартового огляду гравця"),
    "tp_b":      ("Saved/Screenshots/WindowsEditor/Align2_B_user.png", 16.0,
                  "Станція телепортації B: труба шахти співвісна з отвором шлюзу SomaLock"),
    "tp_views":  ("Saved/ClaudeExport/optics/teleport_views.png", 11.0,
                  "Ракурси транзитної системи: гирло станції A, шлюз станції B, вихід у відкриту воду"),
}

# =====================================================================================================================
# 2. Зміст. Розмітка в тексті: _{нижній індекс}, ^{верхній індекс}. (Жирний у тілі звіту не використовується, п. 13.)
# =====================================================================================================================
THEORY = [
    "Усі об’єкти ігрового світу в Unreal Engine 5 побудовані на єдиній ієрархії класів. Її коренем є UObject – "
    "базовий клас системи рефлексії, який забезпечує збирання сміття, серіалізацію, реплікацію та доступ до "
    "властивостей із редактора й Blueprint через макроси UCLASS, UPROPERTY та UFUNCTION. Клас AActor розширює "
    "UObject можливістю існувати на рівні: актор має трансформацію (через кореневий компонент), життєвий цикл "
    "(BeginPlay, Tick, EndPlay) і може бути створений, знищений та реплікований. APawn – актор, яким володіє "
    "контролер (APlayerController або AAIController) і який отримує ввід; ACharacter додає до нього капсулу "
    "колізії, скелетну сітку та UCharacterMovementComponent з готовою логікою ходьби, стрибків і плавання. "
    "У проєкті AOS_DK підводний апарат Shell-1 (AShellPawn) успадковує APawn, оскільки його рух визначають сили "
    "фізичного рушія, а пілот на пірсі (AAdminCharacter) є нащадком ACharacter.",

    "Актор є контейнером компонентів, а його поведінка складається з них за принципом композиції. UActorComponent – "
    "базовий компонент без просторового положення, що містить логіку і стан (таким є, наприклад, власний "
    "UAOSFluidPhysicsComponent). USceneComponent додає трансформацію відносно батьківського компонента та "
    "ієрархічне кріплення (SetupAttachment, сокети). UPrimitiveComponent – нащадок USceneComponent, що має "
    "геометричне представлення для рендерингу та фізики: UStaticMeshComponent, USkeletalMeshComponent, "
    "UBoxComponent, USphereComponent. Саме примітивні компоненти беруть участь у колізіях, генерують події "
    "OnComponentHit і OnComponentBeginOverlap та можуть симулювати фізику. Кореневий компонент визначає "
    "трансформацію всього актора: якщо він симулює фізику, рух актора повністю передається рушію Chaos.",

    "Колізію кожного примітивного компонента описує профіль (Collision Profile), який задає режим (NoCollision, "
    "QueryOnly, PhysicsOnly, QueryAndPhysics), тип об’єкта (Object Type: WorldStatic, WorldDynamic, Pawn, "
    "PhysicsBody, Vehicle тощо) та відгуки (Collision Responses) на кожен канал. Відгук Block зупиняє рух і "
    "трасування та породжує подію Hit; Overlap пропускає об’єкт, але генерує подію перекриття (за ввімкненого "
    "Generate Overlap Events); Ignore повністю виключає взаємодію. Для пари об’єктів діє найменш обмежувальний із "
    "двох відгуків, тому блокування виникає лише тоді, коли обидва об’єкти блокують один одного. Типи об’єктів "
    "описують, чим є сам компонент під час руху, а канали трасування (Trace Channels, наприклад Visibility і "
    "Camera) використовуються лише в запитах – трасуваннях променем і розгортках (sweep), на яких будують "
    "прицілювання, перевірку видимості та фокус взаємодії. Власні профілі й канали оголошують у файлі "
    "Config/DefaultEngine.ini.",

    "Фізичну симуляцію в UE5 виконує рушій Chaos. Компонент з увімкненим Simulate Physics стає твердим тілом "
    "(rigid body), рух якого визначають маса, тензор інерції, центр мас, сили та імпульси. Маса обчислюється з "
    "об’єму простої колізії та густини фізичного матеріалу або задається явно (Mass in Kg Override); тензор інерції "
    "визначає опір обертанню навколо кожної осі, а зміщення центру мас донизу створює відновлювальний момент. "
    "Лінійне та кутове демпфування (Linear/Angular Damping) імітують опір середовища, а фізичний матеріал задає "
    "тертя і пружність контакту. Для стабільної та продуктивної симуляції застосовують прості опуклі оболонки, які в "
    "3ds Max позначають префіксом UCX_ і обмежують 32 вершинами. Сили, що діють у рідині, – архімедова "
    "виштовхувальна сила F_{b} = ρ·g·V_{зан}, пропорційна зануреному об’єму, та гідродинамічний опір (рівняння "
    "Морісона) – Chaos не моделює, тому їх додають програмно через AddForce і AddTorque у фазі такту TG_PrePhysics.",

    "Тригер – це примітивний компонент або об’єм (TriggerBox, UBoxComponent, USphereComponent) у режимі QueryOnly, "
    "який не блокує рух, а реагує на перекриття відгуком Overlap. Подія OnComponentBeginOverlap запускає ігрову "
    "логіку: підбирання предмета, зміну параметрів гравця, старт сценарію. Під час кінематичних переходів (втягування "
    "апарата в шлюз, телепортації) фізичну симуляцію тіла тимчасово вимикають (SetSimulatePhysics(false)), а "
    "трансформацію задають безпосередньо через SetActorLocationAndRotation з типом ETeleportType::TeleportPhysics, "
    "який не породжує фізичних швидкостей і хибних зіткнень. Після завершення переходу симуляцію відновлюють, "
    "задають початкову швидкість, а від циклічного повторного спрацювання тригера захищаються періодом "
    "охолодження (cooldown).",
]

# Дослівний текст завдань із методичних вказівок (номер, текст, підпункти-маркери).
TASK_INTRO = "Відповідно до методичних вказівок до лабораторної роботи необхідно виконати такі завдання:"
TASK_ITEMS = [
    ("1.", "Оформити сцену гри згідно обраного варіанту з використанням готових асетів. Для заміни "
           "ресурсів-заповнювачів використати мінімум 13 різних по своїй формі асетів і розмістити на сцені "
           "сумарно 100+ об’єктів.", []),
    ("2.", "Додати на сцену щонайменше 4 різних об’єкти, які відповідають індивідуальному варіанту та розроблені "
           "самостійно у засобах 3D-моделювання.", []),
    ("3.", "Визначити поведінку для 3-х різних категорій об’єктів:", [
        "нерухомі об’єкти-перешкоди різного розміру і форми, які персонаж повинен обходити (із застосування "
        "колізій різного типу);",
        "2+ типи об’єктів, які персонаж може переміщати по сцені за допомогою різної фізичної взаємодії з ними;",
        "об’єкти, які персонаж може підібрати та змінювати свій ігровий стан – аптечка та сумка/ящик з патронами "
        "(повинні відповідати графічному оформленню гри).",
    ]),
    ("4.", "Забезпечити 2 локації для телепортації гравця на значну відстань по сцені. Використати механізм "
           "тригера для реалізації телепортації.", []),
]
VARIANT_TEXT = (
    f"Обраний варіант графічного оформлення гри – № {VARIANT_NO} «{VARIANT_NAME}». Дія відбувається на "
    "підводній дослідницькій станції AOS-DK: надводна частина – пірс із причалом підводного апарата Shell-1, "
    "підводна – бетонна вежа A з житловим кластером C-01 /home/a03, шахтами та високовольтними "
    "шинопроводами. Гравець пересувається пішки по пірсу та керує апаратом Shell-1 з шістьма ступенями свободи "
    "в товщі води; стилістика – бруталістський бетон, промислове обладнання та неонова палітра Dracula в "
    "інтерфейсі й світлових елементах.")

# ---------------------------------------------------------------------------------------------------------------------
# Фрагменти коду (скорочено, без зміни логіки; рядки ≤ CODE_MAX_COLS символів)
# ---------------------------------------------------------------------------------------------------------------------
CODE_FLUID_COUPLING = r"""
// AOSFluidPhysicsComponent.cpp – зв'язок з хвильовим полем, a = F_wave / m
float UAOSFluidPhysicsComponent::ComputeWaveCoupling(float Mass) const
{
    if (ResponseModel == EAOSFluidResponseModel::VehicleAcceleration)
    {
        return WaveInfluenceScale; // vehicle tuning is in accelerations
    }
    const float M = FMath::Max(Mass, KINDA_SMALL_NUMBER);
    const float Inertia = FMath::Min(1.f, WaveReferenceMassKg / M);

    // Heavy bodies (cargo pods, wrecks): zero forcing at the cutoff mass
    const float Immunity = (WaveImmuneMassKg > 0.f)
        ? 1.f - FMath::SmoothStep(0.5f * WaveImmuneMassKg,
                                  WaveImmuneMassKg, M)
        : 1.f;

    return WaveInfluenceScale * Inertia * Immunity;
}
"""

CODE_FLUID_NEWTON = r"""
// AOSFluidPhysicsComponent.cpp – StepNewtonian(): сили для тіла Chaos
// 1) Archimedes: a = BuoyancyFactor * g * submersion (semi-implicit)
const float MidCenterZ =
    float(Center.Z) + 0.5f * float(Velocity.Z) * PhysicsStep;
const float Sub = FMath::Clamp(
    (SurfaceZ - (MidCenterZ - HalfHeight)) / (2.f * HalfHeight), 0.f, 1.f);
Body->AddForce(FVector(0.f, 0.f, BuoyancyFactor * G * Sub), NAME_None, true);

// 2) Morison drag against the mass-coupled orbital flow
const FVector RelativeVelocity = Velocity - FluidVelocity;
const float DragRate = FMath::Min(
    (FluidDrag + FluidQuadraticDrag * float(RelativeVelocity.Size())) * Sub,
    MaxSafeRate);
Body->AddForce(-RelativeVelocity * DragRate, NAME_None, true);

// 3) Waterline heave damping (fraction of critical for the buoyancy spring)
if (Sub > 0.f && Sub < 1.f && HeaveDampingRatio > 0.f)
{
    const float HeaveOmega =
        FMath::Sqrt(BuoyancyFactor * G / (2.f * HalfHeight));
    const float HeaveRate =
        FMath::Min(2.f * HeaveDampingRatio * HeaveOmega, MaxSafeRate);
    Body->AddForce(FVector(0.f, 0.f, -RelativeVelocity.Z * HeaveRate),
                   NAME_None, true);
}

// 4) Rotational damping, 5) metacentric righting towards the wave normal
const float AngularRate = FMath::Min(AngularFluidDrag * Sub, MaxSafeRate);
Body->AddTorqueInRadians(-S.AngularVelocity * AngularRate, NAME_None, true);
const FVector Axis = FVector::CrossProduct(Body->GetUpVector(), WaveNormal);
Body->AddTorqueInRadians(Axis * (RightingStiffness * Sub), NAME_None, true);
"""

CODE_PICKUP = r"""
// AOSPickupBase.cpp – тригер фокуса та підбирання на [F]
AAOSPickupBase::AAOSPickupBase()
{
    PrimaryActorTick.bCanEverTick = true;

    Trigger = CreateDefaultSubobject<USphereComponent>(TEXT("Trigger"));
    SetRootComponent(Trigger);
    Trigger->InitSphereRadius(150.f);
    Trigger->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Trigger->SetCollisionObjectType(ECC_WorldDynamic);
    Trigger->SetCollisionResponseToAllChannels(ECR_Ignore);
    Trigger->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
    Trigger->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Overlap);
    Trigger->SetCollisionResponseToChannel(ECC_Vehicle, ECR_Overlap);
    Trigger->SetGenerateOverlapEvents(true);

    Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
    Mesh->SetupAttachment(Trigger);
    Mesh->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);

    Glow = CreateDefaultSubobject<UPointLightComponent>(TEXT("Glow"));
    Glow->SetupAttachment(Mesh);
}

void AAOSPickupBase::GetInteractPrompt_Implementation(AActor* InstigatorActor,
    FText& OutAction, bool& bOutAvailable)
{
    const AShellPawn* Shell = Cast<AShellPawn>(InstigatorActor);
    bOutAvailable = !bCollected && Shell && CanApplyPickup(Shell);
    OutAction = bOutAvailable ? GetSalvageLabel()
                              : NSLOCTEXT("AOSPickup", "Full", "FULL");
}

bool AAOSPickupBase::TryCollect(AShellPawn* Shell)
{
    if (bCollected || !IsValid(Shell) || !ApplyPickup(Shell))
    {
        return false;               // core / reserve full: the pickup stays
    }
    bCollected = true;
    Trigger->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Mesh->SetHiddenInGame(true);
    if (CollectSound)
    {
        UGameplayStatics::PlaySoundAtLocation(this, CollectSound,
                                              Mesh->GetComponentLocation());
    }
    BP_OnCollected(Shell);
    // ... Niagara burst CollectFX (User.BubbleRate = 900) ...
    SetLifeSpan(CollectFXTime);     // 0.9 s flash, then Destroy()
    return true;
}
"""

CODE_TELEPORT = r"""
// AOSTeleportStation.cpp – втяг за сплайном Ерміта та перенесення
void AAOSTeleportStation::TickIntake(float DeltaSeconds)
{
    AShellPawn* Shell = TransitShell.Get();
    const float T = IntakeDuration;                       // 1.2 s
    const float t = FMath::Clamp(PhaseTime / T, 0.f, 1.f);
    const float t2 = t * t, t3 = t2 * t;
    const FVector V1 = EntryWorld * IntakeEndSpeed;    // 1000 cm/s, axis
    const FVector P = (2.f * t3 - 3.f * t2 + 1.f) * IntakeStart
                    + (t3 - 2.f * t2 + t) * T * IntakeStartVelocity
                    + (-2.f * t3 + 3.f * t2) * IntakeEnd
                    + (t3 - t2) * T * V1;
    const float Align = FMath::SmoothStep(0.f, 1.f,
        FMath::Clamp(t / AlignFraction, 0.f, 1.f));
    const FQuat Q = FQuat::Slerp(IntakeStartQuat, IntakeTargetQuat, Align);
    Shell->SetActorLocationAndRotation(P, Q.GetNormalized(), false, nullptr,
                                       ETeleportType::TeleportPhysics);
    if (t >= 1.f)
    {
        Phase = EAOSTransitPhase::FadeOut;
        PhaseTime = 0.f;
        if (APlayerCameraManager* Cam = AOSTransit::CameraOf(Shell))
        {
            Cam->StartCameraFade(0.f, 1.f, FadeDuration,
                                 FLinearColor::Black, false, true);
        }
    }
}

void AAOSTeleportStation::CompleteWarp()
{
    AShellPawn* Shell = TransitShell.Get();
    AAOSTeleportStation* Target = TransitTarget.Get();
    // Anti-loop first: overlaps generated by the warp itself are ignored
    Target->ApplyArrivalCooldown(Target->ArrivalCooldown);            // 3.0 s

    const USceneComponent* Exit = Target->GetExitPoint();
    Shell->SetActorLocationAndRotation(Exit->GetComponentLocation(),
        Exit->GetComponentRotation(), false, nullptr,
        ETeleportType::TeleportPhysics);
    ReleaseShell(Shell, Target->GetExitVelocity());    // physics, 500 cm/s
    // ... StartCameraFade(1, 0, 0.8 s), SetBlockControls(false), log ...
}
"""

# =====================================================================================================================
# 3. Низькорівневі помічники (з дотриманням порядку елементів схеми OOXML)
# =====================================================================================================================
_MARKUP = re.compile(r"(_\{.+?\}|\^\{.+?\})")

PPR_ORDER = ["pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
             "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
             "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid",
             "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc", "textDirection",
             "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr", "pPrChange"]
TBLPR_ORDER = ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize", "tblStyleColBandSize",
               "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook",
               "tblCaption", "tblDescription"]


def insert_ordered(parent, child, order):
    """Вставляє child у parent з урахуванням порядку дочірніх елементів, визначеного схемою."""
    tag = child.tag.split("}")[1]
    for old in parent.findall(qn(f"w:{tag}")):
        parent.remove(old)
    idx = order.index(tag)
    for successor in order[idx + 1:]:
        found = parent.find(qn(f"w:{successor}"))
        if found is not None:
            found.addprevious(child)
            return child
    parent.append(child)
    return child


def set_run_font(run, name=BODY_FONT, size=BODY_PT, bold=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = None
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), name)
    return run


def set_mark(p, name=BODY_FONT, size=BODY_PT):
    """Шрифт символу кінця абзацу (визначає висоту порожніх рядків)."""
    ppr = p._p.get_or_add_pPr()
    rpr = OxmlElement("w:rPr")
    rf = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(attr), name)
    rpr.append(rf)
    for t in ("w:sz", "w:szCs"):
        el = OxmlElement(t)
        el.set(qn("w:val"), str(int(size * 2)))
        rpr.append(el)
    insert_ordered(ppr, rpr, PPR_ORDER)


def fmt(p, *, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first=INDENT, left=Cm(0), right=Cm(0), line=1.5,
        keep_next=False, mark=(BODY_FONT, BODY_PT)):
    pf = p.paragraph_format
    pf.alignment = align
    pf.first_line_indent = first
    pf.left_indent = left
    pf.right_indent = right
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    if line == 1.5:
        pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    elif line == 1.0:
        pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    else:
        pf.line_spacing = line            # множник (MULTIPLE)
    pf.widow_control = True
    pf.keep_with_next = keep_next
    set_mark(p, *mark)
    return p


def add_rich(p, text, size=BODY_PT, font=BODY_FONT, bold=None):
    """Текст із розміткою _{sub} та ^{sup}."""
    for part in _MARKUP.split(text):
        if not part:
            continue
        if part.startswith("_{"):
            set_run_font(p.add_run(part[2:-1]), font, size, bold).font.subscript = True
        elif part.startswith("^{"):
            set_run_font(p.add_run(part[2:-1]), font, size, bold).font.superscript = True
        else:
            set_run_font(p.add_run(part), font, size, bold)
    return p


def clear_runs(p):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)


def border_el(tag, edges, color, sz=4, space=0):
    box = OxmlElement(tag)
    for edge in edges:
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), str(space))
        el.set(qn("w:color"), color)
        box.append(el)
    return box


def twips(cm):
    return str(int(round(cm / 2.54 * 1440)))


# =====================================================================================================================
# 4. Побудова документа на основі шаблону
# =====================================================================================================================
class Report:
    def __init__(self, root: Path, template: Path):
        if not template.is_file():
            raise SystemExit(f"Не знайдено шаблон звіту: {template}")
        self.root = root
        self.doc = Document(str(template))
        self.fig_no = self.tab_no = self.formula_no = 0
        self.last_blank = False
        self.missing = []
        self._check_section()
        self._fill_title_page()

    # ------------------------------------------------------------------ шаблон
    def _check_section(self):
        sec = self.doc.sections[0]
        # п. 1 і п. 3: значення шаблону; явно фіксуємо, щоб документ не залежав від версії шаблону
        sec.page_width, sec.page_height = Mm(210), Mm(297)
        sec.left_margin, sec.right_margin = Mm(25), Mm(10)
        sec.top_margin, sec.bottom_margin = Mm(20), Mm(20)
        sec.different_first_page_header_footer = True
        hdr_xml = sec.header._element.xml
        if "PAGE" not in hdr_xml:
            raise SystemExit("У шаблоні немає поля PAGE у верхньому колонтитулі")

    def _find(self, predicate, start=0):
        for i, p in enumerate(self.doc.paragraphs[start:], start):
            if predicate(p.text.strip()):
                return i, p
        raise SystemExit("Шаблон має неочікувану структуру титульного аркуша")

    @staticmethod
    def _set_runs(p, texts):
        """Замінює текст наявних прогонів (зберігаючи їхнє форматування з шаблону)."""
        runs = p.runs
        for r, t in zip(runs, texts):
            r.text = t
        for r in runs[len(texts):]:
            r._element.getparent().remove(r._element)

    def _fill_title_page(self):
        doc = self.doc
        _, p = self._find(lambda t: t.startswith("До лабораторної роботи"))
        self._set_runs(p, [f"До лабораторної роботи № {LAB_NUMBER}"])
        i_topic, p = self._find(lambda t: t.startswith("На тему"))
        self._set_runs(p, [p.runs[0].text, f"“{TOPIC}”"])
        # рядок варіанта – у порожньому центрованому абзаці шаблону під темою (формат як у рядків вище)
        pv = doc.paragraphs[i_topic + 1]
        if pv.text.strip():
            raise SystemExit("Очікувався порожній рядок під темою на титульному аркуші")
        lab = copy.deepcopy(p.runs[0]._element)
        val = copy.deepcopy(p.runs[1]._element)
        pv._p.append(lab)
        pv._p.append(val)
        self._set_runs(pv, ["Варіант: ", f"№ {VARIANT_NO} “{VARIANT_NAME}”"])

        i, _ = self._find(lambda t: t == "Виконав:")
        self._set_runs(doc.paragraphs[i + 1], [STUDENT[0]])
        self._set_runs(doc.paragraphs[i + 2], [STUDENT[1]])
        i, p = self._find(lambda t: t in ("Прийняла:", "Прийняв:"))
        self._set_runs(p, ["Прийняв:"])
        self._set_runs(doc.paragraphs[i + 1], [EVALUATOR[0]])
        self._set_runs(doc.paragraphs[i + 2], [EVALUATOR[1]])
        i, _ = self._find(lambda t: t == "Лектор:")
        self._set_runs(doc.paragraphs[i + 1], [LECTURER[0]])
        self._set_runs(doc.paragraphs[i + 2], [LECTURER[1]])
        self._find(lambda t: t == CITY_YEAR)

        # «Тема роботи» / «Мета роботи» – перші абзаци тіла; все, що нижче, генерується заново
        i_theme, p_theme = self._find(lambda t: t.startswith("Тема роботи"))
        p_goal = doc.paragraphs[i_theme + 1]
        for par, label, text in ((p_theme, "Тема роботи:", f" {TOPIC}."), (p_goal, "Мета роботи:", f" {GOAL}.")):
            clear_runs(par)
            set_run_font(par.add_run(label), bold=True)
            set_run_font(par.add_run(text))
            fmt(par)
        # титульний аркуш завжди закінчується розривом сторінки (у Word він і так заповнений до кінця;
        # pageBreakBefore на першому рядку нової сторінки порожньої сторінки не створює)
        p_theme.paragraph_format.page_break_before = True
        body = doc.element.body
        node = p_goal._p.getnext()
        while node is not None:
            nxt = node.getnext()
            if node.tag != qn("w:sectPr"):
                body.remove(node)
            node = nxt
        self.last_blank = False

        cp = doc.core_properties
        cp.title = f"Звіт до лабораторної роботи № {LAB_NUMBER}: {TOPIC}"
        cp.author = f"{STUDENT[1].title()}, ПЗ-43"
        cp.subject = COURSE
        cp.language = "uk-UA"
        cp.keywords = "Unreal Engine 5, AOS_DK, колізії, Chaos, тригери, телепортація"
        cp.comments = ""

    # ------------------------------------------------------------------ примітиви
    def blank(self, keep_next=False):
        p = fmt(self.doc.add_paragraph(), first=Cm(0), keep_next=keep_next)
        self.last_blank = True
        return p

    def para(self, text, *, keep_next=False):
        p = fmt(self.doc.add_paragraph(), keep_next=keep_next)
        add_rich(p, text)
        self.last_blank = False
        return p

    def list_item(self, marker, text, level=0):
        """п. 8: відступ ліворуч 1,25 см (позиція маркера) + навислий 1 см; вкладений рівень – ще на 1 см."""
        left = LIST_LEFT + Cm(level * 1.0)
        p = fmt(self.doc.add_paragraph(), first=-LIST_HANG, left=left)
        p.paragraph_format.tab_stops.add_tab_stop(left, WD_TAB_ALIGNMENT.LEFT)
        add_rich(p, f"{marker}\t{text}")
        self.last_blank = False
        return p

    def section(self, title):
        """п. 9: порожній рядок перед (якщо не нова сторінка) і після; назва тримається з першим рядком тексту."""
        if not self.last_blank:
            self.blank(keep_next=True)
        p = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.CENTER, first=Cm(0), keep_next=True)
        set_run_font(p.add_run(title.upper()), bold=True)
        self.blank(keep_next=True)
        return p

    def subsection(self, title):
        """п. 10: «N. Назва» жирним, з абзацного відступу, порожній рядок перед, без крапки в кінці."""
        assert not title.endswith("."), title
        if not self.last_blank:
            self.blank(keep_next=True)
        p = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.JUSTIFY, keep_next=True)
        set_run_font(p.add_run(title), bold=True)
        self.last_blank = False
        return p

    def formula(self, text):
        """п. 17: формула посередині рядка, номер у круглих дужках праворуч."""
        self.formula_no += 1
        p = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.LEFT, first=Cm(0))
        stops = p.paragraph_format.tab_stops
        stops.add_tab_stop(Cm(TEXT_WIDTH.cm / 2), WD_TAB_ALIGNMENT.CENTER)
        stops.add_tab_stop(TEXT_WIDTH, WD_TAB_ALIGNMENT.RIGHT)
        add_rich(p, "\t" + text + f"\t({self.formula_no})")
        self.last_blank = False
        return self.formula_no

    def code(self, source):
        """Лістинг: Courier New 10, інтервал 1, без абзацного відступу; суцільна світла рамка з абзаців
        з однаковими межами та заливкою (Word і LibreOffice об'єднують їх в один блок)."""
        lines = source.strip("\n").expandtabs(4).split("\n")
        for ln in lines:
            if len(ln) > CODE_MAX_COLS:
                raise SystemExit(f"Рядок коду довший за {CODE_MAX_COLS} символів: {ln}")
        for ln in lines:
            p = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.LEFT, first=Cm(0), left=Cm(0.2),
                    right=Cm(0.2), line=1.0, mark=(CODE_FONT, CODE_PT))
            ppr = p._p.get_or_add_pPr()
            insert_ordered(ppr, border_el("w:pBdr", ("top", "left", "bottom", "right"), CODE_BORDER, 4, 4),
                           PPR_ORDER)
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), CODE_BG)
            insert_ordered(ppr, shd, PPR_ORDER)
            r = set_run_font(p.add_run(ln), CODE_FONT, CODE_PT)
            if ln.lstrip().startswith("//"):
                r.font.color.rgb = RGBColor(0x4F, 0x62, 0x28)
        self.last_blank = False

    def figure(self, key):
        """п. 14: рисунок окремо посередині, під ним «Рис. N. Назва» без крапки."""
        rel, width_cm, title = FIGURES[key]
        assert not title.endswith(".")
        self.fig_no += 1
        path = self.root / rel
        p = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.CENTER, first=Cm(0), line=1.0, keep_next=True)
        if path.is_file():
            p.add_run().add_picture(str(path), width=Cm(width_cm))
        else:
            self.missing.append(rel)
            set_run_font(p.add_run(f"[рисунок відсутній: {rel}]"))
        cap = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.CENTER, first=Cm(0))
        set_run_font(cap.add_run(f"Рис. {self.fig_no}. {title}"))
        self.last_blank = False
        return self.fig_no

    def table(self, title, header, rows, widths_cm, align_cols=None):
        """п. 15–16: «Таблиця N.» праворуч, назва посередині, шрифт 14, інтервал 1,2; таблиця не розривається."""
        assert abs(sum(widths_cm) - TEXT_WIDTH.cm) < 0.05, (title, sum(widths_cm))
        self.tab_no += 1
        c1 = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.RIGHT, first=Cm(0), keep_next=True)
        set_run_font(c1.add_run(f"Таблиця {self.tab_no}."))
        c2 = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.CENTER, first=Cm(0), keep_next=True)
        set_run_font(c2.add_run(title))

        t = self.doc.add_table(rows=1 + len(rows), cols=len(header))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        tblpr = t._tbl.tblPr
        tblw = OxmlElement("w:tblW")
        tblw.set(qn("w:w"), twips(sum(widths_cm)))
        tblw.set(qn("w:type"), "dxa")
        insert_ordered(tblpr, tblw, TBLPR_ORDER)
        insert_ordered(tblpr, border_el("w:tblBorders",
                                        ("top", "left", "bottom", "right", "insideH", "insideV"), "000000"),
                       TBLPR_ORDER)
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        insert_ordered(tblpr, layout, TBLPR_ORDER)
        mar = OxmlElement("w:tblCellMar")
        for edge, val in (("top", 0), ("left", 85), ("bottom", 0), ("right", 85)):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:w"), str(val))
            el.set(qn("w:type"), "dxa")
            mar.append(el)
        insert_ordered(tblpr, mar, TBLPR_ORDER)
        for gc, w in zip(t._tbl.tblGrid.findall(qn("w:gridCol")), widths_cm):
            gc.set(qn("w:w"), twips(w))

        all_rows = [header] + rows
        for i, row in enumerate(all_rows):
            tr = t.rows[i]
            trpr = tr._tr.get_or_add_trPr()
            trpr.append(OxmlElement("w:cantSplit"))          # рядок не розривається
            if i == 0:
                th = OxmlElement("w:tblHeader")               # повтор заголовка
                th.set(qn("w:val"), "true")
                trpr.append(th)
            last_row = i == len(all_rows) - 1
            for j, txt in enumerate(row):
                cell = tr.cells[j]
                cell.width = Cm(widths_cm[j])
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                p = cell.paragraphs[0]
                a = WD_ALIGN_PARAGRAPH.CENTER if i == 0 else (align_cols or {}).get(j, WD_ALIGN_PARAGRAPH.LEFT)
                # keep_with_next у всіх рядках, крім останнього: таблиця переноситься цілою
                fmt(p, align=a, first=Cm(0), line=TABLE_LINE, keep_next=not last_row)
                add_rich(p, txt)
        self.last_blank = False
        return self.tab_no

    # ------------------------------------------------------------------ тіло звіту
    def build(self):
        self.section("Теоретичні відомості")
        for t in THEORY:
            self.para(t)

        self.section("Завдання")
        self.para(TASK_INTRO)
        for marker, text, bullets in TASK_ITEMS:
            self.list_item(marker, text)
            for b in bullets:
                self.list_item("●", b, level=1)
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

    # ------------------------------------------------------------------ завдання 1
    def step_1(self):
        self.subsection("1. Оформлення сцени гри та заміна ресурсів-заповнювачів")
        self.para(
            "Роботу виконано на рівні Lvl_FirstPerson проєкту AOS_DK (Unreal Engine 5.7.4). Сцену оформлено "
            "готовими асетами з бібліотек Quixel Megascans, Fab і LevelPrototyping. Перед наповненням проведено "
            "аудит ресурсів середовища за метаданими Asset Registry: видалено 255 невикористаних або стилістично "
            "невідповідних ресурсів (близько 1,9 ГБ) – демонстраційні об’єкти Quixel, плоскі заготовки-коробки, "
            "надлишкові варіанти мегасканів, органічні трави й дерев’яні поверхні, що не пасують до бетонної "
            "станції. Ресурс видалявся лише тоді, коли всі посилання на нього знаходилися всередині множини "
            "видалення, а захищені теки (власні моделі, вихідні файли, підводний апарат) не змінювалися.")
        self.para(
            "Для заміни ресурсів-заповнювачів використано 17 готових асетів різної форми (табл. 1), що перевищує "
            "вимогу щодо 13 форм, а разом із примітивами LevelPrototyping (коробка, клин, циліндр, чверть "
            "циліндра, площина) бібліотека сцени містить 22 різні форми. Сумарно на сцені розміщено понад 170 "
            "об’єктів оформлення (вимога – 100+): опори й перекриття пірса, колони, балки, сходові марші, діжки, "
            "палети, контейнер, уламки бетону, кабельні траси, світильники, кнехти.")
        self.table(
            "Готові асети, використані для заміни ресурсів-заповнювачів",
            ["№", "Форма", "Асет"],
            [
                ["1", "Плита перекриття", "SM_Concrete_Floor_Level1/2"],
                ["2", "Кругла колона", "Pillar_Concrete_Round_01"],
                ["3", "Квадратна колона", "Pillar_Square_Concrete_Stained_01"],
                ["4", "Сходовий марш", "Stairs_Concrete_Worn_01"],
                ["5", "Балка перекриття", "Beams_Ceiling_Concrete_Rough_01"],
                ["6", "Металева діжка", "Container_Drum_Metal_Worn_02"],
                ["7", "Палета", "Pallet_Wood_Worn_01"],
                ["8", "Морський контейнер", "SM_UsedContainer_Shell"],
                ["9", "Шлакоблок", "Cinder_Block_Chipped_02"],
                ["10", "Уламки бетону", "Debris_Concrete_Broken_01–06"],
                ["11", "Плита-уламок", "Broken_Concrete_Slab"],
                ["12", "Мішок з уламками", "Storeage_Sack_Debris_M_01"],
                ["13", "Кабельна траса", "Electrical_Wiring_Set, Power_Cable"],
                ["14", "Кутовий кабельний лоток", "SM_CableTray_Corner"],
                ["15", "Фланець труби", "SM_PipeFlange_Angled"],
                ["16", "Підвісний світильник", "Light_Ceiling_Metal_Hanging_02"],
                ["17", "Швартовий кнехт", "Wooden_Bollard"],
            ],
            [1.2, 6.3, 10.0],
            {0: WD_ALIGN_PARAGRAPH.CENTER},
        )
        self.para(
            "Невідповідні стилю «замкові» сходи Castle_Stairs (2 актори) і цегляну арку Brick_Ruin_Door_Arch "
            "замінено бетонними SM_Stairs_Concrete_Brutalist і SM_Concrete_Arch_Brutalist безпосередньо в наявних "
            "акторах: напрямок підйому сходів визначено трасуваннями згори вниз, масштаб підібрано так, щоб нова "
            "сітка точно заповнювала світовий AABB старої (похибка 0,0 см), а вихідну сітку та трансформацію "
            "збережено в тегах AOS_LegacyMesh і AOS_LegacyXform для можливості відкату. Окремо в 3ds Max побудовано "
            "модульний набір із 28 статичних сіток (труби, хомути, серверні шафи, кабельні лотки, решітчасті містки, "
            "гермодвері, двотаврові балки, вентиляційні короби) з колізією UCX і сокетами для стикування.")
        self.para(
            "Скриптом Tools/setup_macro_topology.py розгорнуто макрокаркас вежі A: опорні точки двох шпилів A-0, "
            "площину кільцевої шини (Z = −90 000 см), якірні точки кластерів C-01…C-05, шахту доку Socket "
            "діаметром 60 м, магістральний шинопровід D-1 із шести сегментів та 24-гранну оболонку-обмежувач рівня "
            "з KillZ = −175 000 см. Кожен актор позначено тегом AOS_MacroID, тому скрипт є ідемпотентним: повторний "
            "запуск вирівнює наявні актори за специфікацією, а не дублює їх.")
        self.para(
            "Кластер C-01 /home/a03 зібрано скриптом Tools/setup_cluster_a03.py навколо якоря ANC_A3_home_a03 "
            "(−48 000; 22 000; −9 800 см). Шість приміщень (табл. 2) утворені 86 бетонними оболонками, 19 порталами "
            "та 6 об’ємами-кімнатами з тегами AOS_RoomID і AOS_DirectoryPath. Стіни й перекриття завтовшки 100 см "
            "отримано відніманням коробок «конструкція – повітря – вже розміщені елементи», тому елементи не "
            "перетинаються і не мають копланарних граней, а матеріал M_AOS_Concrete_BoxMap проєктує текстуру в "
            "локальних сантиметрах кластера без розтягування на масштабованих коробках.")
        self.table(
            "Приміщення кластера C-01 /home/a03",
            ["Приміщення", "Шлях", "Розмір, см", "Підлога"],
            [
                ["R1 – вестибюль", "/home/a03/lobby", "2400 × 3200 × 1350", "B + 0"],
                ["R2 – капсули", "/home/a03/capsules", "2000 × 2000 × 4500", "B + 0"],
                ["R3 – відпочинок", "/home/a03/rec", "4000 × 2800 × 1350", "B + 900"],
                ["R4 – їдальня", "/var/a03/canteen", "1600 × 2400 × 900", "B + 0"],
                ["R5 – сервери", "/sys/a03/node", "3200 × 2400 × 900", "B + 3600"],
                ["R6 – диспетчерська", "/sys/a03/dispatch", "2000 × 1200 × 600", "B + 3600"],
            ],
            [4.6, 4.6, 5.3, 3.0],
            {2: WD_ALIGN_PARAGRAPH.CENTER, 3: WD_ALIGN_PARAGRAPH.CENTER},
        )
        self.para(
            "Прохідність перевірено розгортками об’єктного запиту WorldStatic коробкою 400 × 200 × 200 см і "
            "сферою радіусом 245 см (габарити апарата Shell-1) уздовж усього маршруту «зовні – SomaLock – R1 – R2 – "
            "R5 – R6» та додаткових проходів: жодного зіткнення. Контрольні розгортки, зміщені в опори арок, "
            "суцільні стіни та перемички, навпаки, очікувано фіксують зіткнення, що підтверджує коректність тесту.")

    # ------------------------------------------------------------------ завдання 2
    def step_2(self):
        self.subsection("2. Розробка та розміщення 4-х власних 3D-моделей")
        self.para(
            "Чотири власні моделі, що відповідають варіанту «Підводний світ», побудовано процедурно скриптами "
            "pymxs (Tools/max_build_*.py) у 3ds Max 2027, тому сітку, колізію та специфікацію сокетів можна "
            "повністю відтворити одним запуском. Одиниці – сантиметри, вісь Z спрямована вгору. Експорт виконано "
            "у бінарний FBX із групами згладжування, імпорт – легасі-імпортером FBX (на час імпорту "
            "Interchange.FeatureFlags.Import.FBX = 0), оскільки Interchange відкидає оболонки UCX. Для кожної "
            "моделі виконано UV-розгортку Flatten без перекритих граней, увімкнено Nanite, призначено "
            "PBR-екземпляри матеріалу M_AOS_HeroSurface та автоматично перевірено межі, кількість опуклих "
            "елементів, сокети й слоти матеріалів. Характеристики моделей і їх розміщення на сцені наведено в "
            "таблиці 3.")
        self.table(
            "Власні 3D-моделі та їх розміщення на сцені",
            ["Модель", "Габарити, см", "Колізія", "Розміщення"],
            [
                ["SK_LARS_RoboticArm", "1683 × 304 × 360", "форми на 12 кістках", "пірс, причал Shell-1"],
                ["SM_Breach_SomaLock", "1143 × 1945 × 1209", "18 UCX", "вхід C-01, рамки станцій A і B"],
                ["SM_GIS_BusCoupler", "6000 × 8800 × 8800", "23 UCX", "магістраль D-1 (6 сегментів)"],
                ["SM_Cargo_Pod_Phys", "400 × 188 × 207", "1 UCX (32 вершини)", "їдальня R4, гирло D-1 (3 шт.)"],
            ],
            [5.3, 4.4, 3.3, 4.5],
            {1: WD_ALIGN_PARAGRAPH.CENTER},
        )

        self.subsection("2.1. Артикульована рука крана SK_LARS_RoboticArm")
        self.para(
            "Кран LARS (Launch and Recovery System) призначений для спуску апарата Shell-1 з пірса на воду та його "
            "підйому. Модель складається зі 195 деталей із фасками (14 814 вершин, 28 852 трикутники); у прив’язній "
            "позі рука витягнута вздовж осі +X, а її розмах від осі повороту становить 14,45 м до центру захвату і "
            "15,05 м до кінчиків щелеп. Скелет містить 12 кісток: Root, Base_Yaw (поворот платформи), "
            "Shoulder_Pitch, Elbow_Pitch, Wrist_Pitch, Wrist_Roll, дві щелепи Jaw_L і Jaw_R та чотири кістки "
            "гідроциліндрів (корпус і шток для плеча та ліктя). Застосовано жорсткий скіннінг – рівно один вплив на "
            "вершину, а всі основні суглоби мають нульове обертання в прив’язній позі, тому значення прямої "
            "кінематики відповідають каналам FRotator без перерахунку.")
        self.para(
            "Анімацію реалізовано нативним проксі ULARSArmAnimInstance, що виконується в робочому потоці: спершу "
            "пряма кінематика суглобів, потім Aim-орієнтація пар «корпус – шток» гідроциліндрів, коли кожна деталь "
            "отримує мінімальний поворот, який суміщає її вісь із лінією «цапфа – вушко». Під час PIE похибка "
            "співвісності циліндрів становила 0,00°, мінімальне перекриття телескопа – 35,9 см. Актор ALARSDockArm, "
            "встановлений на пірсі біля причалу, виконує сценарій утримання, спуску (Z 500 → −300 см зі швидкістю "
            "140 см/с) і підйому апарата з плоскою інверсною кінематикою та кінематографічною камерою LaunchCam.")

        self.subsection("2.2. Деформований шлюз SOMA-типу SM_Breach_SomaLock")
        self.para(
            "Броньований шлюз SOMA-типу є головним входом до кластера C-01 і рамкою обох станцій телепортації. "
            "Модель містить фланці зовнішнім діаметром 1200 см з отвором Ø 820 см, камеру завдовжки 600 см з "
            "обручами жорсткості та 12 радіальними косинками, титанову стулку Ø 860 × 80 см, заклинену на 60 % ходу "
            "(зміщення центру 516 см), деформовану кромку кишені стулки та два пошкоджені гідроциліндри – зігнутий "
            "і розірваний, які візуально пояснюють заклинювання (рис. 1). Вільний прохід утворює вписане коло "
            "перетину отвору (R 410 см) і стулки (R 430 см), діаметр якого становить 496 см; для Shell-1 з "
            "півдіагоналлю перерізу 141 см залишається запас 107 см з усіх боків.")
        self.figure("soma")
        self.para(
            "Колізію утворюють 18 опуклих оболонок UCX: 12 клепок тунелю через кожні 30°, 16-кутна призма стулки "
            "(32 вершини), корпус кишені, дві напрямні та два корпуси циліндрів. Дрібні деталі (шланги, світлова "
            "панель, болти, термінальна плата) колізії не мають і розміщені поза отвором. Розгортка коробки Shell-1 "
            "та сфери R 240 см уздовж осі проходу, а також 72 трасування по колу R 245 см зіткнень не виявили, тоді "
            "як контрольна сфера R 256 см очікувано зачіпає оболонку стулки.")

        self.subsection("2.3. Високовольтний шинопровід SM_GIS_BusCoupler")
        self.para(
            "Модель відтворює сегмент елегазового шинопроводу (GIS) у масштабі вежі: литий алюмінієвий корпус "
            "зовнішнім діаметром 8000 см (80 м) із товщиною стінки 150 см, мідний провідник Ø 2830 см, фланці "
            "Ø 8800 см із 96 болтами, 64 поздовжні ребра охолодження, епоксидний опорний ізолятор із шести спиць на "
            "конусі 26°, оглядові люки та патрубок запобіжної мембрани. Між провідником і корпусом утворено "
            "коаксіальний кільцевий канал R 1504…3776 см, яким апарат рухається з повними шістьма ступенями "
            "свободи, а шість вікон ізолятора дають осьові проходи з чистим радіусом не менше 992 см. Сегмент "
            "завдовжки 60 м має сокети SOCKET_Snap_Front/Rear, тому шість сегментів без зазорів стикуються в "
            "магістраль D-1.")
        self.para(
            "Колізія складається з 23 оболонок UCX: 16 клепок корпусу, 16-кутної призми провідника та 6 оболонок "
            "спиць ізолятора. Аналітична перевірка в 3ds Max показала 0 вершин рендер-сітки поза оболонками і 0 "
            "вершин усередині проходів, а в UE виконано 18 осьових розгорток коробки Shell-1 (крен 0°, 45°, 90°) та "
            "432 кільцеві розгортки сфери R 245 см – без жодного зіткнення.")

        self.subsection("2.4. Важкий фізичний контейнер SM_Cargo_Pod_Phys")
        self.para(
            "Герметичний вантажний контейнер є основним фізичним рухомим об’єктом сцени. Корпус – восьмикутна призма "
            "(164 см між гранями) з торцевими куполами, чотирма ребрами, гумовими бамперами, буксирними вушками, "
            "люком із клапаном, магнітною плитою захоплення та полозами з гумовими накладками; габарити "
            "400 × 188 × 207 см, 13 252 трикутники. Колізія навмисно складається з однієї опуклої оболонки на 32 "
            "вершини: плоска нижня грань 344 × 146 см на рівні полозів не дає контейнеру котитися, а скошені носи "
            "дозволяють наїжджати на краї доків, не застрягаючи. Центр мас розташований на 17,1 см нижче осі "
            "корпусу через масу полозів, що створює природний самовідновлювальний момент. Три екземпляри "
            "контейнера розміщено в їдальні R4 та на дні гирла магістралі D-1.")

    # ------------------------------------------------------------------ завдання 3
    def step_3(self):
        self.subsection("3. Поведінка 3-х категорій об’єктів сцени")
        self.para(
            "Класи інтерактивних акторів розміщено в модулі Source/AOS_DK/Gameplay/Interactables/, а їхні "
            "Blueprint-нащадки – у теці /Game/AOS_DK_Game/Gameplay/Interactables/. Скрипт "
            "Tools/deploy_interactables_c01.py ідемпотентно розставив 14 акторів у приміщеннях кластера C-01, "
            "магістралі D-1 і шахті Socket, визначаючи рівень підлоги трасуваннями WorldStatic. Параметри акторів "
            "наведено в таблиці 4.")
        self.table(
            "Інтерактивні актори трьох категорій",
            ["Актор", "Колізія", "Параметри"],
            [
                ["BP_Obstacle_Bulkhead", "BlockAll, UBX", "1520 × 120 × 1250 см"],
                ["BP_Obstacle_CableTangle", "AOS_SoftFoliage", "швидкість × 0,5 на 3 с"],
                ["BP_Phys_CargoPod", "PhysicsActor, UCX", "1500 кг; B = 0,4; μ = 0,3"],
                ["BP_Phys_BuoyantDrum", "PhysicsActor", "45 кг; B = 3,5"],
                ["BP_Pickup_EnergyCell", "сфера R 150", "+25 % енергії"],
                ["BP_Pickup_TorpedoMagazine", "сфера R 150", "+32 торпеди"],
            ],
            [6.5, 4.3, 6.7],
        )

        self.subsection("3.1. Нерухомі об’єкти-перешкоди")
        self.para(
            "Клас AAOSStaticObstacle – актор зі статичною сіткою-коренем у профілі BlockAll і статичною "
            "мобільністю. Його нащадок BP_Obstacle_Bulkhead (плита 1520 × 120 × 1250 см з ребрами та помаранчевою "
            "сигнальною смугою) має просту колізію-коробку UBX і встановлений у вестибюлі R1 так, що перекриває пряму "
            "лінію від шлюзу SomaLock до арки капсульного атріуму: гравець має обходити його через бічні проходи "
            "шириною 990 та 690 см.")
        self.para(
            "Друга перешкода, BP_Obstacle_CableTangle (клубок із 21 обірваного кабелю, 435 × 745 × 540 см), "
            "використовує власний профіль AOS_SoftFoliage, оголошений у DefaultEngine.ini: QueryOnly, тип "
            "WorldDynamic, Overlap для Pawn, PhysicsBody, Vehicle і Projectile, Ignore для решти каналів. Вона не "
            "блокує рух, а заплутує апарат: під час входу його швидкість одразу зменшується вдвічі, а протягом 3 с "
            "діє додатковий лінійний опір")
        n = self.formula("k = d · f / (1 − f),")
        self.para(
            f"де d – коефіцієнт гідродинамічного опору апарата, f = 0,5 – частка гасіння швидкості. Формула ({n}) "
            "забезпечує, що усталена швидкість під тягою зменшується саме в (1 − f) раз, тому клубок вигідніше "
            "обійти. Після звільнення діє 2-секундний захист від повторного захоплення. Перешкода має тег "
            "AOS.FuseTarget і міцність 40 одиниць, тому три влучання мікроторпед (по 14 одиниць) перерізають кабелі "
            "і знищують актор.")
        self.para(
            "Великі нерухомі перешкоди сцени також мають колізії різного типу: шлюз SomaLock – 18 опуклих оболонок "
            "UCX, сегменти шинопроводу – 23 UCX, транзитні шахти телепортації – складну колізію (Use Complex As "
            "Simple), кран LARS – коробки й капсули, прикріплені до кісток, а стіни кластера – прості коробки "
            "BlockAll. Таким чином, перешкоди відрізняються як розміром (від 4 до 88 м), так і формою та типом "
            "колізії.")

        self.subsection("3.2. Об’єкти, які гравець переміщує фізичною взаємодією")
        self.para(
            "Обидва фізичні актори успадковують AAOSPhysicsProp, у якому коренем є сітка з профілем PhysicsActor та "
            "увімкненим Simulate Physics, а поведінку у воді задає універсальний компонент UAOSFluidPhysicsComponent "
            "(нащадок UActorComponent, такт TG_PrePhysics). Компонент виокремлено з класу AShellPawn без дублювання "
            "коду: аналітичний стан моря складається з чотирьох гармонік Герстнера (амплітуди 10–200 см, довжини "
            "хвиль 8–140 м, домінантний напрямок 35°) з глибоководною дисперсією ω = √(g·k). Для апарата компонент "
            "працює в режимі VehicleAcceleration (точне перенесення попередньої гідродинаміки), а для предметів – у "
            "режимі Newtonian, де вагу m·g задає рушій, а компонент додає силу Архімеда, опір Морісона, демпфування "
            "вертикальних коливань і метацентричний відновлювальний момент.")
        self.para(
            "Ключова ідея ньютонівської моделі – залежність впливу хвиль від маси тіла: хвиля діє з силою, "
            "характерною для тіла референтної маси, тому прискорення a = F/m зменшується для важких тіл. "
            "Коефіцієнт зв’язку з хвильовим полем обчислюється як")
        n_c = self.formula("C(m) = s · min(1, m_{0} / m) · (1 − smoothstep(0,5·M_{i}, M_{i}, m)),")
        self.para(
            "де s – множник WaveInfluenceScale, m_{0} = 50 кг – референтна маса, M_{i} = 1000 кг – маса імунітету, "
            "за якої вплив хвиль дорівнює нулю. Коефіцієнт масштабує орбітальну швидкість води, підйом поверхні та "
            "нахил нормалі хвилі. Прискорення від виштовхувальної сили")
        n_b = self.formula("a_{b} = B · g · σ,")
        self.para(
            "де B – коефіцієнт плавучості (BuoyancyFactor), σ – частка занурення, яку обчислюють у середині кроку "
            "симуляції (напівнеявна схема), щоб пружина ватерлінії не накопичувала енергію. За B < 1 тіло тоне, а "
            f"за B > 1 спливає і плаває із зануренням σ = 1/B. Реалізацію формули ({n_c}) наведено нижче:")
        self.code(CODE_FLUID_COUPLING)
        self.para(
            f"Сили, що відповідають формулі ({n_b}), опору Морісона та стабілізації, додаються до тіла Chaos як "
            "прискорення (AddForce з bAccelChange = true), тому не залежать від маси. Крок обмежується значенням "
            "MaxPhysicsDeltaTime, а коефіцієнти опору – величиною 0,5/Δt, що гарантує стійкість явної схеми:")
        self.code(CODE_FLUID_NEWTON)
        self.para(
            "Два типи об’єктів переміщуються різною фізичною взаємодією. BP_Phys_CargoPod масою 1500 кг лежить на "
            "дні (B = 0,4), хвилі на нього не діють (C(m) = 0), а гравець зсуває його контактним ударом корпусу "
            "апарата: рух визначають імпульс зіткнення та тертя ковзання полозів (фізичний матеріал "
            "PM_AOS_CargoSkid, тертя 0,3/0,35, комбінування Min). BP_Phys_BuoyantDrum – діжка 57 × 62 × 88 см "
            "масою 45 кг (C(m) = 1) з B = 3,5 рухається завдяки плавучості: три діжки на ватерлінії шахти Socket "
            "гойдаються на хвилях Герстнера та дрейфують за орбітальною швидкістю води, апарат легко відштовхує їх, "
            "а дві діжки в залі R3 спливають і зупиняються під стелею.")

        self.subsection("3.3. Об’єкти зміни ігрового стану: аптечка та ящик з набоями")
        self.para(
            "Роль аптечки в грі виконує енергоелемент BP_Pickup_EnergyCell: енергія ядра апарата "
            "(UShellEnergyComponent) одночасно є його запасом міцності – влучання ворогів віднімають відсотки "
            "енергії, а її вичерпання запускає аварійний режим Kernel Panic. Енергоелемент додає 25 % енергії через "
            "AddEnergy і виводить у термінальний журнал «core: energy cell absorbed +25%». Роль ящика з набоями "
            "виконує магазин торпед BP_Pickup_TorpedoMagazine, який знаходить у відсіку дрон ASubDrone_Attacker і "
            "додає 32 мікроторпеди до резерву. Обидва предмети мають власні процедурні сітки (енергоелемент 88 см, "
            "каністра 160 см) з емісійними вставками кольорів палітри Dracula, яку використовує HUD гри, тому вони "
            "відповідають графічному оформленню. Якщо ядро або резерв повні, предмет залишається на місці.")
        self.para(
            "Абстрактний клас AAOSPickupBase реалізує інтерфейс IInteractable і містить сферу-тригер R 150 см "
            "(QueryOnly, WorldDynamic, Overlap лише для Pawn, PhysicsBody і Vehicle, оскільки коренем Shell-1 є "
            "коробка типу PhysicsBody), сітку без колізії та точкове світло; предмет погойдується (амплітуда 12 см, "
            "0,35 Гц) і обертається (35°/с). Підбирання відбувається явною взаємодією на клавішу [F] (дія "
            "IA_Interact системи Enhanced Input): AShellPawn з частотою 30 Гц визначає фокус у радіусі 800 см "
            "трасуванням каналу Visibility від камери та розгорткою об’єктного типу WorldDynamic сферою R 25 см, яка "
            "знаходить сфери-тригери предметів (вони не блокують жоден канал трасування і не заважають "
            "прицілюванню). Віджет прицілу виводить підказку «[F] SALVAGE ENERGY (+25%)» або «[F] SALVAGE AMMO "
            "(+32)», а якщо застосування неможливе – «[F] FULL» із прозорістю 0,4. У разі успіху TryCollect вимикає "
            "колізію, ховає сітку, програє звук і ефект бульбашок Niagara та знищує актор через 0,9 с:")
        self.code(CODE_PICKUP)

    # ------------------------------------------------------------------ завдання 4
    def step_4(self):
        self.subsection("4. Телепортація між двома віддаленими локаціями")
        self.para(
            "Клас AAOSTeleportStation (Source/AOS_DK/Gameplay/Teleport/) реалізує двосторонню евакуаційну транзитну "
            "шахту. Його компоненти: SceneRoot; PortalFrame – сітка SM_Breach_SomaLock у профілі BlockAll; ShaftMesh – "
            "процедурна труба SM_AOS_TransitShaft завдовжки 2400 см із ребрами й світловими напрямними; "
            "EntranceTrigger – UBoxComponent у режимі QueryOnly типу WorldDynamic з Overlap лише для Pawn, PhysicsBody "
            "і Vehicle; ExitPoint; редакторські стрілки входу та виходу і блакитне світло гирла. Станції пов’язуються "
            "взаємно через TSoftObjectPtr<AAOSTeleportStation> LinkedStation, а функція ApplyLayout у "
            "OnConstruction автоматично розташовує рамку, тригер і точку виходу на осі проходу, а трубу – співвісно "
            "з отвором рамки з радіальним масштабом FrameBoreRadius / ShaftOuterRadius = 410 / 370 = 1,1105.")
        self.para(
            "Дві локації телепортації розміщено на значній відстані одна від одної. Станцію A «Surface Socket "
            "[ETS-A]» встановлено біля шахти доку Socket з гирлом на Z = −1800 см і вертикальним напрямком входу "
            "Down; станцію B «Tower A C-01 SomaLock [ETS-B]» – за 32 м на захід від головного шлюзу кластера C-01, "
            "з гирлом на Z = −8750 см і напрямком Up. Відстань між точками виходу становить 236 м, перепад висот – "
            "85,5 м. Глибину гирла A вибрано так, щоб імпульс виходу 500 см/с угору (близько 3,3 м інерційного руху) "
            "не виносив апарат на поверхню. Для станцій із горизонтальною шахтою додатково реалізовано режим "
            "EAOSTransitDirection::Forward.")
        n_h = self.formula_no + 1
        self.para(
            "Телепортація запускається механізмом тригера. Перекриття EntranceTrigger викликає BeginTransit, який "
            "перевіряє, що апаратом керує гравець, ядро не зупинене, станція призначення вільна і не перебуває в "
            "періоді охолодження; потім блокує керування (SetBlockControls) і вимикає фізичну симуляцію корпусу. "
            "Протягом 1,2 с апарат кінематично втягується в трубу за кубічним сплайном Ерміта, що зберігає вхідну "
            "швидкість (не більше 1500 см/с) і завершується на осі шахти зі швидкістю 1000 см/с, а ніс апарата "
            "плавно повертається на вісь (slerp):")
        self.formula("P(t) = (2t^{3} − 3t^{2} + 1)·P_{0} + (t^{3} − 2t^{2} + t)·T·V_{0} + "
                     "(−2t^{3} + 3t^{2})·P_{1} + (t^{3} − t^{2})·T·V_{1},")
        self.para(
            "де P_{0}, V_{0} – положення та швидкість апарата на вході, P_{1}, V_{1} – кінцева точка на осі шахти та "
            "швидкість уздовж неї, T = 1,2 с, t ∈ [0; 1]. Далі камера затемнюється (StartCameraFade 0 → 1 за 0,8 с), "
            "апарат продовжує ковзати шахтою з уповільненням, після чого CompleteWarp спершу накладає на станцію "
            "призначення період охолодження 3 с, переносить апарат у ExitPoint з ETeleportType::TeleportPhysics, "
            "вмикає фізику з імпульсом 500 см/с назовні, знімає затемнення та розблоковує керування. Кожен етап "
            "дублюється в термінальний журнал HUD повідомленнями «transit: decompression seal locked – routing to "
            "<станція>» і «transit: arrived at <станція> – 6DOF restored». Параметри послідовності наведено в "
            "таблиці 5.")
        self.table(
            "Параметри послідовності телепортації",
            ["Властивість", "Значення", "Призначення"],
            [
                ["IntakeDuration", "1,2 с", "кінематичне втягування"],
                ["IntakeEndSpeed", "1000 см/с", "швидкість на осі шахти"],
                ["MaxCarriedEntrySpeed", "1500 см/с", "межа вхідної швидкості"],
                ["FadeDuration", "0,8 с", "затемнення камери"],
                ["ExitSpeed", "500 см/с", "імпульс виходу"],
                ["ArrivalCooldown", "3,0 с", "захист від зациклення"],
                ["TriggerDepth", "500 см", "глибина тригера"],
                ["ExitClearance", "300 см", "відступ виходу від тригера"],
            ],
            [6.2, 3.6, 7.7],
            {1: WD_ALIGN_PARAGRAPH.CENTER},
        )
        self.para(f"Реалізацію формули ({n_h}) та перенесення апарата наведено у фрагменті коду:")
        self.code(CODE_TELEPORT)
        self.para(
            "Захист від зациклення реалізовано порядком дій: період охолодження накладається на станцію призначення "
            "до перенесення, тому перекриття, яке породжує сам переніс, ігнорується, а точку виходу розміщено за "
            "300 см від тригера. Аварійний шлях AbortTransit відновлює фізику, керування та затемнення, якщо апарат "
            "або станція зникають посеред переходу.")

    # ------------------------------------------------------------------ результати
    def results(self):
        self.para(
            "Тестування виконано в режимі PIE (Play In Editor) автоматизованими Python-скриптами, які керують "
            "апаратом через ін’єкцію вводу Enhanced Input і записують телеметрію у файли Saved/*_PIE.json. Збірка "
            "C++ (UBT AOS_DKEditor Win64 Development, UHT із -WarningsAsErrors) завершилася без попереджень. "
            "Статична верифікація сцени показала 15 вільних маршрутів Shell-1 і 7 із 7 очікуваних контрольних "
            "зіткнень. Зведені результати PIE наведено в таблиці 6.")
        self.table(
            "Результати тестування в PIE",
            ["Сценарій", "Результат"],
            [
                ["Кран LARS", "31/31 перевірок; персонаж зупиняється біля турелі, HUD з’являється в кадрі "
                              "приземлення камери"],
                ["Контейнер", "осідає на полози, C(m) = 0; удар 900 см/с зсуває його на 40 см без перекидання"],
                ["Діжки на хвилях", "занурення 0,25–0,50 (1/B = 0,286), поверхня −110…+74 см, дрейф"],
                ["Клубок кабелів", "600 → 300 см/с; вибіг 85 см проти 368 см; 3 влучання – перерізано"],
                ["Енергоелемент", "60 % → 85 %, актор знищено; за 100 % – FULL, предмет лишається"],
                ["Магазин торпед", "224/224 – FULL; за місткості 256 – +32 торпеди"],
                ["Без натискання [F]", "1,5 с у сфері – предмет не підібрано"],
                ["Телепорт A → B", "2,01 с кінематики; вихід 500 см/с; керування відновлено"],
                ["Повторний вхід", "через 0,4 с – відмова, залишок охолодження 2,57 с"],
                ["Телепорт B → A", "2,00 с; вихід 500 см/с; апарат вирівняний"],
            ],
            [4.9, 12.6],
        )
        self.para(
            "1) Оформлення сцени. На рис. 2 показано надводну частину рівня: бетонний пірс із бруталістськими "
            "сходами, дерев’яний причал, кнехти та опори з готових асетів, а також власні моделі – кран LARS, що "
            "утримує апарат Shell-1, і рамку SomaLock станції телепортації A. Інтер’єр кластера C-01 з бетонними "
            "стінами та аркою видно на рис. 5.")
        self.figure("scene")
        self.para(
            "2) Власні 3D-моделі. Рис. 3 демонструє роботу крана SK_LARS_RoboticArm у PIE: персонаж упирається в "
            "турель, апарат утримується в захваті, рука опускає його на глибину 3 м, розкриває щелепи, після чого "
            "пілот отримує керування в кокпіті, а під час підйому щелепи знову захоплюють корпус. Колізійні форми "
            "на кістках блокують персонажа і не штовхають утримуваний апарат.")
        self.figure("lars")
        self.para(
            "3) Об’єкти трьох категорій. Контекстну взаємодію з аптечкою та ящиком з набоями ілюструють рис. 4 і "
            "рис. 5: під прицілом відображається дія та її ефект, а стан FULL виводиться напівпрозорим і не "
            "застосовується. Фізику діжок і контейнера підтверджено телеметрією (табл. 6): частка занурення діжок "
            "коливається навколо статичного значення 1/B, а контейнер масою 1500 кг залишається нерухомим за будь-"
            "якого стану моря, доки його не штовхне апарат.")
        self.figure("prompts")
        self.figure("cell")
        self.para(
            "4) Телепортація. Станції телепортації показано на рис. 6–8. Труба шахти заповнює круглий отвір рамки "
            "концентрично, зазор у гирлі дорівнює 0,0 см, трасування вздовж осі отвору й осі проходу досягають "
            "торцевої заглушки шахти, а зонд розміром з апарат нічого не зачіпає.")
        self.figure("tp_a")
        self.figure("tp_b")
        self.figure("tp_views")

    # ------------------------------------------------------------------ висновки
    def conclusions(self):
        self.para(
            "У ході лабораторної роботи засвоєно компонентну модель Unreal Engine 5: ієрархію UObject – AActor – "
            "APawn – ACharacter, розподіл обов’язків між UActorComponent, USceneComponent і UPrimitiveComponent та "
            "систему профілів колізій з відгуками Block, Overlap і Ignore, типами об’єктів і каналами трасування. "
            "Сцену рівня «Підводний світ» оформлено 17 готовими асетами різної форми та понад 170 об’єктами, "
            "ресурси-заповнювачі замінено бруталістськими модулями, розгорнуто макрокаркас вежі A та кластер "
            "C-01 /home/a03 з автоматичною перевіркою прохідності. У 3ds Max процедурно розроблено чотири власні "
            "3D-моделі – артикульований кран із 12-кістковим скелетом, деформований шлюз, шинопровід і фізичний "
            "контейнер – з UV-розгорткою, сокетами та простими колізіями UCX, коректність яких підтверджено "
            "аналітичними й трасувальними тестами.")
        self.para(
            "Програмно на C++ реалізовано універсальний компонент UAOSFluidPhysicsComponent, який поєднує хвилі "
            "Герстнера, силу Архімеда й опір Морісона із залежністю впливу хвиль від маси тіла, завдяки чому діжка "
            "масою 45 кг плаває на хвилях, а контейнер масою 1500 кг лишається на дні й переміщується лише від "
            "удару. Створено три категорії об’єктів – нерухомі перешкоди з різними типами колізій, фізичні рухомі "
            "об’єкти та аптечку й ящик з набоями з контекстною взаємодією на [F] – і двосторонню тригерну "
            "телепортацію між локаціями, віддаленими на 236 м, з кінематичним втягуванням, затемненням камери та "
            "захистом від зациклення. Автоматизовані тести PIE підтвердили відповідність поведінки всіх систем "
            "поставленим завданням.")

    # ------------------------------------------------------------------ перевірки
    def validate(self):
        body = self.doc.element.body
        full = "".join(t.text or "" for t in body.iter(qn("w:t")))
        if "—" in full:
            raise SystemExit("Помилка: у документі знайдено довге тире (—). Використовуйте коротке (–).")
        for p in self.doc.paragraphs:
            if (p.runs[0].font.name if p.runs else None) != CODE_FONT and re.search(r"\s-\s", p.text):
                raise SystemExit(f"Помилка: дефіс замість тире: {p.text[:80]}")
        # порожні абзаци: дозволені лише навколо назв розділів і перед назвами підрозділів (п. 7, 9, 10)
        paras = self.doc.paragraphs
        start = next(i for i, p in enumerate(paras) if p.text.startswith("Тема роботи"))
        for i in range(start, len(paras)):
            if paras[i].text.strip() or paras[i]._p.xpath(".//w:drawing") or \
                    (paras[i].runs and paras[i].runs[0].font.name == CODE_FONT):   # порожній рядок у лістингу
                continue
            neighbours = [paras[j] for j in (i - 1, i + 1) if 0 <= j < len(paras)]
            ok = any(n.runs and n.runs[0].font.bold for n in neighbours)
            if not ok:
                raise SystemExit(f"Зайвий порожній рядок після: {paras[i - 1].text[:60]}")
        return len(full)

    def save(self, out: Path):
        out.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                    help="корінь проєкту AOS_DK (типово – тека над Tools/)")
    ap.add_argument("--template", type=Path, default=None, help="шаблон звіту кафедри (.docx)")
    ap.add_argument("--out", type=Path, default=None, help="шлях до вихідного .docx")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    template = args.template or (root / TEMPLATE_REL)
    out = args.out or (root / TARGET_REL)

    rep = Report(root, template)
    rep.build()
    n_chars = rep.validate()
    rep.save(out)
    print(f"OK: {out}")
    print(f"    рисунків {rep.fig_no}, таблиць {rep.tab_no}, формул {rep.formula_no}, символів {n_chars}")
    if rep.missing:
        print("    УВАГА, відсутні зображення: " + "; ".join(rep.missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
