# AOS_DK — Лабораторна №3: енергія Shell, Kernel Panic, кокпіт-HUD, демони, спавнер, 3D-шкала

Статус на 2026-11-04: C++ зібрано (UE 5.7.4, без попереджень), усі асети створено й збережено, рівень `Lvl_FirstPerson` доповнено. PIE-перевірка пройдена: посадка → HUD, зарядка в доці, шкода + глітч, атаки демонів (ривок і EMP), влучання торпед → вибух → респавн, Kernel Panic → повернення в док пішим персонажем із базовим зарядом 40 %.

---

## 1. Що і де

| Шар | Файли (Source/AOS_DK/…) | Призначення |
|---|---|---|
| Палітра | `Core/UI/AOSDraculaPalette.h` | 11 кольорів Dracula (sRGB → linear), єдине джерело кольорів UI |
| Векторний HUD-фреймворк | `Core/UI/HUD/AOSHudPainter.*`, `AOSHudElement.*`, `AOSHudTypes.h` | UWidget + Slate-лист `SAOSHudSurface`: уся геометрія малюється в C++ (лінії, меші, текст), без текстур |
| Енергія | `Submarine/Energy/ShellEnergyComponent.*` | Енергія = здоров'я + ресурс; споживачі (%/с), джерела зарядки, шкода, `OnSubmarineEnergyDepleted` |
| Shell | `Submarine/ShellPawn.*` (доповнено) | Форсаж, розхід, світло (кабіна + 2 фари), блокування керування, мерехтіння, пост-процес глітч, Niagara влучання, послідовність Kernel Panic |
| Док | `Systems/Dock/ShellDock.*` (доповнено), `Systems/Dock/ShellChargingZone.*` | `RecoverShell()`: пілот → на док пішки, Shell → на стоянку; зона швидкісної зарядки |
| HUD | `Submarine/HUD/PlayerSubmarineHUDWidget.*` + 8 елементів `Hud*.*` | Хаб даних + батарея, навігація, приціл, соти, лог, рамка кокпіта, глітч, панель Kernel Panic |
| Ворог | `Enemies/Daemon/AOS_EnemyDaemon.*`, `DaemonGeometry.*` | Процедурна модель, детермінований FSM, маршрут сплайном, атаки, смерть |
| Спавнер | `Enemies/Spawning/AOS_EnemySpawner.*` | Сектор, ліміт активних, інтервал, сплайн-маршрут (3 режими) |
| 3D-шкала | `Enemies/UI/EnemyHealthBarWidget.*` | UUserWidget, NativePaint, градієнт Green→Yellow→Orange→Red |
| Редакторний хелпер | `Core/Tools/AOSDKUIAuthoringLibrary.*` | Будує дерево WBP_SubmarineHUD (Canvas + елементи) |

Нове C++: ≈ 6 000 рядків + ≈ 790 рядків у ShellPawn/ShellDock. Blueprint-и не містять жодного вузла логіки — лише значення властивостей, розкладка UMG, меші/матеріали/Niagara. Частка C++ у логіці ≈ 100 % (вимога ≥ 60 % виконана з запасом).

**Заборонене ШІ не використано:** немає BehaviorTree, Blackboard, AIController, NavMesh, EQS, AIPerception. `AAOS_EnemyDaemon` — це `AActor` (не Pawn), тож AIController навіть не може бути створений; виявлення цілі — звичайна перевірка відстані + line trace.

Контент (Content/AOS_DK_Game/…):

- `Submarine/UI/WBP_SubmarineHUD`, `Submarine/FX/NS_ShellHitDischarge`
- `Enemies/Daemon/BP_EnemyDaemon`, `Materials/M_EnemyDaemon_Hull`, `MI_EnemyDaemon_Hull`, `M_EnemyDaemon_Glow`, `FX/NS_DaemonExplosion`, `NS_DaemonCharge`, `NS_DaemonPulse`
- `Enemies/Spawning/BP_EnemySpawner`, `Enemies/UI/WBP_EnemyHealthBar`
- `Systems/Dock/Blueprints/BP_ShellChargingZone`
- `Core/FX/Materials/M_FX_Spark` (адитивні іскри для всіх нових Niagara)
- `Core/Input/Actions/IA_Sub_Boost` (Left Ctrl, додано в `IMC_Submarine`)
- Змінено: `BP_Shell` (HUDWidgetClass, HullHitFX, HullHitSecondaryFX, BoostAction), `AOS_DK.uproject` (плагін ProceduralMeshComponent), `AOS_DK.Build.cs` (ProceduralMeshComponent, editor-only UMGEditor)
- На рівні: `ChargingZone_Dock`, `EnemySpawner_WestWater` (Lunge/Pulse по черзі), `EnemySpawner_EastWater` (Pulse/Lunge)

Скрипти авторингу: `Saved/Lab3/lab3_assets.py` (матеріали, Niagara, WBP, BP), `Saved/Lab3/build_daemon.ps1` (збирання без відкритого редактора).

---

## 2. Енергія, зарядка, смерть

**Одиниці:** усе в % від MaxEnergy (100). 8.5 %/с = повна зарядка за ≈ 11.8 с.

