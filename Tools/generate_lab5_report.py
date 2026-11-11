# -*- coding: utf-8 -*-
"""
AOS-DK | Генератор звіту до лабораторної роботи № 5 «Реалізація NPC ботів з використанням засобів штучного
інтелекту» (варіант № 10 «Підводний світ»).

Движок верстки (поля 25/10/20/20 мм, Times New Roman 14, інтервал 1,5, абзацний відступ 1,25 см, рамки лістингів
Courier New 10, таблиці, формули, колонтитул з номером сторінки) – без змін із Tools/generate_lab_report.py
(клас Report). Тут перевизначено лише змінні поля титульного аркуша та тіло звіту, додано рамки-заповнювачі для
скріншотів. Титульний аркуш береться з Docs/Templates/Шаблон_звіту_ПРІ_2026.docx.

Джерела даних: claude/AOS_Lab5_Reaper_Pike_DCC_Build_Report_2026-11-11.md (моделі, сокети),
claude/AOS_Lab5_Phase2_BT_Nodes_Report_2026-11-11.md (Behavior Tree, C++), claude/AOS_Lab5_Deploy_PIE_Report_2026-11-11.md
(арена, PIE 25/25) та Saved/Lab5_Reaper_PIE.json, Saved/Lab5_Followup_PIE.json; фрагменти коду – з
Source/AOS_DK/Enemies/Reaper/.

Запуск:  python Tools/generate_lab5_report.py [--root <AOS_DK>] [--template <.docx>] [--out <.docx>]
Результат: Docs/Звіт_ЛР5_ШІ_Боти_Ігор_Брайченко.docx
"""
from __future__ import annotations

import glob
import os

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate_lab_report as base                       # noqa: E402  (движок верстки ЛР4)

from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT   # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH            # noqa: E402
from docx.oxml import OxmlElement                        # noqa: E402
from docx.oxml.ns import qn                              # noqa: E402
from docx.shared import Cm, Inches                               # noqa: E402

# =====================================================================================================================
# 1. Метадані (підміна констант движка до створення документа)
# =====================================================================================================================
TARGET_REL = Path("Docs") / "Звіт_ЛР5_ШІ_Боти_Ігор_Брайченко.docx"
base.LAB_NUMBER = 5
base.TOPIC = "Реалізація NPC ботів з використанням засобів штучного інтелекту"
base.GOAL = ("Навчитися створювати NPC ворогів зі скелетною сіткою та програмувати їхню поведінку засобами "
             "штучного інтелекту: Behavior Tree, Blackboard, Perception та навігаційну сітку")
base.TARGET_REL = TARGET_REL

C = WD_ALIGN_PARAGRAPH.CENTER
SHOT_DIR = str(Path(__file__).resolve().parent.parent / "Saved" / "Screenshots" / "Lab5")
W = base.TEXT_WIDTH.cm                                   # 17,5 см

base.FIGURES["reaper"] = (
    "Claude outputs/SK_OOMReaper_preview.png", 14.5,
    "Модель SK_OOMReaper у вікні перегляду 3ds Max: гексапод, щогла сенсорів, дорсальний маніпулятор і шість лап")

# =====================================================================================================================
# 2. Зміст
# =====================================================================================================================
THEORY = [
    "Ігровий штучний інтелект в Unreal Engine 5 побудований на розділенні «тіла» і «мозку». Тілом є APawn або "
    "ACharacter: скелетна сітка, капсула колізії та UCharacterMovementComponent, що реалізує фізику руху. Мозком "
    "є AAIController, який володіє пішаком (Possess), приймає рішення і керує ним командами MoveTo, SetFocus та "
    "RunBehaviorTree. Такий поділ дозволяє змінювати поведінку, не чіпаючи модель руху, і навпаки. Функціональність "
    "підключається модулями AIModule, GameplayTasks і NavigationSystem, які додаються до PublicDependencyModuleNames "
    "у файлі AOS_DK.Build.cs. У лабораторній роботі № 3 вороги-Daemon були звичайними акторами з детермінованим "
    "скінченним автоматом (FSM); у цій роботі застосовано повний стек: контролер, систему сприйняття, дерево "
    "поведінки та навігаційну сітку.",

    "Скінченний автомат (FSM) описує поведінку множиною станів і переходів між ними. Із зростанням кількості станів n "
    "кількість можливих переходів зростає до n(n − 1), кожну нову поведінку доводиться вручну з’єднувати з усіма "
    "існуючими, а умови переривання розсіюються по коду. Дерево поведінки (Behavior Tree, BT) організує рішення як "
    "ієрархію вузлів: Selector виконує дочірні вузли до першого успішного, Sequence – до першої невдачі, а листя "
    "дерева (Task) виконують дію і повертають Succeeded, Failed або InProgress. Декоратори (Decorator) є умовами "
    "допуску до гілки, сервіси (Service) періодично оновлюють дані. Режими Observer Aborts (Self, Lower Priority, "
    "Both) дозволяють перервати поточну дію одразу, як змінилася умова, без опитування в кожному кадрі, тому "
    "дерево реактивне, а нову гілку додають, не змінюючи решту.",

    "Blackboard є типізованою пам’яттю дерева: UBlackboardData описує ключі (Object, Vector, Bool, Float, Int, "
    "Enum), UBlackboardComponent зберігає їхні значення для кожного ШІ-агента. Сервіс і контролер записують у "
    "Blackboard результати сприйняття (ціль, відстань, видимість), а декоратори та задачі читають їх, тому "
    "сприйняття та ухвалення рішень відокремлені одне від одного, а зміна ключа автоматично запускає перевірку "
    "декораторів-спостерігачів.",

    "Система сприйняття (Perception System) представлена компонентом UAIPerceptionComponent контролера. Кожне "
    "відчуття налаштовується конфігурацією: UAISenseConfig_Sight (SightRadius, LoseSightRadius, "
    "PeripheralVisionAngleDegrees – півкут конуса огляду, AutoSuccessRangeFromLastSeenLocation, MaxAge), "
    "UAISenseConfig_Hearing (HearingRange, події UAISense_Hearing::ReportNoiseEvent) та UAISenseConfig_Damage. "
    "Фільтрація за належністю (DetectionByAffiliation) спирається на інтерфейс IGenericTeamAgentInterface і "
    "FGenericTeamId. Результат надходить у делегат OnTargetPerceptionUpdated у вигляді FAIStimulus, що містить "
    "тип відчуття, місце та ознаку успішного виявлення (WasSuccessfullySensed). Джерела подразників "
    "реєструються компонентом UAIPerceptionStimuliSourceComponent або автоматично.",

    "Навігацію виконує Recast NavMesh: ARecastNavMesh розбиває прохідну геометрію в межах NavMeshBoundsVolume "
    "на полігони з урахуванням радіуса, висоти, максимальної висоти сходинки й нахилу агента. Область навігації "
    "UNavArea задає вартість проходження (DefaultCost) і фіксовану вартість входу (FixedAreaEnteringCost), а "
    "UNavModifierComponent позначає нею довільний об’єм. Фільтр UNavigationQueryFilter перевизначає ці вартості "
    "для конкретного запиту, тому той самий об’єм для одного агента є перешкодою, а для іншого – звичайною "
    "підлогою. Пошук шляху (A*) мінімізує сумарну вартість",
]
THEORY_AFTER_NAV = (
    "де L_{i} – довжина i-го відрізка шляху, c_{i} – вартість навігаційної області, в якій він лежить, e_{j} – "
    "вартості входу в області. Режим Runtime Generation = Dynamic Modifiers Only дозволяє вмикати й вимикати "
    "області під час гри без повної перебудови сітки.")
THEORY_IK = (
    "Процедурна анімація ніг ґрунтується на аналітичній оберненій кінематиці (IK) двокісткового ланцюга. Якщо "
    "довжини стегна й гомілки дорівнюють a та b, а відстань від суглоба до цільової точки стопи дорівнює d, то "
    "внутрішній кут коліна визначає закон косинусів")
THEORY_IK_AFTER = (
    "за умови |a − b| ≤ d ≤ a + b; поза діапазоном ціль притискають до досяжної сфери. Положення цілей стоп "
    "визначають трасуванням униз від проєкції кроку, а чергування ніг у «триподній ході» (дві групи по три ноги) "
    "надає ходу стійкості. Обчислення виконуються у структурі FAnimInstanceProxy в робочому потоці, тому "
    "AnimGraph потрібен лише для виводу пози, а вся логіка залишається у C++.")

