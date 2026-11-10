# -*- coding: utf-8 -*-
"""
AOS-DK | Генератор звіту до лабораторної роботи «Взаємодія з Акторами сцени» (варіант № 10 «Підводний світ»).

Запуск із кореня проєкту (або будь-звідки):
    python Tools/generate_lab_report.py [--root <шлях до AOS_DK>] [--out <шлях до .docx>]

Результат: Docs/Звіт_ЛР_Взаємодія_з_Акторами_Ігор_Брайченко.docx

Форматування (ДСТУ-подібний шаблон кафедри ПЗ НУ «Львівська політехніка»):
  * A4; поля: ліве 25 мм, праве 10 мм, верхнє 20 мм, нижнє 20 мм;
  * номер сторінки – угорі праворуч, арабськими цифрами; титульна сторінка без номера (Different First Page);
  * основний текст – Times New Roman 14 pt, міжрядковий 1,5, вирівнювання за шириною,
    абзацний відступ 1,25 см, інтервали до/після 0 pt;
  * код – Courier New 10 pt, одинарний інтервал, без абзацного відступу, у світлій рамці;
  * розділи – ЖИРНІ ВЕЛИКІ, порожній рядок до і після; підрозділи – жирні, відступ 1,25 см, порожній рядок до;
  * підписи: «Рис. N. Назва» під рисунком по центру; «Таблиця N.» праворуч над таблицею, назва по центру нижче;
  * тире – лише коротке (–) з пробілами; довге тире (—) у тексті заборонене (перевіряється перед збереженням).

Залежності: python-docx >= 1.1 (pip install python-docx).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

# =====================================================================================================================
# 1. Константи документа
# =====================================================================================================================
TARGET_REL = Path("Docs") / "Звіт_ЛР_Взаємодія_з_Акторами_Ігор_Брайченко.docx"

LAB_NUMBER = "4"
COURSE = "Проектування та розробка ігор"
TOPIC = "Взаємодія з Акторами сцени"
VARIANT = "Варіант № 10 “Підводний світ”"
LECTURER = ("ст. викл. каф. ПЗ", "Тетяна ЦИМБАЛЮК")
EVALUATOR = ("асист. каф. ПЗ", "Олександр БАУСК")
STUDENT = ("ст. гр. ПЗ-43", "Ігор БРАЙЧЕНКО")
CITY_YEAR = "Львів – 2026"

BODY_FONT, CODE_FONT = "Times New Roman", "Courier New"
BODY_PT, CODE_PT, TABLE_PT = 14, 10, 12
INDENT = Cm(1.25)
CODE_MAX_COLS = 78                         # Courier New 10 pt (2,12 мм/символ) у рамці ~169 мм
TEXT_WIDTH = Mm(210 - 25 - 10)             # 175 мм
CODE_BG, CODE_BORDER = "F3F4F6", "BFBFBF"

# Рисунки: (ключ, відносний шлях, ширина в см, назва без крапки в кінці)
FIGURES = {
    "soma":    ("Claude outputs/SomaLock_front34.png", 15.5,
                "Модель SM_Breach_SomaLock у вікні перегляду 3ds Max: заклинена стулка, кишеня та гідроциліндри"),
    "lars":    ("Saved/Screenshots/LARS_cinematic_collision_PIE.jpg", 16.0,
                "Тестування крана SK_LARS_RoboticArm у PIE: колізія з персонажем, спуск, захоплення та підйом Shell-1"),
    "prompts": ("Saved/ClaudeExport/optics/prompt_crops.png", 9.5,
                "Контекстні підказки під прицілом: [F] SALVAGE ENERGY (+25%), [F] FULL та [F] SALVAGE AMMO (+32)"),
    "cell":    ("Saved/ClaudeExport/optics/prompt_full.png", 16.0,
                "Енергоелемент BP_Pickup_EnergyCell у серверному вузлі R5 та HUD апарата під час PIE"),
    "tp_a":    ("Saved/ClaudeExport/optics/start_view_1.png", 16.0,
                "Станція телепортації A: рамка SomaLock і транзитна шахта зі стартового огляду гравця"),
    "tp_b":    ("Saved/Screenshots/WindowsEditor/Align2_B_user.png", 16.0,
                "Станція телепортації B: труба шахти співвісна з отвором шлюзу SomaLock"),
    "tp_views": ("Saved/ClaudeExport/optics/teleport_views.png", 11.0,
                 "Ракурси транзитної системи: гирло станції A, шлюз станції B, вихід у відкриту воду"),
}

# =====================================================================================================================
# 2. Зміст звіту
#    Розмітка в тексті: **жирний**, _{нижній індекс}, ^{верхній індекс}.
# =====================================================================================================================
THEME = "Взаємодія з Акторами сцени."
GOAL = ("Навчитися наповнювати сцену власними 3D-моделями, налаштовувати колізії та фізичну симуляцію акторів "
        "і програмувати їх взаємодію з гравцем за допомогою тригерів у середовищі Unreal Engine 5.")

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

# УВАГА: формулювання завдань варіанта № 10 відтворено за методичними вказівками; за потреби замініть дослівним
# текстом із силабусу (лише цей список, решта документа від нього не залежить).
TASK_INTRO = ("Варіант № 10 «Підводний світ». Тематика рівня – підводна дослідницька станція, елементи якої "
              "розташовані на поверхні океану та в товщі води. Завдання лабораторної роботи:")
TASK_ITEMS = [
    "Завдання 1. Оформити сцену рівня відповідно до тематики варіанта: замінити об’єкти-заповнювачі (примітиви) "
    "тематичними 3D-моделями, використавши не менше 13 різних геометричних форм.",
    "Завдання 2. Створити у 3ds Max не менше 4-х власних 3D-моделей відповідно до тематики варіанта, з UV-розгорткою, "
    "матеріалами та простою колізією (UCX), та імпортувати їх у проєкт Unreal Engine.",
    "Завдання 3. Розмістити на сцені інтерактивні актори трьох категорій: статичні перешкоди, які гравець має "
    "оминати; фізичні рухомі об’єкти, на які гравець може впливати; об’єкти, взаємодія з якими змінює стан гравця.",
    "Завдання 4. Реалізувати систему телепортації гравця між двома віддаленими точками рівня за допомогою тригерів.",
]

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
# 3. Низькорівневі помічники python-docx
# =====================================================================================================================
_MARKUP = re.compile(r"(\*\*.+?\*\*|_\{.+?\}|\^\{.+?\})")


def set_run_font(run, name=BODY_FONT, size=BODY_PT, bold=None, italic=None):
    run.font.name = name
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), name)
    return run


def fmt(p, *, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first=INDENT, left=Cm(0), line=1.5, keep_next=False):
    pf = p.paragraph_format
    pf.alignment = align
    pf.first_line_indent = first
    pf.left_indent = left
    pf.right_indent = Cm(0)
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE if line == 1.5 else WD_LINE_SPACING.SINGLE
    pf.widow_control = True
    pf.keep_with_next = keep_next
    return p


def add_rich(p, text, size=BODY_PT, font=BODY_FONT, bold=False):
    """Додає текст із мінімальною розміткою **жирний**, _{sub}, ^{sup}."""
    for part in _MARKUP.split(text):
        if not part:
            continue
        if part.startswith("**"):
            set_run_font(p.add_run(part[2:-2]), font, size, bold=True)
        elif part.startswith("_{"):
            r = set_run_font(p.add_run(part[2:-1]), font, size, bold=bold)
            r.font.subscript = True
        elif part.startswith("^{"):
            r = set_run_font(p.add_run(part[2:-1]), font, size, bold=bold)
            r.font.superscript = True
        else:
            set_run_font(p.add_run(part), font, size, bold=bold)
    return p


def shade_cell(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcpr.append(shd)


def set_cell_borders(cell, color="000000", sz=4):
    tcpr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tcpr.append(borders)


def set_cell_margins(table, top=80, bottom=80, left=140, right=140):
    tblpr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for edge, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblpr.append(mar)


def set_table_width(table, widths_cm):
    table.autofit = False
    tblpr = table._tbl.tblPr
    tblw = tblpr.find(qn("w:tblW"))
    if tblw is None:
        tblw = OxmlElement("w:tblW")
        tblpr.append(tblw)
    total = sum(widths_cm)
    tblw.set(qn("w:w"), str(int(total / 2.54 * 1440)))
    tblw.set(qn("w:type"), "dxa")
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblpr.append(layout)
    grid = table._tbl.tblGrid
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths_cm):
        gc.set(qn("w:w"), str(int(w / 2.54 * 1440)))
    for row in table.rows:
        for cell, w in zip(row.cells, widths_cm):
            cell.width = Cm(w)


def add_page_number_field(paragraph):
    def fld(kind):
        r = paragraph.add_run()
        set_run_font(r)
        el = OxmlElement("w:fldChar")
        el.set(qn("w:fldCharType"), kind)
        r._element.append(el)
        return r
    fld("begin")
    r = paragraph.add_run()
    set_run_font(r)
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    r._element.append(instr)
    fld("separate")
    set_run_font(paragraph.add_run("2"))
    fld("end")


# =====================================================================================================================
# 4. Побудова документа
# =====================================================================================================================
class Report:
    def __init__(self, root: Path):
        self.root = root
        self.doc = Document()
        self.fig_no = 0
        self.tab_no = 0
        self.formula_no = 0
        self.last_blank = False
        self.missing = []
        self._setup()

    # ------------------------------------------------------------------ setup
    def _setup(self):
        doc = self.doc
        normal = doc.styles["Normal"]
        normal.font.name = BODY_FONT
        normal.font.size = Pt(BODY_PT)
        rpr = normal.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.insert(0, rfonts)
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rfonts.set(qn(attr), BODY_FONT)
        lang = OxmlElement("w:lang")
        lang.set(qn("w:val"), "uk-UA")
        lang.set(qn("w:eastAsia"), "uk-UA")
        lang.set(qn("w:bidi"), "ar-SA")
        rpr.append(lang)
        npf = normal.paragraph_format
        npf.space_before = Pt(0)
        npf.space_after = Pt(0)
        npf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE

        sec = doc.sections[0]
        sec.page_width, sec.page_height = Mm(210), Mm(297)
        sec.left_margin, sec.right_margin = Mm(25), Mm(10)
        sec.top_margin, sec.bottom_margin = Mm(20), Mm(20)
        sec.header_distance, sec.footer_distance = Mm(10), Mm(10)
        sec.different_first_page_header_footer = True

        hp = sec.header.paragraphs[0]
        fmt(hp, align=WD_ALIGN_PARAGRAPH.RIGHT, first=Cm(0), line=1.0)
        add_page_number_field(hp)
        fp = sec.first_page_header.paragraphs[0]
        fmt(fp, align=WD_ALIGN_PARAGRAPH.RIGHT, first=Cm(0), line=1.0)

        cp = doc.core_properties
        cp.title = f"Звіт до лабораторної роботи № {LAB_NUMBER}: {TOPIC}"
        cp.author = "Ігор Брайченко, ПЗ-43"
        cp.subject = COURSE
        cp.language = "uk-UA"
        cp.keywords = "Unreal Engine 5, AOS_DK, колізії, Chaos, тригери, телепортація"

    # ------------------------------------------------------------------ primitives
    def blank(self, line=1.5):
        p = fmt(self.doc.add_paragraph(), first=Cm(0), line=line)
        set_run_font(p.add_run(""))
        self.last_blank = True
        return p

    def para(self, text, *, align=WD_ALIGN_PARAGRAPH.JUSTIFY, first=INDENT, bold=False, keep_next=False):
        p = fmt(self.doc.add_paragraph(), align=align, first=first, keep_next=keep_next)
        add_rich(p, text, bold=bold)
        self.last_blank = False
        return p

    def section(self, title):
        if not self.last_blank:
            self.blank()
        p = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.CENTER, first=Cm(0), keep_next=True)
        set_run_font(p.add_run(title.upper()), bold=True)
        self.blank().paragraph_format.keep_with_next = True
        return p

    def subsection(self, title):
        assert not title.endswith("."), title
        if not self.last_blank:
            self.blank().paragraph_format.keep_with_next = True
        p = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.LEFT, first=INDENT, keep_next=True)
        set_run_font(p.add_run(title), bold=True)
        self.last_blank = False
        return p

    def formula(self, text):
        """Формула по центру, номер у круглих дужках праворуч."""
        self.formula_no += 1
        p = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.LEFT, first=Cm(0))
        stops = p.paragraph_format.tab_stops
        stops.add_tab_stop(Cm(TEXT_WIDTH.cm / 2), WD_TAB_ALIGNMENT.CENTER)
        stops.add_tab_stop(TEXT_WIDTH, WD_TAB_ALIGNMENT.RIGHT)
        add_rich(p, "\t" + text + f"\t({self.formula_no})")
        self.last_blank = False
        return self.formula_no

    def code(self, source):
        lines = source.strip("\n").expandtabs(4).split("\n")
        for ln in lines:
            if len(ln) > CODE_MAX_COLS:
                print(f"[warn] code line {len(ln)} > {CODE_MAX_COLS}: {ln}", file=sys.stderr)
        if not self.last_blank:
            self.blank()
        table = self.doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_width(table, [TEXT_WIDTH.cm])
        set_cell_margins(table, 100, 100, 160, 160)
        cell = table.rows[0].cells[0]
        shade_cell(cell, CODE_BG)
        set_cell_borders(cell, CODE_BORDER, 4)
        first = True
        for ln in lines:
            p = cell.paragraphs[0] if first else cell.add_paragraph()
            first = False
            fmt(p, align=WD_ALIGN_PARAGRAPH.LEFT, first=Cm(0), line=1.0)
            r = set_run_font(p.add_run(ln if ln else ""), CODE_FONT, CODE_PT)
            if ln.lstrip().startswith("//"):
                r.font.color.rgb = RGBColor(0x55, 0x6B, 0x2F)
        self.blank()

    def figure(self, key):
        rel, width_cm, title = FIGURES[key]
        assert not title.endswith(".")
        self.fig_no += 1
        path = self.root / rel
        if not self.last_blank:
            self.blank()
        p = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.CENTER, first=Cm(0), line=1.0, keep_next=True)
        if path.is_file():
            p.add_run().add_picture(str(path), width=Cm(width_cm))
        else:
            self.missing.append(rel)
            set_run_font(p.add_run(f"[рисунок відсутній: {rel}]"), italic=True)
        cap = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.CENTER, first=Cm(0))
        set_run_font(cap.add_run(f"Рис. {self.fig_no}. {title}"))
        self.blank()
        return self.fig_no

    def table(self, title, header, rows, widths_cm, align_cols=None, size=TABLE_PT):
        assert abs(sum(widths_cm) - TEXT_WIDTH.cm) < 0.05, (title, sum(widths_cm))
        self.tab_no += 1
        if not self.last_blank:
            self.blank()
        c1 = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.RIGHT, first=Cm(0), keep_next=True)
        set_run_font(c1.add_run(f"Таблиця {self.tab_no}."))
        c2 = fmt(self.doc.add_paragraph(), align=WD_ALIGN_PARAGRAPH.CENTER, first=Cm(0), keep_next=True)
        set_run_font(c2.add_run(title))
        t = self.doc.add_table(rows=1 + len(rows), cols=len(header))
        t.style = self.doc.styles["Table Grid"]
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_width(t, widths_cm)
        set_cell_margins(t, 30, 30, 80, 80)
        for i, row in enumerate([header] + rows):
            tr = t.rows[i]
            if i == 0:
                trpr = tr._tr.get_or_add_trPr()
                th = OxmlElement("w:tblHeader")
                th.set(qn("w:val"), "true")
                trpr.append(th)
            cant = OxmlElement("w:cantSplit")
            tr._tr.get_or_add_trPr().append(cant)
            for j, txt in enumerate(row):
                cell = tr.cells[j]
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                p = cell.paragraphs[0]
                if i == 0:
                    a = WD_ALIGN_PARAGRAPH.CENTER
                else:
                    a = (align_cols or {}).get(j, WD_ALIGN_PARAGRAPH.LEFT)
                fmt(p, align=a, first=Cm(0), line=1.0)
                add_rich(p, txt, size=size, bold=(i == 0))
        self.blank()
        return self.tab_no

    def page_break(self):
        p = self.doc.add_paragraph()
        fmt(p, first=Cm(0), line=1.0)
        p.add_run().add_break(WD_BREAK.PAGE)
        self.last_blank = True

    # ------------------------------------------------------------------ title page
    def title_page(self):
        C, R = WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.RIGHT

        def line(parts, align, size=BODY_PT, keep=False):
            p = fmt(self.doc.add_paragraph(), align=align, first=Cm(0), line=1.0, keep_next=keep)
            for text, bold in parts:
                set_run_font(p.add_run(text), size=size, bold=bold)
            return p

        def gap(n):
            for _ in range(n):
                line([("", False)], C)

        line([("МІНІСТЕРСТВО ОСВІТИ І НАУКИ УКРАЇНИ", True)], C)
        line([("НАЦІОНАЛЬНИЙ УНІВЕРСИТЕТ “ЛЬВІВСЬКА ПОЛІТЕХНІКА”", True)], C)
        gap(1)
        line([("Інститут ", False), ("КНІТ", True)], R)
        line([("Кафедра ", False), ("ПЗ", True)], R)
        gap(7)
        line([("ЗВІТ", True)], C, size=18)
        gap(1)
        line([(f"до лабораторної роботи № {LAB_NUMBER}", False)], C)
        line([("з дисципліни: ", True), (f"“{COURSE}”", False)], C)
        line([("на тему: ", True), (f"“{TOPIC}”", False)], C)
        line([(VARIANT, False)], C)
        gap(5)
        for label, (pos, name) in (("Лектор:", LECTURER), ("Виконав:", STUDENT), ("Прийняв:", EVALUATOR)):
            line([(label, True)], R)
            line([(pos, False)], R)
            line([(name, False)], R)
            gap(1)
        line([("« ____ » ____________ 2026 р.", False)], R)
        gap(7)
        line([(CITY_YEAR, False)], C)

    # ------------------------------------------------------------------ body
    def build(self):
        self.title_page()
        p = self.para(f"**Тема роботи:** {THEME}")
        p.paragraph_format.page_break_before = True  # без порожнього абзацу-розриву
        p = self.para(f"**Мета роботи:** {GOAL}")

        # ---------------- ТЕОРЕТИЧНІ ВІДОМОСТІ
        self.section("Теоретичні відомості")
        for t in THEORY:
            self.para(t)

        # ---------------- ЗАВДАННЯ
        self.section("Завдання")
        self.para(TASK_INTRO)
        for t in TASK_ITEMS:
            self.para(t)

        # ---------------- ХІД ВИКОНАННЯ
        self.section("Хід виконання")
        self.step_1()
        self.step_2()
        self.step_3()
        self.step_4()

        # ---------------- РЕЗУЛЬТАТИ
        self.section("Результати")
        self.results()

        # ---------------- ВИСНОВКИ
        self.section("Висновки")
        self.conclusions()

    # ------------------------------------------------------------------ 1
    def step_1(self):
        self.subsection("1. Оформлення сцени та заміна заповнювачів")
        self.para(
            "Роботу виконано на рівні Lvl_FirstPerson проєкту AOS_DK (Unreal Engine 5.7.4). Перед наповненням сцени "
            "проведено аудит ресурсів середовища за метаданими Asset Registry без масового завантаження ресурсів. "
            "Видалено 255 невикористаних або стилістично невідповідних ресурсів (близько 1,9 ГБ): демонстраційні "
            "об’єкти Quixel, плоскі заготовки-коробки, надлишкові варіанти мегасканів. Ресурс видалявся лише тоді, "
            "коли всі посилання на нього знаходилися всередині множини видалення, а захищені теки (власні моделі, "
            "вихідні файли RawArt, підводний апарат) не змінювалися. Після чистки бібліотека містить 22 різні "
            "геометричні форми в єдиному стилі (плита, кругла і квадратна колони, сходовий марш, балка, діжка, "
            "палета, контейнер, бетонні уламки, кабельні траси, фланець, підвісний світильник, арка, кнехт тощо), "
            "що перевищує вимогу щодо 13 форм.")
        self.para(
            "Сцену наповнено понад 170 акторами оформлення. Для заміни заповнювачів у стилі бруталістської "
            "підводної станції в 3ds Max процедурно побудовано модульний набір із 28 статичних сіток: труби "
            "D20–D80 з колінами, трійником і перехідником, хомути, серверні шафи, кабельні лотки, решітчасті "
            "містки зі сходами, гермодвері зі стулкою, засувку з маховиком, двотаврові балки, вентиляційні короби, "
            "бетонні арку й сходи. Кожна сітка має колізію UCX (не більше 32 вершин на оболонку), увімкнений Nanite, "
            "сокети для стикування та прив’язку до сітки 50 см. Невідповідні стилю «замкові» сходи Castle_Stairs "
            "(2 актори) і цегляну арку Brick_Ruin_Door_Arch замінено на SM_Stairs_Concrete_Brutalist і "
            "SM_Concrete_Arch_Brutalist безпосередньо в наявних акторах: напрямок підйому сходів визначено "
            "трасуваннями згори вниз, масштаб підібрано так, щоб нова сітка точно заповнювала світовий AABB старої "
            "(похибка 0,0 см), а вихідну сітку та трансформацію збережено в тегах AOS_LegacyMesh і AOS_LegacyXform "
            "для можливості відкату.")
        self.para(
            "Скриптом Tools/setup_macro_topology.py розгорнуто макрокаркас вежі A згідно з просторовою специфікацією "
            "рівня: опорні точки двох шпилів A-0, площину кільцевої шини (Z = −90 000 см), якірні точки кластерів "
            "C-01…C-05, шахту доку Socket діаметром 60 м, магістральний шинопровід D-1 із шести сегментів "
            "SM_GIS_BusCoupler із кроком 60 м та 24-гранну оболонку-обмежувач рівня з KillZ = −175 000 см. Кожен "
            "актор позначено тегом AOS_MacroID, тому скрипт є ідемпотентним: повторний запуск вирівнює наявні "
            "актори за специфікацією, а не дублює їх.")
        self.para(
            "Кластер C-01 /home/a03 зібрано скриптом Tools/setup_cluster_a03.py навколо якоря ANC_A3_home_a03 "
            "(−48 000; 22 000; −9 800 см). Шість приміщень (табл. 1) утворені 86 бетонними оболонками, 19 порталами "
            "та 6 об’ємами-кімнатами з тегами AOS_RoomID і AOS_DirectoryPath. Стіни й перекриття завтовшки 100 см "
            "отримано відніманням коробок «конструкція – повітря – вже розміщені елементи», тому елементи не "
            "перетинаються і не мають копланарних граней. Для бетону створено матеріал M_AOS_Concrete_BoxMap із "
            "проєкцією текстури в локальних сантиметрах кластера, що усуває розтягування текстури на "
            "масштабованих коробках. Головним входом у кластер слугує власна модель шлюзу SM_Breach_SomaLock.")
        self.table(
            "Приміщення кластера C-01 /home/a03",
            ["Приміщення", "Шлях у віртуальній ФС", "Внутрішній розмір, см", "Рівень підлоги"],
            [
                ["A03_R1 – вестибюль", "/home/a03/lobby", "2400 × 3200 × 1350", "B + 0"],
                ["A03_R2 – капсульний атріум", "/home/a03/capsules", "2000 × 2000 × 4500", "B + 0"],
                ["A03_R3 – зала відпочинку", "/home/a03/rec", "4000 × 2800 × 1350", "B + 900"],
                ["A03_R4 – їдальня", "/var/a03/canteen", "1600 × 2400 × 900", "B + 0"],
                ["A03_R5 – серверний вузол", "/sys/a03/node", "3200 × 2400 × 900", "B + 3600"],
                ["A03_R6 – диспетчерська", "/sys/a03/dispatch", "2000 × 1200 × 600", "B + 3600"],
            ],
            [5.0, 4.6, 4.6, 3.3],
            {2: WD_ALIGN_PARAGRAPH.CENTER, 3: WD_ALIGN_PARAGRAPH.CENTER},
        )
        self.para(
            "Прохідність перевірено розгортками об’єктного запиту WorldStatic коробкою 400 × 200 × 200 см і "
            "сферою радіусом 245 см (габарити апарата Shell-1) уздовж усього маршруту «зовні – SomaLock – R1 – R2 – "
            "R5 – R6» та додаткових проходів: жодного зіткнення. Контрольні розгортки, зміщені в опори арок, "
            "суцільні стіни та перемички, навпаки, очікувано фіксують зіткнення, що підтверджує коректність тесту.")

    # ------------------------------------------------------------------ 2
    def step_2(self):
        self.subsection("2. Розробка 4-х власних 3D-моделей у 3ds Max")
        self.para(
            "Усі чотири моделі побудовано процедурно скриптами pymxs (Tools/max_build_*.py) у 3ds Max 2027, що "
            "дозволяє повністю відтворити сітку, колізію та специфікацію сокетів одним запуском. Одиниці – "
            "сантиметри, вісь Z спрямована вгору. Експорт виконано у бінарний FBX із групами згладжування, імпорт – "
            "легасі-імпортером FBX (на час імпорту cvar Interchange.FeatureFlags.Import.FBX = 0), оскільки "
            "Interchange відкидає оболонки UCX. Для кожної моделі виконано UV-розгортку Flatten без перекритих "
            "граней, увімкнено Nanite, призначено PBR-екземпляри матеріалу M_AOS_HeroSurface і автоматично "
            "перевірено межі, кількість опуклих елементів, сокети та слоти. Узагальнені характеристики наведено в "
            "таблиці 2.")
        self.table(
            "Характеристики власних 3D-моделей",
            ["Модель", "Призначення", "Габарити, см", "Кількість трикутників", "Колізія", "Сокети"],
            [
                ["SK_LARS_RoboticArm", "кран спуску та підйому апарата", "1683 × 304 × 360", "28 852",
                 "12 кісток, форми на кістках", "3"],
                ["SM_Breach_SomaLock", "деформований шлюз SOMA-типу", "1143 × 1945 × 1209", "36 636", "18 UCX", "13"],
                ["SM_GIS_BusCoupler", "сегмент високовольтного шинопроводу", "6000 × 8800 × 8800", "52 416",
                 "23 UCX", "11"],
                ["SM_Cargo_Pod_Phys", "важкий фізичний контейнер", "400 × 188 × 207", "13 252",
                 "1 UCX (32 вершини)", "8"],
            ],
            [4.5, 3.2, 2.8, 2.4, 2.9, 1.7],
            {2: WD_ALIGN_PARAGRAPH.CENTER, 3: WD_ALIGN_PARAGRAPH.CENTER, 5: WD_ALIGN_PARAGRAPH.CENTER},
            size=11,
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
            "співвісності циліндрів становила 0,00°, мінімальне перекриття телескопа – 35,9 см. Актор ALARSDockArm "
            "виконує сценарій утримання, спуску (Z 500 → −300 см зі швидкістю 140 см/с) і підйому апарата з плоскою "
            "інверсною кінематикою та кінематографічною камерою LaunchCam. Колізію задано простими блокувальними "
            "формами, прикріпленими до кісток: структурні частини блокують Pawn і PhysicsBody, а захват і щелепи – "
            "лише Pawn, щоб не штовхати утримуваний корпус.")

        self.subsection("2.2. Деформований шлюз SOMA-типу SM_Breach_SomaLock")
        self.para(
            "Броньований шлюз SOMA-типу є головним входом до кластера C-01 і рамкою станцій телепортації. Модель "
            "містить фланці зовнішнім діаметром 1200 см з отвором Ø 820 см, камеру завдовжки 600 см з обручами "
            "жорсткості та 12 радіальними косинками, титанову стулку Ø 860 × 80 см, заклинену на 60 % ходу "
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
            "як контрольна сфера R 256 см очікувано зачіпає оболонку стулки. Модель має 13 сокетів: точки навігації "
            "Nav_In/Nav_Out, кріплення термінала, джерела іскор і бульбашок та шість ламп статусу.")

        self.subsection("2.3. Високовольтний шинопровід SM_GIS_BusCoupler")
        self.para(
            "Модель відтворює сегмент елегазового шинопроводу (GIS) у масштабі вежі: литий алюмінієвий корпус "
            "зовнішнім діаметром 8000 см (80 м) із товщиною стінки 150 см, мідний провідник Ø 2830 см, фланці "
            "Ø 8800 см із 96 болтами, 64 поздовжні ребра охолодження, епоксидний опорний ізолятор із шести спиць на "
            "конусі 26°, оглядові люки та патрубок запобіжної мембрани. Між провідником і корпусом утворено "
            "коаксіальний кільцевий канал R 1504…3776 см, яким апарат рухається з повними шістьма ступенями "
            "свободи, а шість вікон ізолятора дають осьові проходи з чистим радіусом не менше 992 см. Сегмент "
            "завдовжки 60 м має сокети SOCKET_Snap_Front/Rear, тому сегменти без зазорів стикуються в магістраль D-1.")
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
            "400 × 188 × 207 см. Колізія навмисно складається з однієї опуклої оболонки на 32 вершини: плоска нижня "
            "грань 344 × 146 см на рівні полозів не дає контейнеру котитися, а скошені носи дозволяють наїжджати на "
            "краї доків, не застрягаючи. Центр мас розташований на 17,1 см нижче осі корпусу через масу полозів, що "
            "створює природний самовідновлювальний момент. Розгортки коробки Shell-1 із п’яти напрямків "
            "зупиняються на чистих осьових нормалях без застрягань, а 8 сокетів (буксирування, підйом, витік, "
            "магнітний захват) підготовлені для тросів і крана.")

    # ------------------------------------------------------------------ 3
    def step_3(self):
        self.subsection("3. Реалізація 3-х категорій інтерактивних акторів")
        self.para(
            "Класи інтерактивних акторів розміщено в модулі Source/AOS_DK/Gameplay/Interactables/, а їхні "
            "Blueprint-нащадки – у теці /Game/AOS_DK_Game/Gameplay/Interactables/. Скрипт "
            "Tools/deploy_interactables_c01.py ідемпотентно розставив 14 акторів у приміщеннях кластера C-01, "
            "магістралі D-1 і шахті Socket, визначаючи рівень підлоги трасуваннями WorldStatic. Параметри акторів "
            "наведено в таблиці 3.")
        self.table(
            "Інтерактивні актори сцени",
            ["Актор", "Батьківський клас C++", "Колізія", "Ключові параметри"],
            [
                ["BP_Obstacle_Bulkhead", "AAOSStaticObstacle", "BlockAll, Static", "плита 1520 × 120 × 1250 см"],
                ["BP_Obstacle_CableTangle", "AAOSCableTangle", "AOS_SoftFoliage (QueryOnly)",
                 "швидкість × 0,5; 3 с; міцність 40"],
                ["BP_Phys_CargoPod", "AAOSPhysicsProp", "PhysicsActor, 1 UCX", "1500 кг; B = 0,4; μ = 0,3"],
                ["BP_Phys_BuoyantDrum", "AAOSPhysicsProp", "PhysicsActor", "45 кг; B = 3,5"],
                ["BP_Pickup_EnergyCell", "AAOSPickup_EnergyCell", "сфера R 150, QueryOnly", "+25 % енергії ядра"],
                ["BP_Pickup_TorpedoMagazine", "AAOSPickup_TorpedoMagazine", "сфера R 150, QueryOnly",
                 "+32 торпеди до резерву"],
            ],
            [5.1, 5.6, 3.1, 3.7], size=11,
        )

        self.subsection("3.1. Статичні перешкоди")
        self.para(
            "Клас AAOSStaticObstacle – актор зі статичною сіткою-коренем у профілі BlockAll зі статичною "
            "мобільністю та простою колізією. Його нащадок BP_Obstacle_Bulkhead (плита 1520 × 120 × 1250 см з "
            "ребрами та помаранчевою сигнальною смугою, одна проста колізія UBX) встановлено у вестибюлі R1 так, що "
            "він перекриває пряму лінію від шлюзу SomaLock до арки капсульного атріуму і змушує гравця обходити його "
            "через бічні проходи шириною 990 та 690 см.")
        self.para(
            "Друга перешкода, BP_Obstacle_CableTangle (клубок із 21 обірваного кабелю, 435 × 745 × 540 см), "
            "використовує власний профіль AOS_SoftFoliage, оголошений у DefaultEngine.ini: QueryOnly, тип "
            "WorldDynamic, Overlap для Pawn, PhysicsBody, Vehicle і Projectile, Ignore для решти каналів. Вона не "
            "блокує рух, а сповільнює: під час входу Shell-1 його швидкість одразу зменшується вдвічі, а протягом "
            "3 с діє додатковий лінійний опір")
        n = self.formula("k = d · f / (1 − f),")
        self.para(
            f"де d – коефіцієнт гідродинамічного опору апарата, f = 0,5 – частка гасіння швидкості. Формула ({n}) "
            "забезпечує, що усталена швидкість під тягою зменшується саме в (1 − f) раз. Після звільнення діє "
            "2-секундний захист від повторного захоплення, щоб апарат міг пробитися крізь клубок. Перешкода має тег "
            "AOS.FuseTarget і міцність 40 одиниць, тому три влучання мікроторпед (по 14 одиниць) перерізають кабелі, "
            "звільняють апарат і знищують актор.")

        self.subsection("3.2. Фізичні рухомі об’єкти")
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
            "за B > 1 спливає і плаває із зануренням σ = 1/B. Реалізацію формули "
            f"({n_c}) наведено у фрагменті нижче:")
        self.code(CODE_FLUID_COUPLING)
        self.para(
            f"Сили, що відповідають формулі ({n_b}), опору Морісона та стабілізації, додаються до тіла Chaos як "
            "прискорення (AddForce з bAccelChange = true), тому не залежать від маси. Крок обмежується значенням "
            "MaxPhysicsDeltaTime, а коефіцієнти опору – величиною 0,5/Δt, що гарантує стійкість явної схеми:")
        self.code(CODE_FLUID_NEWTON)
        self.para(
            "BP_Phys_CargoPod має масу 1500 кг, що перевищує поріг імунітету, тому C(m) = 0 і хвилі на нього не "
            "діють; коефіцієнт плавучості B = 0,4 утримує його на дні, а фізичний матеріал PM_AOS_CargoSkid (тертя "
            "0,3/0,35, комбінування Min) дозволяє апарату зсувати контейнер ударом. BP_Phys_BuoyantDrum – діжка "
            "57 × 62 × 88 см масою 45 кг (C(m) = 1) з B = 3,5: три діжки на ватерлінії шахти Socket гойдаються на "
            "хвилях Герстнера та дрейфують за орбітальною швидкістю води, а дві діжки в залі R3 спливають і "
            "зупиняються під стелею.")

        self.subsection("3.3. Об’єкти зміни стану гравця")
        self.para(
            "Абстрактний клас AAOSPickupBase реалізує інтерфейс IInteractable і містить сферу-тригер R 150 см "
            "(QueryOnly, WorldDynamic, Overlap лише для Pawn, PhysicsBody і Vehicle, оскільки коренем Shell-1 є "
            "коробка типу PhysicsBody), сітку без колізії та точкове світло; предмет погойдується (амплітуда 12 см, "
            "0,35 Гц) і обертається (35°/с). Нащадки перевизначають методи CanApplyPickup, GetSalvageLabel та "
            "ApplyPickup. BP_Pickup_EnergyCell додає 25 % енергії ядра через UShellEnergyComponent::AddEnergy і "
            "виводить у термінальний журнал повідомлення «core: energy cell absorbed +25%»; "
            "BP_Pickup_TorpedoMagazine знаходить у відсіку перший дрон ASubDrone_Attacker і додає 32 торпеди до "
            "резерву. Якщо ядро або резерв повні, предмет залишається на місці.")
        self.para(
            "Автоматичне підбирання під час перекриття свідомо замінено явною взаємодією на клавішу [F] "
            "(дія IA_Interact системи Enhanced Input). AShellPawn з частотою 30 Гц визначає фокус у радіусі 800 см: "
            "трасування каналом Visibility від камери (стіни перекривають огляд), розгортка об’єктного типу "
            "WorldDynamic сферою R 25 см до найближчої перешкоди для пошуку сфер-тригерів (вони не блокують жоден "
            "канал трасування, тому не заважають прицілюванню дронів) і запасний варіант – інтерактивний об’єкт "
            "контролера. Віджет прицілу UAOSHudCrosshair виводить під перехрестям підказку "
            "«[F] SALVAGE ENERGY (+25%)» або «[F] SALVAGE AMMO (+32)» кольором Cyan #8BE9FD, а якщо застосування "
            "неможливе – «[F] FULL» із прозорістю 0,4. У разі успіху TryCollect вимикає колізію, ховає сітку, "
            "програє звук і ефект бульбашок Niagara та знищує актор через 0,9 с:")
        self.code(CODE_PICKUP)

    # ------------------------------------------------------------------ 4
    def step_4(self):
        self.subsection("4. Система далекої тригерної телепортації")
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
            "Станцію A «Surface Socket [ETS-A]» встановлено біля шахти доку Socket з гирлом на Z = −1800 см і "
            "вертикальним напрямком входу Down; станцію B «Tower A C-01 SomaLock [ETS-B]» – за 32 м на захід від "
            "головного шлюзу кластера C-01, з гирлом на Z = −8750 см і напрямком Up. Відстань між точками виходу "
            "становить 236 м, перепад висот – 85,5 м. Глибину гирла A вибрано так, щоб імпульс виходу 500 см/с "
            "угору (близько 3,3 м інерційного руху) не виносив апарат на поверхню. Для станцій із горизонтальною "
            "шахтою додатково реалізовано режим EAOSTransitDirection::Forward.")
        n_h = self.formula_no + 1
        self.para(
            "Послідовність переходу така. Перекриття тригера викликає BeginTransit, який перевіряє, що апаратом "
            "керує гравець, ядро не зупинене, станція призначення вільна і не перебуває в періоді охолодження; "
            "потім блокує керування (SetBlockControls) і вимикає фізичну симуляцію корпусу. Протягом 1,2 с апарат "
            "кінематично втягується в трубу за кубічним сплайном Ерміта, що зберігає вхідну швидкість (не більше "
            "1500 см/с) і завершується на осі шахти зі швидкістю 1000 см/с, а ніс апарата плавно повертається на "
            "вісь (slerp):")
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
            f"таблиці 4, а реалізацію формули ({n_h}) – у фрагменті коду.")
        self.table(
            "Параметри послідовності телепортації",
            ["Властивість", "Значення", "Призначення"],
            [
                ["IntakeDuration", "1,2 с", "тривалість кінематичного втягування"],
                ["IntakeEndSpeed / MaxCarriedEntrySpeed", "1000 / 1500 см/с", "швидкість на осі / межа вхідної"],
                ["FadeDuration", "0,8 с", "затемнення та відновлення камери"],
                ["ExitSpeed", "500 см/с", "імпульс виходу зі станції призначення"],
                ["ArrivalCooldown", "3,0 с", "захист від циклічного спрацювання"],
                ["TriggerDepth × 2·TriggerHalfWidth", "500 × 600 × 600 см", "об’єм тригера перед гирлом"],
                ["ExitClearance", "300 см", "відстань точки виходу від тригера"],
            ],
            [6.6, 4.0, 6.9],
            {1: WD_ALIGN_PARAGRAPH.CENTER},
        )
        self.code(CODE_TELEPORT)
        self.para(
            "Захист від зациклення реалізовано порядком дій: період охолодження накладається на станцію призначення "
            "до перенесення, тому перекриття, яке породжує сам переніс, ігнорується, а точку виходу розміщено за "
            "300 см від тригера. Аварійний шлях AbortTransit відновлює фізику, керування та затемнення, якщо апарат "
            "або станція зникають посеред переходу.")

    # ------------------------------------------------------------------ results
    def results(self):
        self.para(
            "Тестування виконано в режимі PIE (Play In Editor) автоматизованими Python-скриптами, які керують "
            "апаратом через ін’єкцію вводу Enhanced Input і записують телеметрію у файли Saved/*_PIE.json. Збірка "
            "C++ (UBT AOS_DKEditor Win64 Development, UHT із -WarningsAsErrors) завершилася успішно без "
            "попереджень. Статична верифікація сцени показала 15 вільних маршрутів Shell-1 і 7 із 7 очікуваних "
            "контрольних зіткнень. Зведені результати PIE наведено в таблиці 5.")
        self.table(
            "Результати тестування в PIE",
            ["Сценарій", "Отриманий результат"],
            [
                ["Кран LARS: колізія, спуск і підйом (31 перевірка)",
                 "31/31; персонаж зупиняється за 158,5 см від осі турелі зі швидкістю 0; перехід LaunchCam → "
                 "кокпіт за 1,35 с, HUD з’являється в кадрі приземлення камери"],
                ["Контейнер BP_Phys_CargoPod",
                 "осідає на полози (2 см), C(m) = 0, v = 0; удар Shell-1 900 см/с зсуває його на 40 см без перекидання"],
                ["Діжки BP_Phys_BuoyantDrum на хвилях",
                 "занурення 0,25–0,50 (статичне 1/B = 0,286), висота поверхні −110…+74 см, дрейф за течією; "
                 "діжки R3 спливають до стелі"],
                ["Клубок кабелів",
                 "600 → 300 см/с на вході; вибіг 85 см проти 368 см у відкритій воді; звільнення через 3 с; "
                 "3 влучання по 14 – перерізано"],
                ["Енергоелемент, [F]",
                 "ядро 60 % → 85 %, актор знищено; за 100 % – підказка FULL, відмова, предмет лишається"],
                ["Магазин торпед, [F]",
                 "резерв 224/224 – FULL; за місткості 256 – +32 торпеди, актор знищено"],
                ["Перебування в сфері без натискання [F]", "1,5 с – предмет не підібрано (8/8 перевірок пройдено)"],
                ["Телепорт A → B",
                 "2,01 с у кінематичному стані; затемнення 0 → 1 → 0 по 0,8 с; вихід з v = −500 см/с по Z, "
                 "керування відновлено"],
                ["Повторний вхід у B через 0,4 с",
                 "відмова (залишок охолодження 2,57 с), лічильник відмов = 1, переходу немає"],
                ["Телепорт B → A після охолодження", "2,00 с; вихід з v = +500 см/с по Z, апарат вирівняний"],
            ],
            [6.0, 11.5],
        )
        self.para(
            "На рис. 2 показано послідовність роботи крана LARS із кадру LARS_cinematic_collision_PIE.jpg: "
            "персонаж упирається в турель, апарат утримується в захваті, рука опускає його на глибину 3 м, "
            "розкриває щелепи, після чого пілот отримує керування в кокпіті, а під час підйому щелепи знову "
            "захоплюють корпус. Колізійні форми на кістках коректно блокують персонажа і не штовхають утримуваний "
            "апарат.")
        self.figure("lars")
        self.para(
            "Контекстну взаємодію на [F] ілюструють рис. 3 і рис. 4: під прицілом відображається дія та її ефект, а "
            "стан FULL виводиться напівпрозорим і не застосовується. Після підбирання значення енергії на "
            "шкалі HUD і повідомлення термінального журналу змінюються відповідно до таблиці 5.")
        self.figure("prompts")
        self.figure("cell")
        self.para(
            "Станції телепортації показано на рис. 5–7. Труба шахти заповнює круглий отвір рамки концентрично, зазор "
            "у гирлі дорівнює 0,0 см, трасування вздовж осі отвору й осі проходу досягають торцевої заглушки "
            "шахти, а зонд розміром з апарат нічого не зачіпає.")
        self.figure("tp_a")
        self.figure("tp_b")
        self.figure("tp_views")
        self.para(
            "Фізику діжок на хвилях підтверджено телеметрією: частка занурення коливається навколо статичного "
            "значення 1/B, а вертикальне положення повторює профіль поверхні Герстнера, тоді як контейнер "
            "масою 1500 кг залишається нерухомим за будь-якого стану моря. Відкритим питанням залишається "
            "стійкість пружини ватерлінії за дуже низької частоти кадрів (близько 3 кадрів/с у фоновому режимі "
            "редактора), яку можна усунути розрахунком сил на кожному підкроці фізики.")

    # ------------------------------------------------------------------ conclusions
    def conclusions(self):
        self.para(
            "У ході лабораторної роботи засвоєно компонентну модель Unreal Engine 5: ієрархію UObject – AActor – "
            "APawn – ACharacter, розподіл обов’язків між UActorComponent, USceneComponent і UPrimitiveComponent та "
            "систему профілів колізій з відгуками Block, Overlap і Ignore, типами об’єктів і каналами трасування. "
            "Сцену рівня «Підводний світ» очищено від 255 зайвих ресурсів і наповнено понад 170 акторами, "
            "середньовічні заповнювачі замінено бруталістськими модулями, розгорнуто макрокаркас вежі A та кластер "
            "C-01 /home/a03 з автоматичною перевіркою прохідності. У 3ds Max процедурно розроблено чотири власні "
            "3D-моделі – артикульований кран із 12-кістковим скелетом, деформований шлюз, шинопровід і фізичний "
            "контейнер – з UV-розгорткою, сокетами та простими колізіями UCX, коректність яких підтверджено "
            "аналітичними й трасувальними тестами.")
        self.para(
            "Програмно на C++ реалізовано універсальний компонент "
            "UAOSFluidPhysicsComponent, який поєднує хвилі Герстнера, силу Архімеда й опір Морісона із залежністю "
            "впливу хвиль від маси тіла, завдяки чому діжка масою 45 кг плаває на хвилях, а контейнер масою 1500 кг "
            "лишається нерухомим. Створено три категорії інтерактивних акторів – жорсткі та «м’які» перешкоди, "
            "фізичні рухомі об’єкти та предмети зміни стану гравця з контекстною взаємодією на [F] – і двосторонню "
            "тригерну телепортацію з кінематичним втягуванням, затемненням камери та захистом від зациклення. "
            "Автоматизовані тести PIE підтвердили відповідність поведінки всіх систем поставленим вимогам, а "
            "отримані навички побудови тригерних і фізичних систем є основою для подальшої розробки ігрового "
            "процесу.")

    # ------------------------------------------------------------------ checks & save
    def validate(self):
        texts = []
        body = self.doc.element.body
        for t in body.iter(qn("w:t")):
            texts.append(t.text or "")
        full = "".join(texts)
        if "—" in full:
            raise SystemExit("Помилка: у документі знайдено довге тире (—). Використовуйте коротке (–).")
        # подвійні порожні рядки між текстовими абзацами
        return len(full)

    def save(self, out: Path):
        out.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                    help="корінь проєкту AOS_DK (типово – тека над Tools/)")
    ap.add_argument("--out", type=Path, default=None, help="шлях до вихідного .docx")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    out = args.out or (root / TARGET_REL)

    rep = Report(root)
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
