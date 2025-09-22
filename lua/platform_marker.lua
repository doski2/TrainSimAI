-- /lua/platform_marker.lua
-- Marcador de andén sencillo: emite un MarkerPassed("<nombre>")
-- Requiere que el escenario cargue también tsc_eventbus.lua como script de escenario.

-- Cambia el nombre aquí o crea variantes del script por estación
local STATION_NAME = "Estación X"

function Initialise()
  -- nada
end

-- Se llama cuando la cabeza/cola del tren pasa el marcador (track-linked)
-- Parámetros estándar: prev, next, frontDist, backDist, linkIndex
function OnConsistPass(prev, next, front, back, linkIndex)
  if MarkerPassed ~= nil then
    MarkerPassed(STATION_NAME)
  end
end