TASK_INTRO = "Відповідно до методичних вказівок до лабораторної роботи необхідно виконати такі завдання:"
TASK_ITEMS = [
    ("1.", "Створити додатково до ворогів, реалізованих у лабораторній роботі №3 NPC ворога з використанням "
           "шаблону скелетної сітки (повинен відповідати індивідуальному варіанту) та шкали здоров’я відмінних від "
           "програмованих ворогів та головного персонажа (програмовані та NPC вороги одночасно повинні "
           "перебувати на сцені). У розробленого ворога повинна бути в наявності зброя, яка прикріплюється до його "
           "скелета як окремий асет.", []),
    ("2.", "Запрограмувати поведінку для NPC ворога з використанням засобів штучного інтелекту та відповідних "
           "анімацій:", [
        "пошук головного персонажа на сцені: пересування по сцені, зупинки та оглядання для визначення "
        "оптимального маршруту, перехід на біг при виявленні в його полі огляду головного персонажа;",
        "нанесення незначної шкоди головному персонажу у разі його перебування в радіусі дії зброї NPC ворога;",
        "ухилення від спроб нанесення йому шкоди, імовірність успіху якого збільшується пропорційно до дальності "
        "атаки головного персонажа.",
    ]),
    ("3.", "Реалізувати перешкоду для NPC ворога за допомогою механізму тригерів («сліпа зона», сповільнення "
           "руху з допомогою отруйних об’єктів, тощо).", []),
]
VARIANT_VERBATIM = "Варіант №10 «Підводний світ»"
VARIANT_TEXT = (
    "Відповідно до варіанта дія відбувається на підводній станції AOS-DK, де «головним персонажем» є підводний "
    "апарат Shell-1, а його здоров’я – запас енергії ядра (шкода ворога вимірюється у відсотках цього запасу). "
    "Як NPC ворога розроблено шестилапого донного ходока RPR-6 «OOM Reaper», що патрулює затоплену арену на "
    "відмітці Z = −9800 см, а як перешкоду – підводний басейн розсолу «Heap Brine Pool». Ворога розміщено на тій "
    "самій сцені Lvl_FirstPerson, де працюють програмовані Daemon з лабораторної роботи № 3.")

# ---------------------------------------------------------------------------------------------------------------------
# Фрагменти коду (скорочено, логіка збережена; рядки ≤ 78 символів)
# ---------------------------------------------------------------------------------------------------------------------
CODE_CONTROLLER = r"""
// AOS_AIController.cpp: команда 9 та налаштування Perception
AAOS_AIController::AAOS_AIController()
{
    SetGenericTeamId(FGenericTeamId(ReaperTeamId));        // команда "oom"
    PerceptionComp = CreateDefaultSubobject<UAIPerceptionComponent>(
        TEXT("PerceptionComp"));
    SetPerceptionComponent(*PerceptionComp);

    SightConfig = CreateDefaultSubobject<UAISenseConfig_Sight>(
        TEXT("SightConfig"));
    SightConfig->SightRadius = SightRadius;                // 2600 см
    SightConfig->LoseSightRadius = LoseSightRadius;        // 3000 см
    SightConfig->PeripheralVisionAngleDegrees = SightHalfAngle;  // 75 град
    SightConfig->AutoSuccessRangeFromLastSeenLocation = 400.f;
    SightConfig->SetMaxAge(4.f);

    HearingConfig = CreateDefaultSubobject<UAISenseConfig_Hearing>(
        TEXT("HearingConfig"));
    HearingConfig->HearingRange = HearingRange;            // 4000 см
    HearingConfig->SetMaxAge(4.f);
    // DamageConfig створено аналогічно (MaxAge 6 с)

    PerceptionComp->ConfigureSense(*SightConfig);
    PerceptionComp->ConfigureSense(*HearingConfig);
    PerceptionComp->ConfigureSense(*DamageConfig);
    PerceptionComp->SetDominantSense(SightConfig->GetSenseImplementation());
    PerceptionComp->OnTargetPerceptionUpdated.AddDynamic(
        this, &AAOS_AIController::HandleTargetPerceptionUpdated);
}
"""

CODE_PERCEPTION_CB = r"""
// AOS_AIController.cpp: бачить ціль - біг у тому самому кадрі
void AAOS_AIController::HandleTargetPerceptionUpdated(AActor* Actor,
                                                      FAIStimulus Stimulus)
{
    if (!R || R->IsDead() || bShutDown || !IsHostileActor(Actor)) { return; }

    if (Stimulus.Type == UAISense::GetSenseID<UAISense_Sight>()
        && Stimulus.WasSuccessfullySensed())
    {
        TargetShell = Cast<AShellPawn>(Actor);
        bHasLineOfSight = true;
        SetThreatLevel(EAOSThreatLevel::Hostile);
        R->SetLocomotionMode(EAOSLocomotionMode::Scuttle);  // 620 см/с
        SetFocus(Actor, EAIFocusPriority::Gameplay);
    }
    else if (Stimulus.Type == UAISense::GetSenseID<UAISense_Hearing>()
             && ThreatLevel != EAOSThreatLevel::Hostile)
    {
        InvestigateLocation = ProjectToNavBelow(Stimulus.StimulusLocation);
        SetThreatLevel(EAOSThreatLevel::Suspicious);
        R->SetLocomotionMode(EAOSLocomotionMode::Investigate);
    }
}
"""

CODE_WEAPON = r"""
// AOS_AIWeapon.cpp: SweepStrike(), не більше одного влучання за змах
FCollisionObjectQueryParams Objects;
Objects.AddObjectTypesToQuery(ECC_Pawn);
Objects.AddObjectTypesToQuery(ECC_Vehicle);
Objects.AddObjectTypesToQuery(ECC_PhysicsBody);
const FCollisionShape Sphere = FCollisionShape::MakeSphere(SweepRadius);

// відрізок Strike_Trace_Start -> Strike_Trace_End на сокетах піка
World->SweepMultiByObjectType(Hits, Start, End, FQuat::Identity,
                              Objects, Sphere, Params);
for (const FHitResult& Hit : Hits)
{
    AShellPawn* Shell = Cast<AShellPawn>(Hit.GetActor());
    if (!Shell) { continue; }
    // StrikeDamagePercent = 5.0: 5 % енергії ядра Shell-1
    UGameplayStatics::ApplyPointDamage(Shell, StrikeDamagePercent,
        (End - Start).GetSafeNormal(), Hit, InstigatorController.Get(),
        this, UDamageType::StaticClass());
    bHitThisSwing = true;
    break;
}
"""

CODE_TREE = r"""
Selector RPR_Root                  [Service: ReaperSense, 0,10 с]
|- [bIsEvading] (Both)                       Evade
|- [ThreatLevel >= Hostile] (Both)           Selector Engage
|     |- [bInStrikeEnvelope] (LowerPriority) MeleeStrike
|     |- [bTargetAboveReach] (Both)          Pursue (Shadow)
|     `-                                     Pursue (Chase)
|- [ThreatLevel >= Suspicious] (Both)        PatrolSurvey (Investigate)
`-                                           PatrolSurvey (Patrol)
"""

CODE_SENSE = r"""
// BTService_AOS_ReaperSense.cpp: TickNode(), 10 Гц
if (Level != LastAppliedLevel)               // драбина швидкостей
{
    LastAppliedLevel = Level;
    switch (Level)
    {
    case EAOSThreatLevel::Hostile:
        R->SetLocomotionMode(EAOSLocomotionMode::Scuttle); break;  // 620
    case EAOSThreatLevel::Suspicious:
        R->SetLocomotionMode(EAOSLocomotionMode::Investigate); break; // 320
    default:
        R->SetLocomotionMode(EAOSLocomotionMode::Walk); break;     // 170
    }
}
if (Level == EAOSThreatLevel::Hostile && Shell &&
    AIC->ComputeEnvelope(Shell, Closest, bInEnvelope, bAboveReach))
{
    Distance = FVector::Dist(Closest, R->GetArmTurretLocation());
}
BB->SetValueAsBool(AOSReaperBB::bInStrikeEnvelope, bInEnvelope);
BB->SetValueAsBool(AOSReaperBB::bTargetAboveReach, bAboveReach);
BB->SetValueAsFloat(AOSReaperBB::TargetDistance, Distance);
BB->SetValueAsBool(AOSReaperBB::bIsEvading, Evasion && Evasion->IsEvading());
"""

