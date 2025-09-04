-- /lua/tsc_eventbus.lua (ejemplo mínimo)
local EVENTBUS_PATH = "C:/Users/Public/Documents/tsc_eventbus.jsonl" -- ajusta si lo prefieres dentro de RailWorks
local last_speed_ms = 0.0
local stopped = false
local stop_t0 = nil
local last_limit = nil


local function json_escape(s)
  s = string.gsub(s, "\\", "\\\\")
  s = string.gsub(s, '"', '\\"')
  return s
end


local function emit(evt)
  local f = io.open(EVENTBUS_PATH, "a")
  if not f then return end
  f:write(evt .. "\n")
  f:close()
end


local function emit_json(tbl)
  local parts = {}
  for k, v in pairs(tbl) do
    local vs
    if type(v) == "string" then
      vs = '"' .. json_escape(v) .. '"'
    else
      vs = tostring(v)
    end
    table.insert(parts, '"' .. k .. '":' .. vs)
  end
  emit('{' .. table.concat(parts, ",") .. '}')
end


function Update(time)
  -- Velocidad y hora in-game
  local v = SysCall("PlayerEngine:GetSpeed") or 0.0 -- m/s
  local hours = SysCall("PlayerEngine:GetTime") or 0.0
  -- Próximo límite (si disponible en este contexto)
  local next_limit = SysCall("PlayerEngine:GetNextSpeedLimit", 0, 0)

  -- Evento: cambio de próximo límite
  if next_limit and next_limit ~= last_limit then
    emit_json({ type = "speed_limit_change", prev = last_limit or -1, next = next_limit, time = hours })
    last_limit = next_limit
  end

  -- Heurística de parada: velocidad < 0.2 m/s sostenida ≥ 4 s
  local now = os.time()
  if v < 0.2 then
    if not stopped then
      stop_t0 = stop_t0 or now
      if now - stop_t0 >= 4 then
        stopped = true
        emit_json({ type = "stop_begin", time = hours })
      end
    end
  else
    stop_t0 = nil
    if stopped then
      stopped = false
      emit_json({ type = "stop_end", time = hours })
    end
  end

  last_speed_ms = v
end


-- Llamable opcional desde un marcador personalizado
function MarkerPassed(name)
  emit_json({ type = "marker_pass", name = tostring(name) })
end