| Споживач (ShellPawn → Energy) | Значення | Коли |
|---|---|---|
| Propulsion | 0.2 %/с × тяга × відхилення стіка | W/S/A/D |
| Boost (Left Ctrl) | +0.9 %/с × тяга, тяга × 1.8 | форсаж |
| Ballast | 0.08 %/с × |баласт| | Space/Shift |
| Drones | 0.05 %/с × DeployBlend + 0.5 %/с × SpinAlpha | Deployed / розкрутка-стрільба Attacker |

Без навантаження баланс = 0 → нейтральний «— 0.0%/s» приглушеним Foreground. Незайнятий Shell нічого не витрачає.

**Зарядка:** `AShellChargingZone` (бокс 560×460×600) реєструє себе як джерело зарядки при overlap (і сканує початкові overlap-и — субмарина стартує на стоянці). Рампа 0.6 с, тож показник плавно доходить до «▲ +8.5%/s» зеленим. Лог: `dock: charge cycle active +8.5%/s`, `dock: core charged 100%`, `dock: charge cycle closed`. Маяк-світло зони пульсує, поки йде заряд.

**Kernel Panic (Energy ≤ 0):**

1. `UShellEnergyComponent::OnSubmarineEnergyDepleted` → `AShellPawn::HandleEnergyDepleted`.
2. Двигуни, баласт, гіро, форсаж і взаємодія заблоковані, дрони відкликаються, LMB відпускається; корпус повільно тоне (45 см/с²).
3. Фари й кабіна аварійно мерехтять (детермінований хеш-патерн), за 1.8 с гаснуть; далі лише червоний строб кабіни.
4. HUD: червоний глітч, червона рамка, панель `[FATAL] KERNEL PANIC: CORE DEPLETED / System halted. Emergency surface recovery initiated...` з друком тексту й шкалою прогресу; камера: хроматична аберація + зерно.
5. Через 2.5 с — Fade Out 0.9 с → `AShellDock::RecoverShell`: пілот від'єднується, ставиться в `DisembarkPoint`, контролер посідає `AAdminCharacter` (Walking); Shell телепортується на стоянку (поза старту, збережена в BeginPlay доку, або `ParkingPoint`), обнуляються швидкості, енергія = 40 %, світло вимкнене (порожній човен). Fade In 1.1 с.

Тюнінг: `BP_Shell → AOS_DK|Energy|Recovery` (PanicHoldTime, RecoveryFadeOut/In, RecoveryEnergyFraction, HaltedSinkAcceleration, EmergencyLightDecayTime), `BP_Shell → Energy` (MaxEnergy, ChargeRampTime, DrainWhileCharging, bInvulnerable для налагодження).

---

## 3. HUD (Завдання 4) — архітектура

`UPlayerSubmarineHUDWidget` (UUserWidget) — «хаб»: щокадру читає телеметрію Shell (енергія, баланс, глибина, курс, тангаж, FOV), раз на 1/30 с робить aim line trace (`DroneBay->ComputeAim`), опитує дрони та підписаний на події енергії. Сам нічого не малює — передає дані елементам.

Елементи — це `UWidget` з власним Slate-листом (`UAOSHudElement`): вони є в палітрі UMG у категорії **AOS_DK HUD**, малюються C++-кодом (`FAOSHudPainter`) і масштабуються рівномірно від свого DesignSize, тож лінії лишаються тонкими й чіткими на будь-якій роздільній здатності/DPI. Кожен примітив має власний шар Slate (порядок малювання = порядок у коді).

Створюється один раз при першій посадці (пул), потім лише `SetVisibility`; HitTestInvisible — мишу не перехоплює; ZOrder −10 (інші віджети поверх).

### Кольори (Dracula)

| Елемент | Колір | Чому |
|---|---|---|
| Заливка батареї | Yellow `#F1FA8C` → Orange `#FFB86C` (< 50 %) → Red `#FF5555` (< 25 %), пульс < 12 % | найвищий яскравісний контраст до синьо-зеленої товщі |
| Відновлення енергії | Green `#50FA7B` (стрілка ▲, відтінок заливки, «хвилі» заряду) | загальноприйнятий «плюс» |
| Навантаження | Orange `#FFB86C` (▼) | попередження без тривоги |
| Нейтральний баланс | Foreground `#F8F8F2` @ 55 % | приглушений світлий |
| Компас, сторони світу, джерела лог-рядків | Cyan `#8BE9FD` | навігаційний акцент |
| Тангаж | Purple `#BD93F9` | |
| Сота Attacker | Purple `#BD93F9`; low ammo — пульс Orange; resupply — Red | власний акцент модуля |
| LED стану дрона | Yellow — Ready, Green — Running, Orange — Waiting (док) | метафора станів процесу з концепції |
| Захоплення цілі | Pink `#FF79C6` | не плутається з червоним «шкода» |
| Лог | плашки Background `#282A36` @ 80 %, ліва смуга кольору серйозності | |
| Рамка кокпіта | Background, затемнений до майже чорного; край — тонкі Cyan/Pink лінії (хроматичний «край скла») | |
| Kernel Panic | Red на Background | |