CODE_PATROL = r"""
// BTTask_AOS_PatrolSurvey.cpp: зупинка та оглядання
constexpr float PatrolHeadings[5] = { -75.f, -35.f, 0.f, 35.f, 75.f };
constexpr float PatrolTurnRate = 60.f;      // град/с, поворот на місці
constexpr float PatrolMastAmp = 40.f;       // град, щогла 0,8 Гц
constexpr float PatrolLookUpPitch = 45.f;   // град, погляд угору 0,4 с

void UBTTask_AOS_PatrolSurvey::BeginSurvey(AAOS_AIController* AIC,
    AAOS_AIEnemyCharacter* R, FAOSPatrolSurveyMemory::FState& S) const
{
    AIC->StopMovement();                    // зупинка: ноги стають на опору
    R->SetPhase(EAOSReaperPhase::Survey);
    S.NumHeadings = 5;
    for (int32 i = 0; i < S.NumHeadings; ++i)
    {
        S.Headings[i] = PatrolHeadings[i];
    }

    // seeded shuffle: порядок напрямків різний, прогін відтворюваний
    const int32 T10 = FMath::FloorToInt(Now * 10.f);
    FRandomStream Stream(R->GetPID() * 131 + T10);
    for (int32 i = S.NumHeadings - 1; i > 0; --i)
    {
        Swap(S.Headings[i], S.Headings[Stream.RandRange(0, i)]);
    }
    S.ArrivalYaw = static_cast<float>(R->GetActorRotation().Yaw);
}
"""

CODE_MELEE = r"""
// BTTask_AOS_MeleeStrike.cpp: фіксація лінії удару
bool UBTTask_AOS_MeleeStrike::TryBeginStrike(
    UBehaviorTreeComponent& Owner) const
{
    if (!R || !BB || !R->CanStrike()) { return false; }      // кулдаун 1,5 с
    FVector Closest; bool bInEnvelope = false, bAboveReach = false;
    if (!Shell || !AIC->ComputeEnvelope(Shell, Closest, bInEnvelope,
                                         bAboveReach) || !bInEnvelope)
    {
        return false;
    }
    R->SetLocomotionMode(EAOSLocomotionMode::Combat);
    // телеграф 0,45 с -> змах 0,18 с -> відновлення 0,60 с
    return R->RequestStrike(Shell, Closest);
}
"""

CODE_EVASION_P = r"""
// AOS_EvasionComponent.cpp: закон ухилення
float UAOS_EvasionComponent::ComputeBaseProbability(float DistanceCm)
{
    const UAOS_EvasionComponent* D = GetDefault<UAOS_EvasionComponent>();
    if (DistanceCm < D->ReactionGateDistance) { return 0.f; }    // 240 см
    const float K = (D->MaxProbability - D->MinProbability)
                  / (D->FarDistance - D->PointBlankDistance);    // 3,571e-4
    return FMath::Clamp(D->MinProbability
        + K * (DistanceCm - D->PointBlankDistance),
        D->MinProbability, D->MaxProbability);
}

float UAOS_EvasionComponent::ComputeDodgeProbability(float DistanceCm) const
{
    if (Charges <= 0 || Now - LastDodgeTime < DodgeCooldown || bEvading)
    {
        return 0.f;
    }
    const float P = ComputeBaseProbability(DistanceCm) * ComputeAwareness()
                  * ComputeStateFactor() * ComputeFatigue() * HazardScale;
    return FMath::Clamp(P, 0.f, MaxProbability);
}
"""

CODE_EVASION_ACT = r"""
// EvaluateSalvo(): один детермінований кидок на залп торпед
const int32 Seed = Reaper->GetPID() * 7919 + Salvo.SalvoId;
FRandomStream Stream(Seed);
const float U = Stream.FRand();
const bool bDodge = U < PDodge;               // PDodge = P_dodge(D)

// TrySkitter(): бічний ривок на 340 см, сторона "від точки прицілу"
FVector Side = FVector::CrossProduct(FVector::UpVector, UHat)
                   .GetSafeNormal2D();
if (FVector::DotProduct(Side, AimPoint - B) > 0.f) { Side = -Side; }
Params.bFindInitialOverlaps = false;
World->SweepSingleByChannel(Hit, B, B + Side * SkitterDistance,
    FQuat::Identity, ECC_Pawn, CapsuleShape, Params);
Reaper->LaunchCharacter(Side * (SkitterDistance / SkitterDuration),
                        true, false);         // 340 см за 0,45 с

// хмара кавітації за 80 см від старої позиції, життя 1,2 с
const FVector SpawnLoc =
    Reaper->GetActorLocation() + ToAttacker * DecoyOffset;
Decoy = World->SpawnActor<AAOS_CavitationDecoy>(DecoyClass, SpawnLoc,
    ToAttacker.Rotation(), Params);
Decoy->Activate(DecoyLifetime);
// CombatThreatSubsystem: Torpedo->Retarget(Decoy, Decoy->GetActorLocation());
"""

CODE_NAV = r"""
// AOS_NavArea_Brine.cpp: вартість області для звичайного патрулювання
UAOS_NavArea_Brine::UAOS_NavArea_Brine()
{
    DefaultCost = 3.0f;
    DrawColor = FColor(0xBD, 0x93, 0xF9);        // Dracula Purple
}

// AOS_NavFilter_ReaperChase.cpp: у погоні розсіл не завадить
UAOS_NavFilter_ReaperChase::UAOS_NavFilter_ReaperChase()
{
    AddTravelCostOverride(UAOS_NavArea_Brine::StaticClass(), 1.0f);
    AddEnteringCostOverride(UAOS_NavArea_Brine::StaticClass(), 0.0f);
}
"""

CODE_TRIGGER = r"""
// AOS_AIObstacleTrigger.cpp: тригер басейну розсолу
void AAOS_AIObstacleTrigger::EnterReceiver(AActor* Other)
{
    if (!bActive || !IsValid(Other) || Other->IsA<AShellPawn>())
    {
        return;                      // апарат герметичний: імунітет
    }
    if (!Other->Implements<UAOS_HazardReceiver>()) { return; }
    bool bAlreadyIn = false;
    Receivers.Add(Other, &bAlreadyIn);
    if (!bAlreadyIn)
    {
        IAOS_HazardReceiver::Execute_EnterHazard(Other, this, HazardData);
    }
}

// AOS_AIEnemyCharacter.cpp: мінімум за активними небезпеками
Speed = FMath::Min(Speed, Pair.Value.SpeedScale);         // 0,40
Sight = FMath::Min(Sight, Pair.Value.SightRadiusScale);   // 0,5
Dodge = FMath::Min(Dodge, Pair.Value.DodgeScale);         // 0,25
"""

CODE_RESPAWN = r"""
// AOS_AIEnemyCharacter.cpp: автоматичне відродження
if (bAutoRespawn && GetWorld())
{
    GetWorldTimerManager().SetTimer(RespawnTimer, this,
        &AAOS_AIEnemyCharacter::Respawn,
        FMath::Max(RespawnDelay, 0.01f), false);
    SetLifeSpan(FMath::Max(10.f, RespawnDelay + 2.f));   // труп живе довше
}

void AAOS_AIEnemyCharacter::Respawn()
{
    AAOS_AIEnemyCharacter* Fresh = World->SpawnActorDeferred<
        AAOS_AIEnemyCharacter>(GetClass(), SpawnTransform, nullptr, nullptr,
        ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    Fresh->PatrolNodes = PatrolNodes;
    Fresh->HomeRadius = HomeRadius;
    Fresh->bAutoRespawn = bAutoRespawn;
    Fresh->RespawnDelay = RespawnDelay;                  // 6,0 с
    Fresh->FinishSpawning(SpawnTransform);   // BeginPlay: 168 HP, 3 пастки
}
"""

