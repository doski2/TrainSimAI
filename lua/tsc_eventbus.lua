-- lua/tsc_eventbus.lua — drop-in
-- ✏️ Cambia esta ruta a la ABSOLUTA de tu repo (usa / en vez de \)
local EVENTBUS_PATH = "C:/TrainSimAI/data/lua_eventbus.jsonl"

-- ----------------- util JSON -----------------
local function json_escape(s)
  s = string.gsub(s, "\\", "\\\\")
  s = string.gsub(s, '"', '\\"')
  s = string.gsub(s, "\n", "\\n")
  return s
end

local function emit_json(tbl)
  local parts = {}
  for k,v in pairs(tbl) do
    local vv = v
    if type(v) == "string" then vv = '"'..json_escape(v)..'"'
    elseif type(v) == "boolean" then vv = v and "true" or "false"
    else vv = tostring(v) end
    table.insert(parts, '"'..k..'":'..vv)
  end
  local f = io.open(EVENTBUS_PATH, "a")
  if not f then return end
  f:write("{".. table.concat(parts, ",") .."}\n")
  f:close()
end

-- ----------------- estado -----------------
local last_limit_kmh = nil
local stopped = false
local stop_t0 = nil
local current_station = nil
local last_marker_time = nil

-- parámetros de parada (ajustables)
local STOP_V_BEGIN_KMH = 0.5      -- si < a esto durante N s => stop_begin
local STOP_BEGIN_SECS   = 4.0
local STOP_V_EXIT_KMH   = 1.0      -- si > a esto => stop_end

-- anti-ruido de cambios de límite
local MIN_LIMIT_DELTA_KMH = 0.5    -- evita ping-pong por redondeos

local function to_kmh(x)
  if not x then return nil end
  if x < 20.0 then return x * 3.6 else return x end  -- si parece m/s, convértelo
end

-- emite un init de arranque
emit_json({ type="init", note="tsc_eventbus.lua loaded" })

-- ----------------- bucle de frame -----------------
function Update(time)
  -- hora in-game como horas decimales
  local hours = SysCall("PlayerEngine:GetTime") or 0.0
  -- velocidad actual
  local v_ms = SysCall("PlayerEngine:GetSpeed") or 0.0
  local v_kmh = v_ms * 3.6

  -- 1) evento de cambio de límite
  local nl = SysCall("PlayerEngine:GetNextSpeedLimit", 0, 0)   -- puede ser m/s o kmh
  if nl then
    local next_kmh = to_kmh(nl)
    if next_kmh then
      if not last_limit_kmh or math.abs(next_kmh - last_limit_kmh) >= MIN_LIMIT_DELTA_KMH then
        emit_json({
          type = "speed_limit_change",
          prev = last_limit_kmh or -1,
          next = next_kmh,
          time = hours
        })
        last_limit_kmh = next_kmh
      end
    end
  end

  -- 2) detección de parada (heurística)
  local now = os.time()
  if v_kmh < STOP_V_BEGIN_KMH then
    if not stop_t0 then stop_t0 = now end
    if (not stopped) and (now - stop_t0 >= STOP_BEGIN_SECS) then
      stopped = true
      emit_json({
        type = "stop_begin",
        station = current_station or "",
        time = hours
      })
    end
  else
    stop_t0 = nil
    if stopped and v_kmh > STOP_V_EXIT_KMH then
      stopped = false
      emit_json({
        type = "stop_end",
        station = current_station or "",
        time = hours,
        duration_s = 0  -- no conocemos la duración exacta en segundos reales aquí
      })
      -- mantén la estación hasta que se pase otro marcador
    end
  end
end

-- ----------------- marcadores -----------------
function MarkerPassed(name)
  local sname = tostring(name or "")
  -- marca paso por vía/marcador
  emit_json({ type="marker_pass", name=sname })
  -- considera que el último marcador nombra la estación (si es andén)
  current_station = sname
  last_marker_time = os.time()
end