### Адаптивність

- Якорі Canvas (кути/центр) + DPI-масштабування UMG → однакова розкладка в 16:9, 21:9, 4:3, від 720p до 4K.
- Рамка кокпіта й глітч розтягуються на весь екран, радіус заокруглення = 17 % висоти, ширина = за аспектом.
- Компас: дуга = FOV камери × 1.25 (`CompassArcPerFOV`); або `bCompassMatchesCameraFOV = true` — дуга рівно дорівнює кутам, які стрічка займає на екрані (мітки збігаються зі світом при будь-якому FOV).

---

## 4. Інструкція: збирання WBP_SubmarineHUD в UMG

Готовий асет уже лежить у `Submarine/UI/WBP_SubmarineHUD` (його дерево побудовано `UAOSDKUIAuthoringLibrary::BuildSubmarineHudLayout` за тими ж параметрами). Щоб зібрати вручну (або перевірити):

1. Content Browser → `Content/AOS_DK_Game/Submarine/UI` → ПКМ → *User Interface → Widget Blueprint* → у вікні вибору батьківського класу вкажіть **PlayerSubmarineHUDWidget** → назва `WBP_SubmarineHUD`.
2. Designer → Palette → перетягніть **Canvas Panel** як корінь (назва `CockpitCanvas`).
3. Palette → категорія **AOS_DK HUD** → додайте елементи. **Назви мають точно збігатися** (BindWidgetOptional):

| Назва | Клас | Anchors | Alignment | Position (X, Y) | Size (X, Y) | ZOrder |
|---|---|---|---|---|---|---|
| CockpitFrame | AOS HUD Cockpit Frame | Fill (0,0 – 1,1) | 0, 0 | offsets 0 | — | 0 |
| BatteryGauge | AOS HUD Battery Gauge | Top-Left (0,0) | 0, 0 | 64, 52 | 260, 170 | 10 |
| NavigationTape | AOS HUD Navigation Tape | Top-Center (0.5,0) | 0.5, 0 | 0, 30 | 480, 104 | 10 |
| DroneHoneycomb | AOS HUD Drone Honeycomb | Top-Right (1,0) | 1, 0 | −64, 48 | 270, 180 | 10 |
| Crosshair | AOS HUD Crosshair | Center (0.5,0.5) | 0.5, 0.5 | 0, 0 | 200, 90 | 10 |
| TerminalLog | AOS HUD Terminal Log | Bottom-Left (0,1) | 0, 1 | 60, −56 | 560, 210 | 10 |
| GlitchOverlay | AOS HUD Glitch Overlay | Fill | 0, 0 | offsets 0 | — | 40 |
| KernelPanicPanel | AOS HUD Kernel Panic Panel | Center | 0.5, 0.5 | 0, −30 | 1000, 240 | 50 |

4. Кожному елементу: Visibility = *Not Hit-Testable (Self & All Children)*.
5. Стиль (Details → AOS_DK|HUD|Style): шрифти за замовчуванням SpaceMono Regular/Bold з `Core/UI/Fonts`; кольори вже виставлені з палітри Dracula — змінюйте лише за потреби. Батарея: `SegmentCount` (10), `FillSmoothing`, пороги Low/Critical. Соти: `CellRadius`, `WarningPulseHz`. Лог: `MaxLines`, `HoldTime`, `FadeTime`, `CharsPerSecond`. Панель Kernel Panic: `bPreviewInDesigner` — показати в дизайнері.
6. Елементи в дизайнері показують «демо-значення» зі скетчу (35 %, −0.2 %/s, 102 M, 12/18 [03], два рядки логу) — розкладку видно без запуску гри.
7. Graph не потрібен (уся логіка — у C++). Compile → Save.
8. `BP_Shell` → Class Defaults → `AOS_DK|HUD → HUD Widget Class = WBP_SubmarineHUD`. Якщо поле порожнє, C++ створить ту саму розкладку автоматично.

Плавна батарея: заливка — один суцільний опуклий полігон (корпус, обрізаний по рівню `y ≥ level`), рівень інтерполюється експоненційно (`FillSmoothing`); 10 поділок — окремі тонкі лінії поверх (темні над заливкою, ледь помітні над порожнім склом), тож блоки ніколи не вмикаються/вимикаються стрибком. Відсоток — усередині корпусу; колір тексту плавно стає темним, коли заливка його накриває.

Соти: «12/18» — кільце, «[03]» — повні обойми в резерві (`Reserve / RingCapacity`), риски внизу — по одній на слот кільця. Кожна риска анімується окремо: при пострілі тоншає й гасне (`TickFadeSpeed`), під час розкрутки наступна торпеда звужується й світиться Pink («готується»). Резерв < 1 обойми → пульс Orange + `attacker: low ammo` у лозі.

---

## 5. Ворог AAOS_EnemyDaemon (Завдання 1, 2, 3, 5)