CODE_LOG = r"""
oom_reaper[4703] evade: D=9.0m P=0.23 u=0.17 charges=3 -> hold
oom_reaper[4703] evade: D=23.0m P=0.15 u=0.22 charges=3 -> hold
oom_reaper[4703] evade: D=8.5m P=0.21 u=0.26 charges=3 -> DODGE
oom_reaper[4703] evade: D=9.1m P=0.23 u=0.31 charges=3 -> hold
LogAOSAI:   D= 24.0 m  analytic=0.7643  empirical=0.7670  |d|=0.0027  PASS
LogAOSAI:   D= 25.0 m  analytic=0.8000  empirical=0.8002  |d|=0.0002  PASS
LogAOSAI: aos.ai.DodgeMonteCarlo: PASS
oom_reaper[4707]: respawn in 6.0 s
"""

# ---------------------------------------------------------------------------------------------------------------------
# 25 перевірок PIE: (вимога, перевірка, виміряно, рисунок)
# ---------------------------------------------------------------------------------------------------------------------
PIE_CHECKS = [
    ("1", "Скелетна сітка NPC", "SK_OOMReaper", ""),
    ("1", "Анім-екземпляр", "UAOS_ReaperAnimInstance (нативний проксі)", ""),
    ("1", "Зброя як окремий асет на сокеті", "SM_WPN_SigkillPike на SOCKET_Weapon_Dorsal", "рис. 2"),
    ("1", "Контролер", "AAOS_AIController", ""),
    ("1", "Співіснування з Daemon", "2 Daemon і 1 Reaper живі на сцені", "рис. 9"),
    ("2.1", "Патруль зі зупинками та оглядом", "патруль 170 см/с, огляд 0 см/с; фази PATROL, SURVEY", "рис. 5"),
    ("2.1", "Біг 620 см/с при виявленні", "v_max 576 см/с; перемикання в момент HOSTILE; 90 % за 0,392 с",
     "рис. 5"),
    ("2.1", "Перемикання швидкості не довше 0,2 с", "затримка 0,0 с", ""),
    ("2.2", "Удар = 5 % енергії ядра", "зниження 5,0 % і 5,0 %; інтервал ударів 2,76 с", "рис. 6"),
    ("2.3", "Закон P = P_base(D) · обізнаність", "9 м: 0,23; 23 м: 0,15; розрахункові 6 м: 0,1214, 10 м: 0,2643, "
                                                  "15 м: 0,4429, 25 м: 0,80", "рис. 7"),
    ("2.3", "Журнал примусового ухилення", "D = 8,5 м, P = 0,21, u = 0,26, 3 заряди: DODGE", "рис. 7"),
    ("2.3", "Бічний ривок 340 см", "максимальне зміщення 344 см (до виправлення: 0, evade: blocked)", ""),
    ("2.3", "Кавітаційна пастка", "зміщення 80 см від старої позиції; життя 1,19 с", "рис. 7"),
    ("2.3", "Торпеди перенацілюються на пастку", "мінімум 125 см до пастки; HP Reaper без змін (Δ = 0)", "рис. 7"),
    ("2.3", "Влучання без ухилення", "HP 168 → 154 (14 одиниць)", ""),
    ("2.3", "Діагностика: ривок за океанічного боксу", "зміщення 342 см; кидок DODGE", ""),
    ("2.3", "Діагностика: торпеди + ривок", "125 см до пастки; HP Δ = 0; життя пастки 1,2 с", ""),
    ("2.3", "Монте-Карло закону ухилення", "20 000 кидків на точку; |Δ| ≤ 3σ у всіх рядках 4–25 м", ""),
    ("2.3", "Ухилення в розсолі ×0,25", "розсіл: 0,01; суша: 0,21 (на ~8,5 м)", "рис. 8"),
    ("3", "Reaper у зоні розсолу", "bInHazard = true", "рис. 8"),
    ("3", "Швидкість −60 %", "170 → 68 см/с (×0,40)", "рис. 8"),
    ("3", "Дальність бачення удвічі менша", "2600 → 1300 см", "рис. 8"),
    ("3", "Відновлення після виходу", "швидкість 169 см/с, бачення 2600 см; 3,36 с", ""),
    ("3", "Shell-1 імунний", "перекриття тригера немає; демпфування не змінилося (0,10 / 0,50); "
                              "Δ енергії −0,06", ""),
    ("1", "RSS Page Map (інформаційна)", "компонент присутній, 16 резидентних сторінок; "
                                          "відображення на рис. 3", "рис. 3"),
]

PIE_FOLLOWUP = [
    ("F1", "Стопи на підлозі (6 майданчиків)", "зазор 152–172 см → 0,13 см; 1004 вибірки"),
    ("F2", "Шлях: звичайний обходить, погоня прямо", "2943 см проти 2400 см"),
    ("F2", "Спокійний патруль обходить басейн", "вхід у зону не зафіксовано"),
    ("F2", "Погоня входить у розсіл і перетинає його", "вхід на 3,2 с, 4,02 с у зоні, відхилення від осі 9 см"),
    ("F2", "Фільтр погоні лише під час переслідування", "патруль і розслідування лишаються на стандартному "
                                                         "фільтрі"),
    ("F3", "Автоматичне відродження ×2", "6,0 с; 168/168 HP; 3 пастки; 1–3 см від маркера; фаза PATROL"),
]


