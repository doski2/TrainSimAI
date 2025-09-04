# Perfil base: **DTG · DB BR146 (Dresden)**

> Fuente: *TSClassic Raildriver and Joystick Interface V3.3.0.9* → `FullEngineData/DTG/DRESDEN/DB BR146.2.txt` y `KeyMaps/Levers/DTG/DRESDEN/DB BR146.2.xml`.

## Identidad y rutas SERZ
- **Engine Name:** `DB BR146.2`
- **Engine Bin:** `assets\DTG\Dresden\RailVehicles\Electric\DB146\Engine\146 Engine.bin`
- **Engine Script:** `Assets\DTG\Dresden\RailVehicles\Electric\DB146\Engine\DB146_EngineScript.out`

## Sensores / indicadores clave (rangos)
- **Velocímetro:** `SpeedometerKPH` → **0..180** (→ `v_ms = v/3.6`)
- **Ammeter:** `-1000..1000`
- **BC (cilindro freno):** `TrainBrakeCylinderPressureBAR` → `0..10 bar`
- **BP (tubería freno):** `BrakePipePressureBAR` → `0..12 bar`

## Controles principales (rangos y notas)
- **Acelerador:** `Regulator` (alias: `VirtualThrottle`, `SimpleThrottle`) → `0..1`
- **Freno tren (servicio):** `VirtualBrake` → `0..1`  
  Notches: `0, 0.22, 0.35, 0.48, 0.61, 0.74, 0.87, 1` (desde KeyMap)
- **Freno loco (indep.):** `VirtualEngineBrakeControl` → `-1..1`  
  Notches: `-1.5, -0.0001, 0, 0.0001, 1.5` (Apply/Hold/Release)
- **Freno dinámico:** `VirtualDynamicBrake` (si presente) → `0..1`
- **Reverser:** `-1..1`
- **Sander:** `0..1`
- **Luces cabina:** `CabLight` → `0..1`
- **Faros:** `Headlights` → `0,1,2` (3 posiciones)
- **Puertas:** `DoorsOpenCloseLeft`, `DoorsOpenCloseRight` → `0..1`
- **Pantógrafo:** `VirtualPantographControl` → `0..1`

## AFB / SIFA / PZB / LZB
- **AFB (on/off):** `AFB` → `0..1` (KeyMap indica **37 notches**)
- **AFB velocidad:** `AFB_Speed` → `0..180`
- **SIFA:** `Sifa`, `SifaReset`, `SifaLight`, `SifaAlarm` → `0..1`
- **PZB (estados/mandos):**
  - Estados: `PZB_85`, `PZB_70`, `PZB_55`, `PZB_1000Hz`, `PZB_500Hz`, `PZB_B40`, `PZB_Warning`, `PZB_Emergency`, `PZB_Restriction`, `PZB_RestrictiveMode` (rangos varios, típ. 0..1)
  - Controles: `PZB_1000Hz_Control` (‑1..1250), `PZB_500Hz_Control` (‑1..250), `PZB_2000Hz_Control` (‑1..1)
- **LZB:** presentes indicadores como `LZB_V_SOLL`, `LZB_V_ZIEL`, `LZB_DISTANCE` si están expuestos (no todos los escenarios/variantes los muestran).

## Diferencias 146.0 vs 146.2 (Dresden)
- 146.2 añade `BrakeBar`, `ForceBar`, `SpeedometerNeedle` y pierde `LZB_SpeedWarning`; el resto de rangos clave coinciden (vmax 180, AFB 0..180).

---

