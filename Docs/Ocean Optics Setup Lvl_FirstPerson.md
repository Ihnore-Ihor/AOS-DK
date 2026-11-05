# AOS_DK — Оптика океану та підводне освітлення (Lvl_FirstPerson, UE 5.7.4)

Джерела констант: «UE5 Ocean Optics and Rendering», «Фізика хвиль океану та плавучості в UE5».
Застосовано скриптом `Tools/aos_ocean_setup.py` (ідемпотентний, `DRY_RUN = True` — лише показати зміни).
Рушій: 1 UU = 1 см → C_UE = C_phys × 0.01.

## 0. Що з'ясовано в графах рушія (Water plugin 5.7)

| Матеріал | Формула (з T3D-експорту графа) |
|---|---|
| Water_Material (SLW) | AbsorptionCoefficients = 1 / (Absorption.rgb × Absorption.a) [1/см]; ScatteringCoefficients = Scattering.rgb × Scattering.a / 1000 |
| M_UnderWater_PostProcess_Volume | T = exp(−min(SceneDepth, MaxDepth) × Absorption.rgb / Absorption.a); Fog = exp(−d × Fog); Out = lerp(FogAmbient·a + FogScatter·a·Phase, SceneColor·T, Fog) |
| Water_Underside | TIR-маска = saturate((CriticalAngleDot − dot(N,V)) / Width) |
| BeachFoam | контактна піна = 1 − saturate(DistanceToNearestSurface / Foam Distance) × depth-mask × текстура |

Причина «кольори зникають за 6 м»: дефолтний PP Absorption (25, 5, 2, a=7500) = 0.333 м⁻¹ у червоному → червоний на 6 м = 13.5 %, на 15 м = 0.7 %.
`MI_UnderWater_PostProcess_Volume_Custom` лежить у плагіні рушія (Program Files) і на рівні не використовується. На WaterBodyOcean призначений `MI_UnderwaterPostProcess_AOS` — саме його налаштовано.

## 1. Водна поверхня — MI_Water_Ocean_AOS (Jerlov II)

| Параметр | Було | Стало | Обґрунтування |
|---|---|---|---|
| Absorption (rgb, a) | 285.7, 2222.2, 5000, 1 (Jerlov I) | 256.41, 1250, 1538.46, 1 | 1/(0.0039, 0.0008, 0.00065) см⁻¹ |
| Scattering (rgb, a) | 0.05, 0.15, 0.25, 1 | 0.12, 0.28, 0.35, 1 | ×1/1000 → (0.00012, 0.00028, 0.00035) |
| Anisotropy (PhaseG) | 0.75 | 0.70 | Jerlov II |
| Water Specular / Fresnel Specular | 0.255 / 0.225 | 0.255 / 0.255 | F0 = ((1.333−1)/(1.333+1))² = 0.0204; 0.0204/0.08 |
| Water Roughness / Fresnel Roughness | 0.02 | 0.02 | 0.01–0.03 |
| Refraction | 1.333 | 1.333 | n морської води |
| Critical Angle Dot | 0.225 | 0.661 | cos(48.6°), віконце Снелла 97° |
| Critical Angle Width | 0.01 | 0.03 | м'якший край під хвилями |
| Foam Roughness | 0.4 | 0.8 | піна 0.7–0.85 |
| Foam Distance (DF Width) | 256 | 200 см | saturate(1 − d/Width) біля стін вежі |
| Caustics (static switch) | — | True | Color Scale Behind Water для вигляду з палуби |

Вимога для DF-піни: `r.GenerateMeshDistanceFields=True` (увімкнено). Для великих мешів вежі за потреби підняти Distance Field Resolution Scale.

## 2. Каустика — M_LF_OceanCaustics_AOS / MI_LF_OceanCaustics_AOS (Light Function на DirectionalLight)