# =====================================================================================================================
# 3. Звіт
# =====================================================================================================================
class Lab5Report(base.Report):

    # ------------------------------------------------------------------ рамки-заповнювачі скріншотів
    def placeholder(self, expected_no, title, hint=None, height_cm=None):
        """Реальний скріншот із Unreal Engine (Saved/Screenshots/Lab5) + підпис «Рис. N. …» (п. 14)."""
        self.fig_no += 1
        assert self.fig_no == expected_no, (self.fig_no, expected_no, title)
        assert not title.endswith(".")
        found = sorted(glob.glob(os.path.join(SHOT_DIR, f"shot_{expected_no:02d}_*.png")))
        if not found:
            raise FileNotFoundError(f"немає скріншота для рис. {expected_no} у {SHOT_DIR}")
        pic = base.fmt(self.doc.add_paragraph(), align=C, first=Cm(0), line=1.0, keep_next=True)
        pic.add_run().add_picture(found[0], width=Inches(6.0))
        cap = base.fmt(self.doc.add_paragraph(), align=C, first=Cm(0))
        base.set_run_font(cap.add_run(f"Рис. {self.fig_no}. {title}"))
        self.last_blank = False
        return self.fig_no

    def real_figure(self, expected_no, key):
        n = self.figure(key)
        assert n == expected_no, (n, expected_no)

    def expect_table(self, n):
        assert self.tab_no + 1 == n, (self.tab_no + 1, n)

    # ------------------------------------------------------------------ тіло звіту
    def build(self):
        self.section("Теоретичні відомості")
        for t in THEORY[:-1]:
            self.para(t)
        self.para(THEORY[-1] + ":")
        n_nav = self.formula("S = Σ L_{i}·c_{i} + Σ e_{j},")
        self.para(THEORY_AFTER_NAV + f" Формула ({n_nav}) визначає вибір маршруту.")
        self.para(THEORY_IK + ":")
        n_ik = self.formula("cos γ = (a^{2} + b^{2} − d^{2}) / (2ab),")
        self.para(THEORY_IK_AFTER + f" Кут γ у формулі ({n_ik}) використано для ніг ходока.")

        self.section("Завдання")
        self.para(TASK_INTRO)
        for marker, text, bullets in TASK_ITEMS:
            self.list_item(marker, text)
            for b in bullets:
                self.list_item("●", b, level=1)
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
        self.subsection("1. Концепція та 3D-моделювання ворога RPR-6 OOM Reaper і зброї SM_WPN_SigkillPike")
        self.para(
            "Станція AOS-DK, за легендою, зазнала переповнення пам’яті: ядро запускає підсистему OOM і висилає "
            "«жнеців» (oom_reaper), які знищують процес із найбільшим споживанням. Таким процесом є підводний "
            "апарат гравця Shell-1. Ворога названо RPR-6 «OOM Reaper»: це шестилапий донний ходок довжиною 4,2 м, "
            "що ходить по підлозі затоплених приміщень. Рух по дну обрано свідомо: Recast NavMesh будується на "
            "будь-якій статичній геометрії, тому працює повний стек ШІ (MoveTo, NavArea, фільтри), а силует важкого "
            "ходока протилежний плаваючим Daemon з лабораторної роботи № 3.")
        self.para(
            "Модель SK_OOMReaper побудовано процедурно скриптом Tools/max_build_SK_OOMReaper.py (3ds Max 2027, "
            "сантиметри, вісь Z угору, масштаб 1,0, перед = +X). Розміри в стійці становлять 420 × 280 × 180 см, "
            "сітка містить 20 016 трикутників у 248 деталях. Скелет має 36 кісток: ланцюг із завдання містить 33, "
            "до нього додано Jaw_L_Bone, Jaw_R_Bone (щелепи) та Tail_Drum_Bone (барабан OOM). Кожна з шести ніг "
            "складається з кісток Coxa, Femur, Tibia, Foot (довжина стегна близько 75 см, гомілки близько 140 см), "
            "щогла сенсорів – із Mast_Yaw, Mast_Pitch, Mast_Head, а дорсальний маніпулятор – із Arm_Yaw, Arm_Pitch1, "
            "Arm_Pitch2, Arm_Wrist (рис. 1). Скінінг жорсткий: кожна вершина має рівно один вплив. Імпорт у UE "
            "виконано застарілим імпортером FBX (на час імпорту Interchange.FeatureFlags.Import.FBX = 0), оскільки "
            "Interchange відкидає оболонки UCX; скрипт Tools/ue_import_lab5_reaper_assets.py створив "
            "SK_OOMReaper, SKEL_OOMReaper, PA_OOMReaper і 9 сокетів (Weapon_Dorsal, UI_Health, Decoy_Launcher та "
            "6 сокетів ніг). Результати перевірки наведено в таблиці 1.")
        self.real_figure(1, "reaper")
        self.expect_table(1)
        self.table(
            "Параметри та вимірювання SK_OOMReaper",
            ["Параметр", "Ціль", "Виміряно"],
            [
                ["Габарити в стійці, см", "420 × 280 × 180", "420,0 × 279,5 × 180,0"],
                ["Кістки", "36", "36, батьки збігаються (похибка 0,0 см)"],
                ["Поза прив’язки", "осі збігаються зі світовими", "Root, Body, Mast, Arm, Jaw, Tail_Drum: "
                                                                    "тотожне обертання"],
                ["Скінінг", "1 вплив на вершину", "0 вершин із кількістю впливів ≠ 1"],
                ["Трикутники / вершини", "≤ 45 000", "20 016 / 10 504"],
                ["UV0 / UV1", "без перекриттів", "0 перекритих граней"],
                ["Слоти матеріалів", "4", "MS_CastMetal, MS_RubberSeal, MS_HazardPaint, MS_StatusEmissive"],
                ["Сокети", "9", "9, позиції збігаються з ригом"],
            ],
            [4.8, 4.4, 8.3],
        )
        self.para(
            "Зброя SM_WPN_SigkillPike є дуговим піком довжиною 288 см, шириною голови 30 см і висотою 24 см "
            "(голова 22 см), який створено окремим статичним асетом (Tools/max_build_SM_WPN_SigkillPike.py, "
            "4764 трикутники). Колізію утворюють 4 опуклі оболонки UCX (24, 8, 8 і 8 вершин): призма комлі, "
            "муфти й конденсатора, звужена коробка стрижня та дві коробки зубців. Пік утримується затискачем зап’ястка: "
            "ділянка рукояті 8 × 8 см затиснута між ободами муфти Ø 12 см. Сокети піка: Mount_Base, Arc_Tip_L, "
            "Arc_Tip_R, Strike_Trace_Start і Strike_Trace_End (відрізок X від 170 до 262 см). У грі пік прикріплює "
            "до скелета клас AAOS_AIWeapon на сокет SOCKET_Weapon_Dorsal кістки Arm_Wrist_Bone, тобто зброя "
            "прикріплюється як окремий асет (рис. 2, табл. 2).")
        self.placeholder(2, "Зброя SM_WPN_SigkillPike: чотири оболонки UCX у редакторі Unreal Engine",
                         "Скріншот вікна 3ds Max або Static Mesh Editor з увімкненою колізією та сокетами")
        self.expect_table(2)
        self.table(
            "Параметри та вимірювання SM_WPN_SigkillPike",
            ["Параметр", "Ціль", "Виміряно"],
            [
                ["Довжина / голова / висота, см", "288 / 30 / 22", "287,97 / 29,89 / 24,0"],
                ["Муфта / рукоять, см", "Ø 12 / Ø 8", "Ø 12 / 8 × 8 (прямі площини)"],
                ["Колізія UCX", "4, не більше 32 вершин", "4 елементи: 24 / 8 / 8 / 8"],
                ["Сокети", "5", "Mount_Base, Arc_Tip_L/R, Strike_Trace_Start/End"],
                ["Матеріали", "3", "MS_HardenedAlloy, MS_PowerCoil, MS_AccentEmissive"],
                ["Трикутники", "≤ 6000", "4764"],
            ],
            [5.3, 4.3, 7.9],
        )
        self.para(
            "Шкала здоров’я ворога відрізняється від обох наявних елементів гри: смуги Daemon (екранний UMG) і "
            "кокпітного HUD (Slate). Компонент UAOS_RSSPageMapComponent (так звана 3D Page Map) будує у світовому "
            "просторі сітку 4 × 4 видавлених «сторінок пам’яті»: кількість резидентних сторінок дорівнює "
            "ceil(16 · HP / HP_max), колір рамки кодує стан тривоги, а три шестикутні індикатори показують "
            "кількість кавітаційних пасток. Максимальне здоров’я ворога становить 168 одиниць, тобто 12 влучань "
            "мікроторпедами по 14 одиниць. Під час тестування PIE підтверджено наявність компонента (16 резидентних "
            "сторінок); візуальне відображення подано на рис. 3.")
        self.placeholder(3, "Тривимірна шкала здоров’я RSS Page Map над ворогом у PIE",
                         "Скріншот PIE: сітка 4 × 4 над Reaper із боку камери Shell-1")
        self.para(
            "Рух ніг повністю процедурний. Клас UAOS_ReaperAnimInstance із проксі FAOS_ReaperAnimProxy (структури "
            "AOS_ReaperGait.h/.cpp та AOS_ReaperIK.h) керує триподною ходою (групи {LF, RM, LB} та {RF, LM, RB}), а "
            "кожну ногу розв’язує аналітична IK за формулою (2): кут Coxa знаходять через atan2, а кути стегна й "
            "гомілки – законом косинусів. Ціль стопи шукається трасуванням униз; для шести майданчиків стоп "
            "SOCKET_Foot_L1…R3 після виправлення зазор до підлоги становить 0,13 см (до виправлення: 152–172 см, "
            "причину описано в підрозділі 4).")

    # ------------------------------------------------------------------ 2
    def step_2(self):
        self.subsection("2. C++ архітектура: AAOS_AIEnemyCharacter, AAOS_AIController, AAOS_AIWeapon")
        self.para(
            "Уся логіка ШІ ворога реалізована в C++ у теці Source/AOS_DK/Enemies/Reaper/ (близько 5500 рядків у "
            "модулі ворога, у тому числі підтека AI/ з деревом поведінки). Blueprint-класи BP_OOMReaper, "
            "BP_AIWeapon_SigkillPike та BP_AIObstacle_BrinePool містять лише значення за замовчуванням і посилання "
            "на ресурси, без вузлів логіки; анімацію виконує нативний UAOS_ReaperAnimInstance без логіки в AnimGraph. "
            "Збірка AOS_DKEditor Win64 Development із прапорцем -WarningsAsErrors завершилася без помилок і "
            "попереджень (36 дій). Ієрархію класів наведено в таблиці 3.")
        self.expect_table(3)
        self.table(
            "Основні C++ класи NPC-ворога",
            ["Клас", "Базовий клас", "Призначення"],
            [
                ["AAOS_AIEnemyCharacter", "ACharacter", "тіло ворога: капсула R 120 / HH 135, здоров’я 168, "
                                                         "швидкості 170 / 320 / 620 / 120 см/с, відродження"],
                ["AAOS_AIController", "AAIController", "мозок: Perception, команда 9, запуск BT, Blackboard"],
                ["AAOS_AIWeapon", "AActor", "пік на сокеті; змах із трасуванням сферою, 5 % шкоди ядру"],
                ["UAOS_EvasionComponent", "UActorComponent", "модель ухилення: ймовірність, ривок, пастка"],
                ["AAOS_CavitationDecoy", "AActor", "кавітаційна хмара, що перехоплює торпеди"],
                ["AAOS_AIObstacleTrigger", "AActor", "тригер перешкоди «Heap Brine Pool»"],
                ["UAOS_ReaperAnimInstance", "UAnimInstance", "процедурна хода, IK лап, наведення щогли та руки"],
            ],
            [5.1, 3.6, 8.8],
        )
        self.para(
            "AAOS_AIEnemyCharacter успадковує ACharacter і реалізує інтерфейс IAOS_HazardReceiver, через який "
            "перешкода впливає на рух і сенсори. Рух обмежено режимом MOVE_Walking (NavAgentProps.bCanSwim = false), "
            "гравітацію зменшено до 0,55 для імітації плавучої ваги, а коробка HitVolume 420 × 380 × 200 см "
            "приймає торпеди й проміні прицілювання. Контролер AAOS_AIController відповідає за сприйняття (табл. 4); "
            "налаштування конусів зору та слуху наведено у фрагменті коду нижче.")
        self.expect_table(4)
        self.table(
            "Налаштування системи сприйняття ворога",
            ["Відчуття", "Параметр", "Значення"],
            [
                ["Зір", "SightRadius / LoseSightRadius", "2600 см (26 м) / 3000 см"],
                ["Зір", "PeripheralVisionAngleDegrees", "75° (конус 150°)"],
                ["Зір", "AutoSuccessRangeFromLastSeenLocation / MaxAge", "400 см / 4 с"],
                ["Слух", "HearingRange / MaxAge", "4000 см (40 м) / 4 с"],
                ["Шкода", "MaxAge", "6 с"],
                ["Команда", "TeamId (IGenericTeamAgentInterface)", "9 («oom»)"],
                ["Логіка", "LoseTargetGrace / InvestigateTimeout", "2 с / 25 с"],
            ],
            [3.0, 8.0, 6.5],
            {0: C},
        )
        self.code(CODE_CONTROLLER)
        self.para(
            "Колбек OnTargetPerceptionUpdated перемикає біг у тому самому кадрі, де зір фіксує ціль, не чекаючи "
            "такту дерева: затримка перемикання швидкості в тестах становила 0,0 с при вимозі не більше 0,2 с. Подія "
            "слуху (шум двигуна або запуск торпеди) переводить ворога в стан підозри та спрямовує його до джерела "
            "звуку. Метод IsHostileActor приймає лише AShellPawn, яким керує гравець, що не перебуває у стані "
            "Kernel Panic і не у люльці LARS, тому Daemon, дрони та торпеди ігноруються.")
        self.code(CODE_PERCEPTION_CB)
        self.para(
            "AAOS_AIWeapon реалізує зброю як окремого актора-пік, який AAOS_AIEnemyCharacter створює в BeginPlay і "
            "прикріплює до SOCKET_Weapon_Dorsal. Під час фази змаху (BeginSwing) кожен кадр виконується "
            "SweepMultiByObjectType сферою вздовж відрізка між сокетами Strike_Trace_Start та Strike_Trace_End; "
            "додатково перевіряються переміщення кінців відрізка з попереднього кадру, щоб удар не «пролітав» "
            "крізь ціль. Перше ж влучання в AShellPawn викликає ApplyPointDamage на 5 % енергії ядра, а "
            "прапорець bHitThisSwing гарантує не більше одного влучання за змах:")
        self.code(CODE_WEAPON)

    # ------------------------------------------------------------------ 3
    def step_3(self):
        self.subsection("3. Behavior Tree та дистанційне ухилення")
        self.para(
            "Дерево поведінки RPR_Root і Blackboard створюються нативно у класі AOSReaperBT (BuildBlackboard, "
            "BuildBehaviorTree), оскільки програмний інтерфейс Python не дозволяє будувати графи BT; у "
            "AAOS_AIController::StartBehaviorTree дерево запускається в OnPossess. Якщо у властивості "
            "BehaviorTreeAsset призначено створене дизайнером дерево, воно має пріоритет. Структуру дерева "
            "наведено на лістингу нижче; усі вузли є власними C++ класами (UBTTask_AOS_*, UBTService_AOS_ReaperSense, "
            "UBTDecorator_AOS_Condition), крім UBTTask_MoveTo.")
        self.code(CODE_TREE)
        self.expect_table(5)
        self.para("Ключі Blackboard і їхніх записувачів зведено в таблиці 5.")
        self.table(
            "Ключі Blackboard ворога",
            ["Ключ", "Тип", "Записує"],
            [
                ["SelfActor", "Object", "контролер (OnPossess)"],
                ["TargetActor", "Object (AShellPawn)", "контролер, сервіс"],
                ["ThreatLevel", "Enum None / Suspicious / Hostile", "контролер, сервіс"],
                ["bHasLineOfSight", "Bool", "контролер, сервіс"],
                ["TargetDistance", "Float, від турелі руки до корпусу, см", "сервіс"],
                ["TargetGroundPoint", "Vector", "сервіс"],
                ["bInStrikeEnvelope, bTargetAboveReach", "Bool", "сервіс"],
                ["LastKnownLocation, InvestigateLocation", "Vector", "контролер"],
                ["PatrolLocation, PatrolNodeIndex", "Vector, Int", "PatrolSurvey"],
                ["bIsEvading, bInHazard", "Bool", "сервіс"],
            ],
            [6.2, 6.3, 5.0],
        )
        self.para(
            "Сервіс UBTService_AOS_ReaperSense працює з частотою 10 Гц (±0,02 с). Він перевіряє чинність цілі, "
            "понижує рівень загрози Hostile → Suspicious через 2 с без прямої видимості та Suspicious → None через "
            "25 с, перемикає драбину швидкостей Walk 170 → Investigate 320 → Scuttle 620 см/с і обчислює для "
            "Blackboard найближчу точку корпусу, прапорці зони удару й «ціль вище досяжності»:")
        self.code(CODE_SENSE)
        self.para(
            "Задача UBTTask_AOS_PatrolSurvey реалізує пошук головного персонажа зі зупинками та огляданням. У режимі "
            "Patrol ворог іде до наступного вузла PatrolNodes по колу (за відсутності вузлів – до випадкової "
            "досяжної точки навколо точки появи), зупиняється і виконує 5 поворотів на місці зі швидкістю "
            "60°/с у випадковому, але відтворюваному порядку; щогла сенсорів хитається на ±40° із частотою 0,8 Гц, а "
            "на кожному другому напрямку піднімається на +45°, щоб просканувати товщу води над ворогом. У режимі "
            "Investigate (підозра) ворог іде до InvestigateLocation і виконує 7 поворотів зі швидкістю 90°/с, "
            "на кожному з яких щогла піднімається на +55°; після огляду підозру знімає. Будь-який вихід із задачі "
            "відновлює прапорці руху та положення щогли.")
        self.code(CODE_PATROL)
        self.para(
            "Завдання «біг при виявленні» виконано двома шляхами: колбек Perception (фрагмент вище) і сервіс "
            "(драбина швидкостей), тому швидкість перемикається у тому самому кадрі. Задача UBTTask_AOS_Pursue "
            "веде ворога до TargetGroundPoint (режим Chase) або утримує його під апаратом із піднятим піком "
            "(режим Shadow, якщо Shell-1 вище зони удару). Нанесення шкоди виконує UBTTask_AOS_MeleeStrike: удар "
            "складається з телеграфа 0,45 с, змаху 0,18 с та відновлення 0,60 с, між ударами діє перезаряджання "
            "1,5 с; розпочатий удар не скасовується (спостерігач-переривання завершує його, а не обриває), "
            "тому гравець бачить попереджувальний замах і може відступити:")
        self.code(CODE_MELEE)
        self.para(
            "Гілка Evade має найвищий пріоритет: коли UAOS_EvasionComponent запускає ухилення, сервіс записує "
            "bIsEvading = true, декоратор з режимом Both перериває поточну дію, а задача UBTTask_AOS_Evade "
            "зупиняє рух, скасовує удар і утримує дерево, доки прапорець не знімається (запобіжний таймаут 1,0 с).")

        self.para(
            "Ухилення від торпед реалізує UAOS_EvasionComponent. Гравець атакує керованими мікроторпедами "
            "з пропорційною навігацією, тому проста зміна позиції не рятує: головка самонаведення перенаціюється. "
            "Ворог застосовує контрзаходи: бічний ривок («скіттер») на 340 см за 0,45 с та кавітаційну пастку "
            "(AAOS_CavitationDecoy), на яку перенацілюються торпеди залпу. Кидок виконується один раз на залп "
            "(торпеди, що вилетіли протягом 0,30 с після першої, об’єднуються), а відстань атаки D є відстанню "
            "від точки пуску до найближчої точки HitVolume. Базова ймовірність ухилення лінійно, тобто "
            "пропорційно до відстані, зростає на проміжку між точковим пострілом і дальнім кордоном:")
        n1 = self.formula("P_{base}(D) = P_{min} + k·(D − D_{pb}), D_{pb} < D < D_{far},")
        self.para(
            "де P_{min} = 0,05, D_{pb} = 400 см, D_{far} = 2500 см, а крутизна k = (P_{max} − P_{min}) / "
            "(D_{far} − D_{pb}) = 0,75 / 2100 = 3,571 · 10^{−4} см^{−1}, тобто 3,57 % на кожен метр. Для "
            "D ≤ D_{pb} маємо P_{base} = P_{min}, для D ≥ D_{far} – P_{max} = 0,80, а при D < 240 см (час польоту "
            "менший за 0,15 с) ухилення неможливе: P_{base} = 0. Фактична ймовірність враховує контекст:")
        n2 = self.formula("P_{dodge} = clamp(P_{base}(D) · M_{aware} · M_{state} · M_{fat} · M_{haz}, 0, P_{max}),")
        self.para(
            f"де M_{{aware}} дорівнює 1,0 за прямої видимості, 0,5 за недавнього слуху та 0,2 в інших випадках, "
            "M_{state} дорівнює 0,3 у телеграфі удару, 0 у змаху, 0,5 у відновленні та 1 в інших фазах, M_{haz} = "
            "0,25 в розсолі, а коефіцієнт втоми")
        n3 = self.formula("M_{fat} = φ^{n}, φ = 0,6,")
        self.para(
            f"де n – кількість ухилень за останні 5 с. Ухилення неможливе, якщо запас пасток дорівнює нулю (3 "
            f"пастки, відновлення 1 за 6 с) або не минуло 1,5 с після попереднього. Опорні значення за формулою "
            f"({n1}) наведено в таблиці 6, а реалізацію формул ({n1}) і ({n2}) – у коді нижче. Результат "
            f"кидка визначає seed PID · 7919 + SalvoId, тому поведінка відтворювана, а консольна команда "
            f"aos.ai.DodgeMonteCarlo перевіряє закон серією кидків на кожну відстань (у тестах 20 000).")
        self.expect_table(6)
        self.table(
            "Базова ймовірність ухилення залежно від дальності атаки",
            ["D, м", "4", "6", "8", "10", "15", "20", "25 і більше"],
            [["P_{base}", "0,050", "0,121", "0,193", "0,264", "0,443", "0,621", "0,800"]],
            [2.5, 2.1, 2.1, 2.1, 2.2, 2.2, 2.2, 2.1],
            {i: C for i in range(0, 8)},
        )
        self.code(CODE_EVASION_P)
        self.para(
            "Після успішного кидка компонент спочатку виконує бічний ривок: напрямок «від точки прицілу» "
            "вибирається перпендикулярно лінії атаки, перевіряється вільний шлях капсули (за двох заблокованих "
            "сторін ривок пропускається, але пастка все одно запускається), далі швидкість задає LaunchCharacter "
            "340 см за 0,45 с без тертя. Потім за 80 см від старої позиції у бік нападника з’являється кавітаційна "
            "пастка з часом життя 1,2 с, а підсистема загроз викликає AMicroTorpedo::Retarget для кожної торпеди "
            "залпу:")
        self.code(CODE_EVASION_ACT)

    # ------------------------------------------------------------------ 4
    def step_4(self):
        self.subsection("4. Тригер перешкоди, арена NavMesh та автовідродження")
        self.para(
            "Перешкодою для NPC-ворога є «Heap Brine Pool» – басейн щільного розсолу, що витік із системи "
            "(AAOS_AIObstacleTrigger). Для ходока розсіл є пасткою: ноги грузнуть, оптика спотворюється на межі "
            "галокліну, а патрубки пасток забруднюються. Апарат Shell-1 герметичний і летить над поверхнею, тому "
            "перешкода стосується лише NPC: тригер реагує лише на актори з інтерфейсом IAOS_HazardReceiver і "
            "явно виключає AShellPawn. Кореневий компонент – бокс 500 × 400 × 120 см (профіль AOS_AIHazard, "
            "QueryOnly, Overlap лише для Pawn), який водночас є модифікатором навігації з областю "
            "UAOS_NavArea_Brine. Події OnComponentBeginOverlap та OnComponentEndOverlap враховують лише кореневу "
            "капсулу, тому кожен вхід і вихід фіксується один раз. Наслідки входу наведено в таблиці 7.")
        self.code(CODE_TRIGGER)
        self.expect_table(7)
        self.table(
            "Вплив зони «Heap Brine Pool» на NPC-ворога",
            ["Параметр", "Звичайно", "У розсолі"],
            [
                ["Швидкість ходьби / біг, см/с", "170 / 620", "68 / 248 (множник 0,40, тобто −60 %)"],
                ["Дальність бачення / півкут", "2600 см / 75°", "1300 см / 40°"],
                ["Множник ухилення", "1,0", "0,25; відновлення пасток призупинено"],
                ["Вартість навігаційної області (патруль)", "1,0", "3,0 (DefaultCost)"],
                ["Вартість у фільтрі погоні", "1,0", "1,0, вхід 0,0"],
                ["Повідомлення в терміналі Shell-1", "–", "heap brine - traction lost"],
            ],
            [6.7, 4.0, 6.8],
        )
        self.para(
            "Вплив на маршрути забезпечено двома фільтрами. Область UAOS_NavArea_Brine має DefaultCost = 3,0, "
            "тому спокійний патруль обходить басейн; фільтр UAOS_NavFilter_ReaperChase, який використовує "
            "UBTTask_AOS_Pursue, перевизначає вартість на 1,0 (вхідну – на 0,0), тому погоня веде ворога крізь "
            "розсіл. Контрольний запит шляху між протилежними краями басейну показав: стандартний фільтр дає обхід "
            "довжиною 2943 см, фільтр погоні – прямий шлях через басейн довжиною 2400 см. У живій погоні ворог "
            "входить у розсіл через 3,2 с, швидкість падає з 620 до 248 см/с (620 × 0,4), а перетинає басейн, "
            "відхиляючись від осі не більше ніж на 9 см. Мисливця можна виманити в пастку, а потім відійти поза "
            "зону удару й стріляти по повільній, напівсліпій цілі.")
        self.code(CODE_NAV)
        self.para(
            "Арену побудовано скриптами Tools/setup_lab5_arena.py і Tools/deploy_lab5_arena.py (ідемпотентні): "
            "підводна арена приблизно 40 × 40 м на відмітці Z = −9800 см біля кластера C-01 A-3, об’єм "
            "RPR_Arena_NavBounds, Runtime Generation = Dynamic Modifiers Only, агент «Reaper» з радіусом 140 см і "
            "висотою 280 см у Config/DefaultEngine.ini (RecastNavMesh-Reaper). На арені розміщено ворога RPR_A "
            "(BP_OOMReaper), басейн RPR_BrinePool_01 (BP_AIObstacle_BrinePool, фіолетовий відтінок #BD93F9) і "
            "чотири вузли патрулювання RPR_Node_00…03; Daemon з лабораторної роботи № 3 не змінювалися (рис. 4).")
        self.placeholder(4, "Арена на Z = −9800 см: комірки NavMesh, що проєктуються на навігаційну сітку",
                         "Скріншот редактора: клавіша P (NavMesh), фіолетова область басейну, маркери RPR_Node")
        self.para(
            "Під час тестування виявлено й виправлено два дефекти, спричинені одним джерелом: океанічний бокс "
            "OceanCollisionBoxComponent_1 (WorldStatic = Block, Pawn = Overlap) охоплює всю арену. По-перше, "
            "бічний ривок не рухав ворога (evade: blocked), оскільки розгортка капсули за каналом WorldStatic "
            "починалася всередині блокуючого об’єму; у TrySkitter канал змінено на ECC_Pawn і вимкнено "
            "bFindInitialOverlaps. По-друге, трасування опорної поверхні ніг (TraceGround) давало початкове "
            "проникнення, тому стопи «висіли» на 152–172 см; трасування переведено на ECC_Pawn із відхиленням "
            "bStartPenetrating та використанням Hit.ImpactPoint, після чого зазор становить 0,13 см. Дубльований "
            "RecastNavMesh-Default із рівня видалено.")
        self.para(
            "Автовідродження реалізовано в AAOS_AIEnemyCharacter: у Die() запускається таймер RespawnDelay = 6,0 с, "
            "після якого Respawn() створює новий екземпляр класу ворога (SpawnActorDeferred) у збереженій "
            "трансформації появи, копіює PatrolNodes, HomeRadius і параметри відродження та завершує створення, "
            "а BeginPlay відновлює 168 HP, 3 кавітаційні пастки, новий пік і контролер із деревом:")
        self.code(CODE_RESPAWN)

    # ------------------------------------------------------------------ результати
    def results(self):
        self.para(
            "Тестування виконано в режимі PIE автоматизованими Python-скриптами (Tools/pie_test_lab5_reaper.py, "
            "Tools/pie_test_lab5_followup.py), які керують апаратом, дроном-атакером і ворогом та записують "
            "телеметрію у файли Saved/Lab5_Reaper_PIE.json і Saved/Lab5_Followup_PIE.json. Перший етап пройдено "
            "25 перевірок із 25, додатковий етап – 6 із 6. Ворог співіснує на сцені з двома Daemon. "
            "Результати 25 перевірок із посиланнями на рисунки-скріншоти наведено в таблиці 8.")
        self.expect_table(8)
        rows = []
        for i, (req, chk, meas, fig) in enumerate(PIE_CHECKS, 1):
            rows.append([str(i), req, chk, meas + (f" ({fig})" if fig else ""), "Пройдено"])
        self.table(
            "Результати 25 перевірок PIE (25 з 25)",
            ["№", "Завд.", "Перевірка", "Виміряні дані", "Результат"],
            rows,
            [0.9, 1.5, 5.0, 7.4, 2.7],
            {0: C, 1: C, 4: C},
        )
        self.expect_table(9)
        self.para("Додаткові перевірки після виправлень (6 із 6) наведено в таблиці 9.")
        self.table(
            "Додаткові перевірки: стопи, погоня крізь розсіл, відродження (6 з 6)",
            ["№", "Перевірка", "Виміряні дані", "Результат"],
            [[a, b, c, "Пройдено"] for a, b, c in PIE_FOLLOWUP],
            [1.1, 5.7, 7.6, 3.1],
            {0: C, 3: C},
        )
        self.para("Фрагменти журналу LogAOSAI та терміналу під час тестів:")
        self.code(CODE_LOG)
        self.para(
            "1) Патруль, огляд і біг при виявленні. Під час патрулювання швидкість дорівнює 170 см/с, під "
            "час огляду – 0 см/с, а після виявлення Shell-1 швидкість перемикається на 620 см/с у тому самому "
            "кадрі (рис. 5). Фактична швидкість досягає 90 % від значення за 0,392 с, що визначається "
            "прискоренням руху ходока.")
        self.placeholder(5, "Патруль і оглядання водної товщі Reaper (фаза SURVEY)",
                         "Скріншот PIE: Gameplay Debugger (апостроф), конус зору 150°, фаза SURVEY, потім SCUTTLE")
        self.para(
            "2) Нанесення шкоди. Пік наносить рівно 5,0 % енергії ядра за удар (рис. 6); між ударами проходить "
            "2,76 с, що відповідає сумі фаз удару і перезаряджання. Запис про удар «SIGKILL arc» із "
            "втратою 5 % ядра з’являється в терміналі кокпіту.")
        self.placeholder(6, "Удар піка Reaper по Shell-1 у PIE (фаза STRIKE)",
                         "Скріншот PIE: поза удару, шкала енергії −5 %, рядок SIGKILL arc - core -5%")
        self.para(
            "3) Ухилення. Ймовірність за формулою (3) збігається із записаними значеннями: P = 0,23 на 9 м і "
            "0,15 на 23 м (на 23 м Reaper не бачить ціль, тому множник обізнаності дорівнює 0,2). Примусове "
            "ухилення дає ривок 344 см із пасткою на 80 см від старої позиції, мінімальна відстань "
            "торпед до пастки становить 125 см, а ворог не втрачає HP (рис. 7).")
        self.placeholder(7, "Ухилення Reaper від атаки Shell-1 на арені",
                         "Скріншот PIE: пастка, траєкторії торпед, рядок evade ... DODGE у логах")
        self.para(
            "4) Перешкода. У зоні розсолу швидкість патруля падає зі 170 до 68 см/с, дальність бачення – з "
            "2600 до 1300 см, ймовірність ухилення на тій самій дальності – з 0,21 до 0,01, Shell-1 перешкода не "
            "зачіпає (рис. 8).")
        self.placeholder(8, "Reaper біля зони «Heap Brine Pool» на арені",
                         "Скріншот PIE: Reaper у басейні, запис heap brine - traction lost")
        self.para(
            "5) Співіснування з Daemon. На сцені одночасно перебувають 2 Daemon з лабораторної роботи № 3 та "
            "ворог RPR-6, які мають різні шкали здоров’я й не взаємодіють між собою (рис. 9).")
        self.placeholder(9, "Одночасне перебування Daemon та RPR-6 OOM Reaper на сцені",
                         "Скріншот PIE: обидва типи ворогів у кадрі, їхні шкали здоров’я")

    # ------------------------------------------------------------------ висновки
    def conclusions(self):
        self.para(
            "У лабораторній роботі створено NPC-ворога RPR-6 OOM Reaper на власному 36-кістковому скелеті з "
            "окремою зброєю SM_WPN_SigkillPike (4 опуклі оболонки UCX), прикріпленою до сокета, та власною "
            "тривимірною шкалою здоров’я, що співіснує на сцені з програмованими ворогами Daemon. Конвеєр ШІ "
            "побудований за схемою «AAIController – UAIPerceptionComponent (зір 150° на 26 м, слух 40 м, "
            "команда 9) – Blackboard – Behavior Tree – Recast NavMesh», причому уся логіка (контролер, сервіс, "
            "задачі, декоратори, ухилення, перешкода, процедурна хода й IK) реалізована в C++, а Blueprint "
            "містять лише значення за замовчуванням. Динамічне ухилення задано кусково-лінійним законом "
            "P_base(D) із крутизною 3,57 % на метр і контекстними множниками, а його коректність підтверджено "
            "Монте-Карло перевіркою та сумісністю з журналом (0,23 на 9 м, 0,15 на 23 м). Тригер «Heap Brine "
            "Pool» знижує швидкість на 60 %, удвічі зменшує дальність зору та множить ймовірність ухилення на 0,25, а різниця "
            "вартостей навігаційної області (3,0 для патруля проти 1,0 для погоні) змушує ворога обходити "
            "басейн у спокої та пересікати його в переслідуванні (2943 см проти 2400 см). Усі 25 із 25 перевірок "
            "PIE та 6 із 6 додаткових перевірок пройдено, а автовідродження через 6,0 с підтверджено двічі.")

    # ------------------------------------------------------------------ документ
    def finalize_properties(self):
        cp = self.doc.core_properties
        cp.keywords = "Unreal Engine 5, AOS_DK, Behavior Tree, Blackboard, AI Perception, NavMesh, IK"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=HERE.parent, help="корінь проєкту AOS_DK")
    ap.add_argument("--template", type=Path, default=None, help="шаблон звіту кафедри (.docx)")
    ap.add_argument("--out", type=Path, default=None, help="шлях до вихідного .docx")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    template = args.template or (root / base.TEMPLATE_REL)
    out = args.out or (root / TARGET_REL)

    rep = Lab5Report(root, template)
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