**Модель (процедурна, C++ `DaemonGeometry`):** 80-гранна іскосфера з окремих піднятих пластин (світіння ядра видно крізь шви), лінза-око (+X), два сегментовані гіроскопічні кільця (зовнішня грань — корпус, внутрішня — світна смуга), 4 щупальця-кабелі (трубки, які перебудовуються щокадру біжучою синусоїдою — «плавання»). Матеріали керуються Custom Primitive Data: 0–3 GlowColor, 4 GlowIntensity, 5 HitFlash (без MID).

**Детермінований FSM:**

| Стан | Рух | Вихід |
|---|---|---|
| Patrol | «морква» на сплайні на `PatrolLookAhead` попереду; швидкість = `VInterpTo(Velocity, Desired, Dt, WaterResponsiveness)`; sweep-рух із ковзанням уздовж стін; поворот `RInterpTo` + крен від бічного прискорення | Shell ≤ AggroRadius і видно → Engage |
| Engage | точка утримання на відстані від корпусу, повільне коло навколо Shell (напрям — від PID) | дистанція до корпусу ≤ AttackRange, ніс на цілі, cooldown → Telegraph |
| Telegraph (0.95 с) | Lunge: відкат назад; Pulse: зависання. Колір Orange → Pink → Red, яскравість ×7, кільця розкручуються, щупальця розкриваються, тремтіння й набухання, Niagara `NS_DaemonCharge`, шевроны на шкалі здоров'я | Lunge → Strike; Pulse → розряд `NS_DaemonPulse`, шкода в радіусі `PulseRadius` → Recover |
| Strike | ривок `LungeSpeed` з упередженням цілі; контакт із корпусом → шкода, відскок | Recover |
| Recover (1.5 с) | гальмування у воді | Engage / Return |
| Return | до найближчої точки маршруту | Patrol |

Шкода Shell: фіксовані `AttackDamage = 8` % через `UGameplayStatics::ApplyPointDamage` → `AShellPawn::TakeDamage` → енергія; точка удару — найближча точка колізії корпусу (`GetClosestPointOnCollision`) → там з'являється `NS_ShellHitDischarge` (прикріплений до корпусу) + бульбашки `NS_TorpedoHit`; HUD-глітч; лог `shell: damage 8%`.

Здоров'я: 100; торпеда Attacker = 14 (≈ 8 влучань). Влучання → білий спалах матеріалу; постріл по патрульному демону його провокує. HP ≤ 0 → колізія вимикається, `NS_DaemonExplosion` + бульбашки, модель ховається, спалах світла, лог `daemon[4100]: terminated (SIGKILL)`, `OnDaemonDestroyed` → спавнер, актор видаляється (LifeSpan 0.8 с).

Колізія: QueryOnly сфера, блокує WorldStatic (стіни), WorldDynamic (sweep торпед, інші демони), Visibility (приціл); Pawn/PhysicsBody — Overlap (ніколи не штовхає Shell).

---

## 6. Інструкція: маршрут патрулювання

**Через спавнер (рекомендовано):** виділіть `BP_EnemySpawner` на рівні → `AOS_DK|Spawner|Route → Route Mode`:

- **Generated Ring** — замкнене кільце `PatrolRadius` із вертикальною хвилею `RingVerticalWave`, `RingPointCount` точок (так налаштовано `EnemySpawner_WestWater`/`EastWater`).
- **Edited Spline** — компонент `PatrolSpline` видно у вʼюпорті: виділіть його, тягніть точки, Alt+тягнути — нова точка, ПКМ на точці → тип (Curve/Linear). Сплайн автоматично замкнений; якщо точок < 3, створюється квадрат 6×6 м як заготовка.
- **Patrol Points** — масив `PatrolPoints` із 3D-віджетами (ромбики у вʼюпорті; координати локальні до спавнера).

Інше: `EnemyClass` (BP_EnemyDaemon), `MaxActiveEnemies`, `SpawnInterval`, `InitialDelay`, `TotalSpawnBudget` (0 = безкінечно), `ActivationRadius`, `DefaultAttackMode`, `bAlternateAttackModes`. Демони рівномірно розподіляються по маршруту (детерміновано за порядковим номером).

**Окремий демон без спавнера:** перетягніть `BP_EnemyDaemon` на рівень → `AOS_DK|Daemon|Patrol`:

- `PatrolRouteActor` — будь-який актор зі SplineComponent (наприклад, звичайний порожній Actor + Spline), або
- `PatrolPoints` (локальні 3D-віджети, з'єднуються в замкнений сплайн під час запуску), або нічого — коло `DefaultPatrolRadius`.

Тюнінг руху: `PatrolSpeed`, `PatrolLookAhead`, `WaterResponsiveness` (менше = важча вода), `TurnSpeed`, `MaxBankAngle`, `SurfaceClearance`. Бою: `AggroRadius` (на BP 1800), `DisengageRadius` (3200), `LeashRadius` (4200), `AttackRange`, `TelegraphTime`, `LungeSpeed`, `PulseRadius`, `RecoverTime`, `AttackCooldown`, `AttackDamage`.

---

## 7. Інструкція: зона зарядки в доці

1. Place Actors → `BP_ShellChargingZone` (або `Systems/Dock/Blueprints`) → поставте так, щоб бокс `ChargeVolume` охоплював стоянку й кілька метрів під нею (на рівні: `ChargingZone_Dock` у (−1000, 700, 0), Yaw −90, Extent 560×460×600).
2. Details: `Charge Rate Percent Per Second` (8.5 ⇒ ≈ 12 с; 6.7–12.5 ⇒ 15–8 с), `bRequirePilot` (заряджати лише з пілотом), параметри маяка.
3. Таких зон може бути скільки завгодно (глибинні «розетки»): енергія бере найсильніше джерело.
4. Стоянка для респавну: `BP_ShellDock → bUseParkingPoint` = false — поза Shell на старті рівня; true — компонент `ParkingPoint` (переміщується у вʼюпорті).

---

## 8. Інструкція: 3D-віджет над ворогом

У `BP_EnemyDaemon` уже є компонент **HealthBar** (UWidgetComponent), C++ налаштовує його в BeginPlay:

1. `AOS_DK|Daemon|HealthBar → Health Bar Widget Class` = `WBP_EnemyHealthBar` (нащадок `UEnemyHealthBarWidget`; без нього використовується нативний клас — він теж повністю малюється).
2. `Health Bar Height` (125 см над центром), `Health Bar Visible Distance` (65 м), `bAlwaysShowHealthBar`, `bHideHealthBarWhenOccluded`.
3. Простір: за замовчуванням **Screen** (завжди обличчям до камери, постійний піксельний розмір, не тоне в підводному тумані). `bWorldSpaceHealthBar = true` → World + C++-білборд (щокадру повертається до камери).
4. Draw Size 180×46, Pivot (0.5, 1). Шкала видна лише пілоту Shell і не крізь стіни (trace 5 Гц).
5. Стиль у `WBP_EnemyHealthBar → Class Defaults`: Full/Mid/Low/Critical Color (Green/Yellow/Orange/Red), `CriticalThreshold`, шрифти. Шкала: тонка смуга з 10 поділками, «привид» отриманої шкоди, число «85%», ім'я процесу `daemon[PID]` (Pink під час бою), червоні шеврони під час телеграфу атаки.

---

## 9. Керування та налагодження

| Дія | Клавіша |
|---|---|
| Форсаж | Left Ctrl (новий IA_Sub_Boost) |
| Дрон: строй ↔ бойова позиція | R |
| Атака | ЛКМ (лише в Deployed) |

Налагодження: `BP_Shell → Energy → bInvulnerable`; у PIE — Python `unreal.GameplayStatics.apply_damage(shell, 100, …)` викликає Kernel Panic.

---

## 10. Відомі нюанси

- Підводний пост-процес рівня (`MI_UnderWater_PostProcess_Volume_Custom`, After Tonemapping) сильно поглинає колір: далі ≈ 6 м демони видно як ціанові силуети, кольори телеграфу (Orange/Pink/Red) читаються ближче. Над водою модель світиться фіолетовим (перевірено SceneCapture). Підказки атаки дублюються на 3D-шкалі (шеврони) — їх туман не ховає. Якщо потрібно, зменшіть поглинання в MI підводного пост-процесу.
- `MaterialEditingLibrary.delete_all_material_expressions` на матеріалі, що вже використовується на сцені, валить редактор (рушій, `!IsRooted`) — тому RimStrength винесено в `MI_EnemyDaemon_Hull`.
- Попередження `LoadErrors … VIW111A2WIQMZH3X1HEN9C` на старті — старе посилання в акторі доку з коміту «fix dock», до цієї роботи не стосується.

---

## 11. Виправлення після геймплей-тестів (раунд 2)

### 11.1 Торпеди мажуть по демонах

**Причини.**
- Колізія демона (сфера 91 см) була меншою за видиму модель: ореол ≈ 102 см, щупальця тягнуться ≈ 2.6 м позаду ядра. Процедурний меш колізії не має, тож у хвіст влучити було неможливо.
- Дистанційний підрив був дискретним і міряв відстань лише до точки прицілу, а не до тіла ворога. Близький проліт повз демона, коли приціл був на фоні, не детонував.
- Поки йшов `ArmingTime`, свіп не виконувався зовсім, тож упритул торпеда пролітала крізь ціль.
- Попадання «народився всередині» (`bStartPenetrating`) ігнорувалися для всіх акторів, крім цілі прицілу.

**Виправлення.**
- `AAOS_EnemyDaemon` отримав два query-only об'єми під модель: `HitVolume` (сфера `1.9·R + 8`, ≈ 107 см) і `TailHitVolume` (капсула вздовж щупалець). Обидва блокують лише WorldDynamic і Visibility, на рух не впливають. Розміри перераховуються в `BuildModel()`. Додано тег `AOS.FuseTarget`.
- `AMicroTorpedo::Tick`:
  - прямий свіп іде з першого кадру;
  - безперервний proximity-свіп (`SweepMultiByObjectType`, радіус `ProximityFuseRadius = 55`) відстежує колізію будь-якої fuse-цілі, вмикається після `ArmingTime`;
  - детонує раніше з двох попадань;
  - «народився всередині» ігнорується лише для не-цілей.

**Результат у PIE.** Статичний демон за 12 м, приціл на ньому, редактор у фоні ≈ 3 fps: **79 влучань із 80 пострілів**. Свідомий проліт на 1.4 м від центру (повз `HitVolume`): ≈ 80 % детонацій proximity-фітилем.

### 11.2 Дрон застрягає в геометрії

**Причина.** На контакті рух робив одне ковзання. У вгнутому куті або під плитою, перпендикулярною до напрямку руху, воно давало нуль. Крім того, ціль (слот строю) могла лежати за стіною.

**Виправлення** (`ASubDroneBase`, категорія `AOS_DK|Unstuck`):
- `ClipGoalToShell`: свіп Shell → слот обрізає ціль на першій перешкоді, тож дрон не тисне в скелю.
- Watchdog, який вмикає фазування:
  - *stuck*: свіп заблоковано і пройдено менше 35 % запланованого кроку довше за 0.5 с;
  - *lost*: дрон далі за `LeashRadius`, а шлях до слоту закритий довше за 1.5 с.
- Фазування: дрон рухається без колізії зі швидкістю ≤ `PhaseSpeed` і перевіряє вихід кожні 0.08 с (вільна позиція + чистий шлях або вже біля цілі). Після `MaxPhaseTime` = 2.5 с спрацьовує `RescueTeleport` у найближчу вільну точку біля Shell.
- Події для BP-візуалу: `BP_OnPhaseShift`, `BP_OnRescueTeleport`. Журнал: `LogSubDrone`.

**Результат у PIE.** Shell над бетонною плитою `Ceiling`, дрон під нею. Дрон визначив застрягання, пройшов плиту фазуванням і повернувся до Shell без наближення гравця. У журналі: `stuck -> phasing through geometry` → `free water again`.

### 11.3 Червоний Kernel Panic при повторній посадці

**Причина.** HUD-віджет пулиться і ховається посеред паніки. Приховані віджети не тікають, тому `PanicAlpha` та альфа панелі лишалися рівними 1. `HandleEnergyRestored` не приходив: HUD відв'язувався від Shell раніше, ніж відновлювалась енергія. Пост-процес камери (fringe/grain) теж не скидався.

**Виправлення.**
- `UAOSHudElement::ResetHud()` (віртуальний): кожен елемент миттєво стає в поточний стан без анімації.
- `UPlayerSubmarineHUDWidget::ResetTransientState()` викликається в `BindToShell` і `HandleEnergyRestored`: глітч, паніка, приціл, лог і слоти дронів з'являються вже в стані поточного кадру.
- `AShellPawn::ResetCameraPostProcess()` викликається при посадці й у `FinishRecovery`.

**Результат у PIE.** Перший кадр після повторної посадки чистий: немає червоного тону, панелі й глітчу.

### 11.4 Нюанс рівня

10 блоків `Floor*` мають профіль `BlockAllDynamic` (WorldDynamic). Рух дрона свіпить лише WorldStatic, тому крізь ці блоки дрон пропливає, а торпеди на них детонують. Якщо дрон має їх оминати, переведіть ці актори на `BlockAll` (рівень не змінювався).

---

## 12. HUD & Mechanics Polish v2

### 12.1 Енергетичний баланс (`UShellEnergyComponent`, `AShellPawn`)

| Система | Витрата | Де задається |
|---|---|---|
| Звичайний рух: тяга, баласт, повороти, гіро | **0** | — (споживачі `Propulsion`/`Ballast` видалено) |
| Форсаж (Left Ctrl) | до 1.5 %/с, пропорційно реальній прямій тязі | `AShellPawn::BoostDrainPerSec` |
| Дрон у Deployed (зв'язок + стабілізація) | 0.05 %/с | `DroneDeployedDrainPerSec` |
| Дрон: Spin-up / Attack (імпульсні системи) | до 0.8 %/с | `DroneCombatDrainPerSec` |
| Ручна перезарядка (ПКМ) | 1.5 % разово | `ASubDrone_Attacker::ReloadEnergyCost` |

`TryConsumeEnergy(Percent, Consumer)` атомарно списує разову вартість лише тоді, коли ядро після оплати лишається живим (покупка ніколи не запускає Kernel Panic). Якщо енергії замало, перезарядка блокується, а в лог іде `reload denied - core power low`.

### 12.2 Боєзапас і перезарядка (`ASubDrone_Attacker`, `USubDroneBayComponent`)

- `IA_Sub_DroneReload` (Digital Bool) → **ПКМ** в `IMC_Submarine`. Дію призначено в `BP_Shell → DroneBay → Drone Reload Action`.
- Схема роботи: `Bay::RequestReload` → `ASubDroneBase::CanStartReload()` → оплата з ядра → `StartReload()`. Чергова обойма магнітно подається з резерву в кільце (0.035 с на торпеду). Поки йде перезарядка, стрільба заблокована. Результат бачать HUD і BP через `OnReloadRequested`.
- Магічної регенерації немає: політику `TimedRegen` видалено, автоматичне дозаряджання кільця в полі вимкнено. Поповнити запас можна лише двома способами:
  - посадкою в гніздо субмарини (за порожніх кільця й резерву дрон сідає сам, `bAutoDockWhenEmpty`);
  - стоянкою субмарини в доці (`AShellChargingZone::bRearmDrones` → `Bay::SetServiceStationLinked`).
- Резерв: `ReserveMagazines = 6` обойм × 18 = 108 торпед (було 54). Разом із кільцем це 126 торпед, тобто 7 обойм.

### 12.3 HUD

**Батарея.** Дугова батарея концентрична ободу й кутовій віньєтці кабіни. Віджет розтягнуто на весь HUD, як і рамку, а геометрію кута хаб копіює з `UAOSHudCockpitFrame`.
- 10 концентричних смуг по 10 %. Активна смуга тоншає разом із залишком свого кроку.
- Відсоток стоїть у чистому прямокутному вирізі: `AOSHudMath::SubtractRect` точно обрізає смуги, і за цифрами нічого не малюється.

**Сота дрона** розрізняє стани і кольором, і рухом:

| Стан | Колір | Рух |
|---|---|---|
| Formation | Purple | тонкий спокійний контур |
| Deployed | Green | жирний сталий контур |
| Attack | Pink | мерехтіння, іскра на смузі кільця |
| LowAmmo (менше 1 обойми в резерві) | Orange | повільна пульсація |
| Depleted | Red | різке блимання, червоний тон |
| Service (стиковка / дозаправка) | Cyan | сканер біжить по периметру |

**Віконце значень і смуги обойм.**
- Горизонтальна плашка `18/18 [06]` вирізана з соти: внутрішній контур обрізається через `SegmentOutsideRect`.
- Під нею строго горизонтальні смуги обойм. Верхня смуга — кільце: тоншає з кожною торпедою, а коли кільце порожнє, гасне і пульсує помаранчевим з підказкою `RMB`. Нижче — по одній смузі на кожну обойму резерву: частково витрачена тонша, порожня ємність показана тонкими лініями.

**Термінальний лог.**
- Гіростабілізатор більше не пише через `AddOnScreenDebugMessage`. Його рядки йдуть у термінал кабіни через `AShellPawn::PushTerminalLog` → `UPlayerSubmarineHUDWidget::PushLog`: `gyro: stabilizer engaged - aligning, tilt 25.0 deg`, `gyro: horizon locked - stabilizer idle`, `gyro: no water contact - stabilizer off`.
- Плашка рядка тепер чорна напівпрозора.

### 12.4 Змінені ассети (резервні копії: `Saved/Lab3/backup_v2_assets`)
- `IA_Sub_DroneReload` (новий)
- `IMC_Submarine`: додано ПКМ
- `BP_Shell`: `DroneReloadAction`
- `WBP_SubmarineHUD`: слот `BatteryGauge` → якорі 0,0,1,1

### 12.5 Перевірка в PIE
- **Рух.** На ходу витрата 0.00 %/с. Deployed — 0.05 %/с, стрільба — 0.8 %/с.
- **Перезарядка.** Кільце 0/18 → ПКМ → 18/18, резерв 108 → 90, ядро −1.5 %.
- **Без регенерації.** Порожнє кільце не відновлюється само.
- **Без енергії.** При 1.2 % ядра перезарядка блокується, енергію не списано.
- **Виснаження.** Після 7 обойм — Depleted, далі посадка в гніздо (Service) і поповнення.
- **Док.** Біля доку кільце й резерв поповнюються автоматично.
- **Гіро.** Обидва рядки стабілізатора з'являються в лозі кабіни.
- **Збірка.** Без попереджень.

---

## 13. Геометрія v3: горизонтальна батарея, 32 × 8 боєкомплект, сота без вирізу

### 13.1 Батарея (`UAOSHudBatteryGauge`, `AOSHudMath`)
- **Контур.** Верхня й нижня межі суворо горизонтальні (`Top` / `Bottom`, Y = const). Ліва грань — зовнішня дуга радіуса `R_rim − RimClearance`, права — внутрішня дуга радіуса `R_outer − BandWidth`. Обидві дуги концентричні з ободом кабіни, тобто блок — це горизонтальний зріз кутового кільця.
- **Нова функція.** `AOSHudMath::CircleLeftX(Centre, R, Y)` повертає X лівої половини кола на висоті Y. Вона безпечна поза межами кола, тож NaN не виникає.
- **Смуги.** 10 горизонтальних смуг знизу вгору, кожна обмежена зліва й справа дугами. Смугу нарізано на тонкі горизонтальні трапеції, бо через увігнуту праву дугу вона не опукла. Кожна трапеція точно обрізається вирізом `SubtractRect`. Активна смуга тоншає донизу.
- **Віконце `95%`.** Центрується у вільному проміжку між дугами на всіх рядках вирізу, бо блок нахилений разом із кутом.
- **Параметри.** `RimClearance 12`, `BandWidth 96`, `TopRatio 0.8`, `BottomOffset 24`, `StripeGap 2.2`, `PercentFontSize 20`.

### 13.2 Боєкомплект (`ASubDrone_Attacker`, `UTorpedoReloadPolicy_DockResupply`)

| Параметр | Було | Стало |
|---|---|---|
| `RingSlotCount` (обойма) | 18 | **32** |
| `ReserveMagazines` | 6 | **7** (разом 8 обойм, **256** торпед) |
| `ReloadRoundInterval` | 0.035 с | 0.022 с (ПКМ ≈ 0.7 с) |
| `DockedRingRefillInterval` | 0.04 с | 0.025 с |
| `SecondsPerTorpedo` (гніздо) | 0.03 с | 0.015 с (224 торпеди ≈ 3.4 с) |
| `DockResupplyTimeout` | 6 с | 8 с |

`USubDroneBayComponent` своїх констант боєкомплекту не має: шлюз `RequestMunitionResupply` пропускає будь-яку кількість, яку попросить дрон.

### 13.3 Сота (`UAOSHudDroneHoneycomb`)
- **Смуги.** Виріз-плашку прибрано. Рівно 8 горизонтальних смуг (1 кільце + 7 резерву) рівномірно розподілено на всю висоту шестикутника, від верхнього до нижнього краю. Ширина кожної смуги підганяється під шестикутник.
- **Кольори смуг.** Смуги світлі, білі з відтінком статусу (`MagazineTint`). Верхня смуга — це кільце: вона тоншає з кожною з 32 торпед, а від нагріву генератора відтінюється помаранчевим.
- **Підписи.** `ATK`, `32/32`, `[07]` друкуються поверх смуг через `FAOSHudPainter::TextOutlined`: темне чорнило з чіткою темною обводкою Slate. Якщо смуги за рядком витрачені, чорнило стає світлим, а обводка лишається. Попередження (Orange / Red) зберігають свій колір.

### 13.4 Перевірка в PIE
- **Лічильники.** Повний боєкомплект показує `32/32 [07]` і 8 смуг. Після 14 пострілів — `18/32`, верхня смуга тонша.
- **Довантаження ПКМ.** Ядро −1.5 %. Кільце стало 32/32, резерв зменшився з 224 до 210: показується `[07]`, нижня смуга заповнена на 18/32.
- **Збірка.** Без попереджень.

---

## 14. HUD Visual Fixes v4

### 14.1 Батарея: верхня межа під обідом
- **Верхня межа.** `Top = EdgeInset + RimClearance + TopGap`, тобто приблизно 23 одиниці від краю екрана при `RimClearance 10` і `TopGap 6`. Верхня горизонтальна лінія лежить безпосередньо під верхнім обідом кабіни.
- **Права грань.** Менша концентрична дуга фізично не дістає до верхнього обіду: внутрішнє коло закінчується на `C.y − Rᵢ`. Тому права грань тепер — та сама дуга обода, зсунута праворуч на `BlockWidth` (104). Обидві грані мають радіус заокруглення кабіни, і всі горизонтальні смуги однакової довжини.
- **Віконце `NN%`.** Автоматично стає туди, де вільний проміжок між гранями найширший (грані круті внизу й пологі під обідом). За рівних умов вибирається висота, найближча до `ApertureHeightRatio` (0.62).

### 14.2 Сота: обрізка смуг і активна обойма
- **Обрізка смуг.** Нові функції `AOSHudMath::InsetHexagonRadius` (шестикутник зі стінками, відсунутими на `BarPadding`) і `AOSHudMath::HorizontalSlice` (горизонтальний зріз опуклого полігона). Кожна смуга — це зріз внутрішнього шестикутника. Тож це рівнобічна трапеція (або шматок шестикутника на середньому рядку), торці якої йдуть паралельно стінкам з однаковим відступом 3.5.
- **Активна обойма (верхня смуга):**
  - акцентний колір статусу, який нагрівається до помаранчевого;
  - неонове світіння у 2 шари, що пульсує в стані Attack;
  - тонка рамка навколо повного слота смуги. Рамка лишається, коли кільце порожнє, і тоді пульсує помаранчевим разом із підказкою `RMB`.

### 14.3 Текст
Підписи `ATK ●`, `32/32` і `[07]` зібрано в один компактний блок на темній «пігулці» `AOSHudMath::RoundedRect` (Dracula Background, альфа 0.82) з тонкою рамкою кольору статусу. Ширина блоку фіксована за найширшими можливими рядками, тому він не тремтить, коли змінюються лічильники.
- `ATK` — колір статусу;
- `32/32` — білий жирний (14 pt), а в станах «кільце порожнє» та Depleted — Orange або Red;
- `[07]` — світлий; підказки `RMB` / `LOAD` — у тому ж рядку.

Смуги видно над блоком, під ним і з боків.

### 14.4 Перевірка в PIE
- **Батарея.** При 98 % і 72 % верхня межа стоїть під обідом.
- **Сота.** Перевірено три стани: `32/32 [06]` з рамкою активної смуги, Attack `14/32` (смуга тонша, зі світінням) і `0/32` (помаранчева рамка та `RMB`).
- **Збірка.** Без попереджень.
