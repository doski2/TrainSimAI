-- lua/tsc_eventbus.lua  (escenario o locomotora)
-- Emite JSONL: C:\\TrainSimAI\\data\\lua_eventbus.jsonl
local EVENTBUS_PATH = "C:/TrainSimAI/data/lua_eventbus.jsonl"  -- AJUSTA si usas otra ruta

local DEBUG = true  -- mensajes en pantalla
local last_limit_kph = nil
local stopped = false
local still_s = 0.0     -- segundos parado acumulados
local heartbeat_s = 0.0 -- emite latido cada ~2 s

local function json_escape(s)
  s = string.gsub(s, "\\", "\\\\")
  s = string.gsub(s, '"', '\\"')
  return s
end

local function emit(tbl)
  local parts = {}
  for k, v in pairs(tbl) do
    local vs = (type(v) == "string") and ('"' .. json_escape(v) .. '"') or tostring(v)
    table.insert(parts, '"' .. k .. '":' .. vs)
  end
  local line = "{" .. table.concat(parts, ",") .. "}"
  local f = io.open(EVENTBUS_PATH, "a")
  if f then
    f:write(line .. "\n")
    f:close()
  elseif DEBUG then
    SysCall("ScenarioManager:ShowMessage", "EventBus", "No puedo abrir el archivo", 4, 0)
  end
end

local function get_speed_ms()
  -- m/s; PlayerEngine existe en escenario y loco
  local ok, v = pcall(SysCall, "PlayerEngine:GetSpeed")
  if ok and type(v) == "number" then return v end
  -- Fallback (locomotora): Call("GetSpeed")
  local ok2, v2 = pcall(Call, "GetSpeed")
  if ok2 and type(v2) == "number" then return v2 end
  return 0.0
end

local function query_next_limit_kph()
  -- 1) Escenario: PlayerEngine:GetNextSpeedLimit(dir, distAheadM)
  local ok, a, b, c = pcall(SysCall, "PlayerEngine:GetNextSpeedLimit", 0, 1000)
  if ok then
    -- algunas versiones devuelven solo velocidad, otras (type,speed,dist)
    if type(a) == "number" and b == nil then
      return a * 3.6
    elseif type(b) == "number" then
      return b * 3.6
    end
  end
  -- 2) Loco/señal: Call("GetNextSpeedLimit", dir, distAheadM)
  local ok2, typ, spd, dist = pcall(Call, "GetNextSpeedLimit", 0, 1000)
  if ok2 and type(spd) == "number" then
    return spd * 3.6
  end
  return nil
end

function Initialise()
  -- activar llamadas periódicas a Update(dt)
  Call("BeginUpdate")
  emit({ type = "lua_hello" })
  if DEBUG then
    SysCall("ScenarioManager:ShowMessage", "EventBus", "Inicializado", 3, 0)
  end
end

function Update(dt)
  -- tiempo de juego (hora del día en horas)
  local todH = SysCall("PlayerEngine:GetTime") or 0.0

  -- Heartbeat cada ~2 s para verificar escritura
  heartbeat_s = heartbeat_s + (dt or 0.0)
  if heartbeat_s >= 2.0 then
    heartbeat_s = 0.0
    emit({ type = "lua_heartbeat", t_game_h = todH })
  end

  -- Próximo límite
  local next_kph = query_next_limit_kph()
  if next_kph and next_kph ~= last_limit_kph then
    emit({ type = "speed_limit_change", prev = last_limit_kph or -1, next = next_kph, t_game_h = todH })
    last_limit_kph = next_kph
  end

  -- Paradas (heurística simple)
  local v_ms = get_speed_ms()
  if v_ms < 0.2 then
    still_s = still_s + (dt or 0.0)
    if (not stopped) and still_s >= 4.0 then
      stopped = true
      emit({ type = "stop_begin", t_game_h = todH })
    end
  else
    still_s = 0.0
    if stopped then
      stopped = false
      emit({ type = "stop_end", t_game_h = todH })
    end
  end
end

-- Marcadores del escenario (opcional)
function MarkerPassed(name)
  emit({ type = "marker_pass", name = tostring(name) })
end