```
depth   = max(WaterZ − WorldPos.z, 0)                      WaterZ = 40 см
mask    = saturate(depth / 50)                             відсікання надводної частини
sun     = exp(−Kd_PAR × depth),  Kd_PAR = 0.000725 см⁻¹    (Kd 525/460 нм Jerlov II → 1 % на ~63 м)
caustic = min(Tex(panA ± shift) RGB, Tex(panB))            Caustics_Tiling_01_HDR, період 300 см
fade    = exp(−depth / 1100) × (1 − smoothstep(1200, 1500, depth))
LF      = lerp(1, sun × lerp(1, lerp(0.25, 1, caustic), fade), mask)
```
127 інструкцій пікселя. Параметри MI: WaterZ, Kd_PAR_per_cm, CausticPeriod, ChromaticShift, CausticExtinctionDepth, CausticCutStart/End, CausticStrength, CausticFloor, CausticGain.
Light Function рушій зводить у greyscale (dot(Color, 1/3)), тож хроматичний зсув дає лише м'яке розмиття.

## 3. Підводний пост-процес — MI_UnderwaterPostProcess_AOS (геймплейний баланс)

| Параметр | Було | Стало |
|---|---|---|
| Absorption (rgb, a) | 25, 5, 2, 7500 | 0.030, 0.0092, 0.0075, **100** (при a=100 rgb читаються в м⁻¹) |
| Fog | 0.0002 | 0.0002 см⁻¹ |
| Fog Ambient Color | 0.1, 0.4, 0.75, 0.25 | 0.01, 0.08, 0.18, 0.35 |
| Fog Scatter Color | 0.5, 1, 0.75, 3 | 0.05, 0.35, 0.65, 0.6 |
| Scattering Aniso | 0.2 | 0.70 |

Червоний: −ln(0.55)/20 м = 0.030 м⁻¹. G, B = Kd Jerlov II × 0.115 (фізичне співвідношення G:B збережено).

| Дистанція | Червоний | Зелений | Синій | Прозорість туману |
|---|---|---|---|---|
| 6 м | 84 % | 95 % | 96 % | 89 % |
| 15 м | 64 % | 87 % | 89 % | 74 % |
| 20 м | 55 % | 83 % | 86 % | 67 % |
| 50 м | 22 % | 63 % | 69 % | 37 % |
| 100 м | 5 % | 40 % | 47 % | 13 % |

WaterBodyOcean → Underwater Post Process Settings: Priority 10, White Temp 5000 K, Auto Exposure Histogram, Min EV100 0, Max EV100 6.

## 4. Світло й туман (актори рівня)

| Актор | Параметр | Значення |
|---|---|---|
| DirectionalLight | Light Function Material | MI_LF_OceanCaustics_AOS |
| | Light Function Fade Distance | 160 000 |
| | Disabled Brightness | 1.0 |
| | Volumetric Scattering Intensity | 5.0 (PDF 4–7) |
| | Light Shaft Occlusion / Bloom, Cast Volumetric Shadow | On |
| SkyLight | Volumetric Scattering Intensity | 1.0 (було 5 — рівномірне світіння туману) |
| ExponentialHeightFog (Z = ватерлінія 40) | Fog Density | 0.05 |
| | Fog Height Falloff | **0.001** (було 0.2 → e³² на −1600 м) |
| | Inscattering | 0.01, 0.08, 0.18 |
| | Max Opacity | 1.0 |
| | Volumetric: Scattering Distribution / Extinction Scale / Distance | 0.75 / 2.0 / 6000 |
| | Volumetric Albedo (sRGB) | 82, 223, 255 = нормоване b/(a+b) Jerlov II |

LocalFogVolume не додавав: EHF із falloff 0.001 покриває стовп 1.6 км рівномірно. LFV варто ставити лише локально — навколо сигнальних вогнів вежі (g ≈ 0.8, albedo блакитний, emissive 0), щоб давати ореоли.

## 5. Стратифікація за глибиною — AAOSOceanDepthController (C++)

`Source/AOS_DK/Environment/Ocean/AOSOceanDepthController.h/.cpp`. Актор `AOS_OceanDepthController` уже стоїть на рівні. Працює тільки в PIE/грі; на рівні зберігаються значення епіпелагіалі.

| Зона | Глибина | Сонце (DL) | SkyLight / туман / PP-амбієнт |
|---|---|---|---|
| Surface | над водою | база | база, AirFog-пресет |
| Епіпелагіаль | 0–40 м | база; LF дає exp(−Kd·z) по пікселях; Vol. scatter 5·e^(−Kd z) | × e^(−0.0725·z) |
| Мезопелагіаль | 40–150 м | вимикається між 120–150 м | × e^(−0.0725·z), → 0 до 150 м |
| Батипелагіаль | 150–1600 м | 0 (невидиме, VSM звільнено) | 0 — лише фари, вогні вежі, Dracula-емісив |