## Archivo de perfil para el proyecto (`profiles/DTG.Dresden.DB_BR146.2.json`)
```json
{
  "meta": { "provider": "DTG", "product": "DRESDEN", "engine": "DB BR146.2" },
  "speed": { "sensor": { "name": "SpeedometerKPH", "min": 0.0, "max": 180.0 }, "unit": "kmh", "to_ms": "v/3.6" },
  "controls": {
    "throttle": { "name": "Regulator", "min": 0.0, "max": 1.0 },
    "train_brake": { "name": "VirtualBrake", "min": 0.0, "max": 1.0 },
    "loco_brake": { "name": "VirtualEngineBrakeControl", "min": -1.0, "max": 1.0 },
    "dynamic_brake": { "name": "VirtualDynamicBrake", "min": 0.0, "max": 1.0 },
    "reverser": { "name": "Reverser", "min": -1.0, "max": 1.0 },
    "sander": { "name": "Sander", "min": 0.0, "max": 1.0 },
    "headlights": { "name": "Headlights", "min": 0.0, "max": 2.0 },
    "cab_light": { "name": "CabLight", "min": 0.0, "max": 1.0 },
    "doors_left": { "name": "DoorsOpenCloseLeft", "min": 0.0, "max": 1.0 },
    "doors_right": { "name": "DoorsOpenCloseRight", "min": 0.0, "max": 1.0 },
    "pantograph": { "name": "VirtualPantographControl", "min": 0.0, "max": 1.0 },
    "afb_enable": { "name": "AFB", "min": 0.0, "max": 1.0 },
    "afb_speed": { "name": "AFB_Speed", "min": 0.0, "max": 180.0 },
    "sifa": { "name": "Sifa", "min": 0.0, "max": 1.0 },
    "sifa_reset": { "name": "SifaReset", "min": 0.0, "max": 1.0 },
    "sifa_light": { "name": "SifaLight", "min": 0.0, "max": 1.0 },
    "sifa_alarm": { "name": "SifaAlarm", "min": 0.0, "max": 1.0 }
  },
  "indicators": {
    "brake_pipe_bar": { "name": "BrakePipePressureBAR", "min": 0.0, "max": 12.0 },
    "train_bc_bar": { "name": "TrainBrakeCylinderPressureBAR", "min": 0.0, "max": 10.0 },
    "ammeter": { "name": "Ammeter", "min": -1000.0, "max": 1000.0 },
    "tractive_effort": { "name": "ForceBar", "min": 0.0, "max": 1.0 }
  },
  "pzb": {
    "states": {
      "PZB_85": { "name": "PZB_85", "min": 0.0, "max": 1.0 },
      "PZB_70": { "name": "PZB_70", "min": 0.0, "max": 1.0 },
      "PZB_55": { "name": "PZB_55", "min": 0.0, "max": 1.0 },
      "PZB_1000Hz": { "name": "PZB_1000Hz", "min": 0.0, "max": 1.0 },
      "PZB_500Hz": { "name": "PZB_500Hz", "min": 0.0, "max": 1.0 },
      "PZB_B40": { "name": "PZB_B40", "min": 0.0, "max": 1.0 },
      "PZB_Warning": { "name": "PZB_Warning", "min": 0.0, "max": 1.0 },
      "PZB_Emergency": { "name": "PZB_Emergency", "min": 0.0, "max": 1.0 },
      "PZB_Restriction": { "name": "PZB_Restriction", "min": 0.0, "max": 100.0 },
      "PZB_RestrictiveMode": { "name": "PZB_RestrictiveMode", "min": -1.0, "max": 15.0 }
    },
    "controls": {
      "ctrl_1000hz": { "name": "PZB_1000Hz_Control", "min": -1.0, "max": 1250.0 },
      "ctrl_500hz": { "name": "PZB_500Hz_Control", "min": -1.0, "max": 250.0 },
      "ctrl_2000hz": { "name": "PZB_2000Hz_Control", "min": -1.0, "max": 1.0 }
    }
  },
  "notches": {
    "train_brake": { "control": "VirtualBrake", "values": [0, 0.22, 0.35, 0.48, 0.61, 0.74, 0.87, 1], "names": ["Dummy1","Dummy2","Dummy3","Dummy4","Dummy5","Dummy6","Dummy7","Dummy8"] },
    "loco_brake":  { "control": "VirtualEngineBrakeControl", "values": [-1.5, -0.0001, 0, 0.0001, 1.5], "names": ["Release","Hold","Apply"] },
    "headlights":  { "control": "Headlights", "values": [0,1,2], "names": [] },
    "afb_enable":  { "control": "AFB", "values": [], "names": [] }
  }
}
```

## Diff para añadir el perfil
```diff
*** /dev/null	2025-09-04
--- a/profiles/DTG.Dresden.DB_BR146.2.json	2025-09-04
***************
*** 0 ****
--- 1,200 ----
+ { «contenido JSON anterior» }
```

> Si prefieres **BR146.0**, los rangos clave son idénticos (AFB 0..180, Vmax 180); cambia solo el fichero de **engine** y un par de indicadores (146.2 añade `ForceBar/BrakeBar`).