Висота поверхні береться з `GetWaterSurfaceInfoAtLocation` (з урахуванням хвиль Герстнера). Перевірено в PIE: 14.7 м → Sky 0.344; 59.7 м → Sky 0.0132; 231 м → Sun 0, Sky 0, inscattering 0.

## 6. Перевірка

Тест-сфери Dracula Orange / Pink на 6–24 м, захоплення камерою: зі старим PP вони стають ціан/синіми, з новим лишаються помаранчевими/рожевими до ~24 м, а далі тонуть у синьо-чорному.
Скріншоти: `Saved/ClaudeExport/v_new_e06.png`, `v_old_e06.png`, `pie_15m.png`, `pie_70m.png`, `pie_5m_snell.png`.

## 7. Відомі обмеження / що робити далі

- Емісив Daemon (IdleGlow 22, ChargeGlowMax 160) під цією експозицією перепалюється в білий (ACES знебарвлює). Для читабельного кольору варто тримати емісив ≈ 2–8 і віддати «яскравість» bloom.
- Light Function у Volumetric Fog працює в просторі світла, без world-Z, тому глибинне згасання променів додатково робить контролер.
- Дивлячись угору на 5 м, туман у бік сонця пересвічується (Volumetric Scatter 5 + Fog Scatter). Якщо заважає — `SunVolumetricScatteringUnderwater` 3–4.
- WaterZone 10×10 км при RT 1024 дає ≈10 м на тексель. Для мапи 1 км можна поставити Zone Extent ≈ 120 000 (Far Distance Mesh добудує горизонт).

## 8. Морський сніг (Marine Snow) — AAOSMarineSnowField + M_MarineSnow_AOS

**Архітектура (без Niagara-симуляції, 1 draw call, 0 CPU на частку):**
- `Source/AOS_DK/Environment/Ocean/AOSMarineSnowField.h/.cpp` — при BeginPlay один раз будує ProceduralMesh із N квадів (20 000 на Epic, 70 % на Medium, 40 % на Low). Кожен квад зберігає світову «насінину» в межах одного періоду Box і випадкові дані у vertex color.
- `M_MarineSnow_AOS` (Masked, Unlit, Two-Sided; VS 279 / PS 200 інструкцій) — у WPO загортає насінину в куб навколо камери:
  `c = Cam + (frac((P0 + Drift·t − Cam) / Box) − 0.5) · Box`, Box = 40 м.
  Частки нерухомі у воді, тож працює справжній паралакс (відчуття швидкості), а поле нескінченне: мапа 1 × 1 × 1.6 км коштує рівно один Box.
- Актор щокадру лише переносить межі (bounds) за камерою, ховає поле над водою і передає в MID швидкість камери, дві фари з view target і сонце.
- Без тіней, Lumen, distance fields, ray tracing, колізій і reflection/sky captures.

**Оптика (PDF):**
- Фари обчислюються аналітично в пікселі: конус (inner/outer), обернений квадрат відстані, двочленна фазова функція Henyey-Greenstein (g1 = 0.92, g2 = −0.35, α = 0.98).
- Сонце: exp(−Kd_PAR · глибина частки) × та сама фазова функція, плюс слабкий синій амбієнт. У батипелагіалі сніг видно лише у світлі фар.
- Матеріал Masked пише глибину, тому підводний PP поглинає кожну пластівку за її власною дистанцією.
- Смуги руху: квад розтягується вздовж відносної швидкості, перпендикулярної до променя на частку, — радіальні «зіркові» смуги при русі вперед (StreakTime 0.04 с, максимум 40 см).
- Мінімальний радіус ≈ 1 px (dist × 0.0012) прибирає мерехтіння. Згасання поблизу (20–40 см) і на краю Box (14–20 м); невидимі квади колапсують у нуль і не коштують пікселів.

**Параметри MID** (стандартні значення в матеріалі): Gain 1500, SizeP (0.5, 2.4 см, 0.0012, 0.04 с), FadeP (40, 1400 см), Drift (3, 1.5, −0.6) см/с, Phase (0.92, −0.35, 0.98), Amb (0.0003, 0.001, 0.0015). На акторі: ParticleCount 20000, BoxSize 4000, HeadlightScale 0.001, SunScale 0.002.

**PIE (Shell, фари 2 × 5200 lm):**
- 80 м у стані спокою: сніг видно в конусі фар.
- 10 м/с: радіальні смуги.
- 300 м (батипелагіаль): лише пластівці в променях.

ProfileGPU: увесь PrePass займає 0.048 мс, увесь BasePass — 0.39 мс (кадр 10.5 мс), і разом із ними там рендериться сніг (40 тис. трикутників).
Скрипт: `Tools/aos_marine_snow_setup.py` (ідемпотентний).

## 9. Виправлення після PIE-тесту (сніг біля поверхні, темрява, каустика)

| Симптом | Причина (знайдено в коді/даних) | Виправлення |
|---|---|---|
| Каустика відсутня | Light Function брав плагінну HDR-текстуру зі стрімінгом. Текстури LF не бачить стрімер, тож у LF лишався 1×1 mip — пласке значення. До того ж пік каустики > 1 обрізався (вихід LF ≤ 1). | Власна `T_Caustics_AOS` (512², G8, NeverStream, пікселі = HDR / 2). Контраст патерну ~3:1 (Floor 0.2, Gain 3). Середнє LF 0.545 компенсується на сонці контролером: ×1/(1 − fade·(1 − 0.545)), тож опроміненість E_d(z) зберігається. Каустика перерозподіляє світло, а не поглинає його. |
| Темно одразу під поверхнею | 1) LF приглушував сонце в середньому до 0.49. 2) Колір туману PP був заданий в абсолютних одиницях (0.01, 0.08, 0.18) × 0.35 і на фоні денної експозиції виглядав чорним. 3) Мінімальна експозиція під водою EV100 = 0 обрізала денну експозицію. | LF див. вище. Fog Ambient a = 4 (× e^(−Kd·z), веде контролер). Мінімальна експозиція −4 EV біля поверхні → 0 EV в афотичній зоні (smoothstep 40–150 м), її веде контролер. Середня яскравість кадру на 3 м: 0.03 → 0.09–0.12 (над водою 0.35). |
| Сніг видно в повітрі на ватерлінії | Видимість поля визначалась за пласкою площиною води: `GetWaterSurfaceInfoAtLocation` хвиль не враховує. Самі частки не відсікались поверхнею. | VS рахує висоту хвилі в точці частки: 16 хвиль Герстнера з `DA_OceanWaves_AOS`, той самий годинник, що в water mesh. Частки на відстані < 20 см від поверхні колапсують. Контролер і сніг питають `TryQueryWaterInfoClosestToWorldLocation(ComputeLocation \| IncludeWaves)`. |
| Сніг стоїть, а Shell гойдається | Частки були жорстко закріплені у світі. | Частки — пасивні трасери: орбітальний зсув Герстнера × e^(−k·z) («Фізика хвиль…», u = ωA·e^{kz}). Швидкість для смуг рахується відносно водної частинки: v_cam − v_orbital(cam) − drift. На 9 м відносна швидкість упала з ~(85, 70, 88) до ~(60, 30, 20) см/с. |
| Сніг надто щільний біля поверхні | Амбієнт снігу (0.0003…0.0015 × Gain 1500) підсвічував кожну пластівку, і сонячна фаза була сильною. | Amb ÷ 15, SunScale 0.002 → 0.0005. Щільність 25 % під поверхнею, 100 % з 25 м (у перемішаному хвилями шарі агрегати руйнуються). |
| Смуги задовгі | StreakTime 0.04 с | 0.02 с |

Перевірка в PIE (Shell, 16 хвиль, Hs великий): ватерлінія — у повітрі частинок немає; 3 м — синя товща; 6 м — каустична сітка на освітленій плиті; 15 м; 60 м (мезопелагіаль); 300 м — лише фари; рух 7 м/с — короткі смуги. Сонце: 9.7 біля поверхні, 6.15 на 14 м, 0 на 300 м.
