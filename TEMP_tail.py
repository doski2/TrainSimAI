            self.poll_dt = float(poll_dt)
        # Seleccionar la DLL adecuada para evitar WinError 193 (arquitecturas distintas)
        dll_path = _locate_raildriver_dll()
        self.rd = RailDriver(dll_location=dll_path) if dll_path else RailDriver()
        # Necesario para intercambiar datos con TS
        try:
            self.rd.set_rail_driver_connected(True)
        except Exception:
            # Versiones antiguas ignoran el parámetro; continúamos.
            pass

        # Índices cacheados por nombre para lecturas directas cuando conviene
        self.ctrl_index_by_name: Dict[str, int] = {
            name: idx for idx, name in self.rd.get_controller_list()
        }

        # Listener para cambios y snapshots unificados
        self.listener = Listener(self.rd, interval=self.poll_dt)
        # Cache de la última geo conocida para rellenar huecos momentáneos
        self._last_geo: Dict[str, Any] = {"lat": None, "lon": None, "heading": None, "gradient": None}
        # Suscribir todos los controles disponibles (las especiales se evalúan siempre)
        try:
            self.listener.subscribe(list(self.ctrl_index_by_name.keys()))
        except Exception:
            # Si cambia de locomotora y hay controles ausentes, se puede re-suscribir más tarde
            pass

    # --- Lectura mediante iteración única del listener ---
    def _snapshot(self) -> Dict[str, Any]:
        """Fuerza una iteración del listener y devuelve una copia del estado actual."""
        # No arrancamos hilo; usamos una iteración síncrona
        self.listener._main_iteration()  # type: ignore[attr-defined]
        cd = getattr(self.listener, "current_data", None)
        return dict(cd) if cd else {}

    # --- Lecturas puntuales ---
    def read_specials(self) -> Dict[str, Any]:
        # py‑raildriver expone helpers; aquí usamos listener snapshot para unificar
        snap = self._snapshot()
        out: Dict[str, Any] = {}
        # LocoName → [Provider, Product, Engine]
        if "!LocoName" in snap:
            loco = snap["!LocoName"] or []
            if isinstance(loco, (list, tuple)) and len(loco) >= 3:
                out.update({
                    "provider": loco[0],
                    "product": loco[1],
                    "engine": loco[2],
                })
        # Coordenadas/tiempo/rumbo/pendiente…
        coords = snap.get("!Coordinates")
        if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
            out["lat"], out["lon"] = float(coords[0]), float(coords[1])
        else:
            # Fallback directo a RailDriver si el snapshot no trae coordenadas
            try:
                c2 = self.rd.get_current_coordinates()
                if isinstance(c2, (list, tuple)) and len(c2) >= 2:
                    out["lat"], out["lon"] = float(c2[0]), float(c2[1])
            except Exception:
                pass
        # Heading en la DLL a veces llega en radianes (~0..6.28). Añade grados también.
        if "!Heading" in snap:
            try:
                hdg = float(snap["!Heading"])
            except Exception:
                hdg = snap["!Heading"]
            out["heading"] = hdg
        elif "heading" not in out:
            try:
                h = float(self.rd.get_current_heading())
                out["heading"] = h
            except Exception:
                pass
        if "heading" in out and out["heading"] is not None:
            try:
                _hdg = float(out["heading"])
                if -7.0 <= _hdg <= 7.0:  # parece radianes
                    out["heading_deg"] = (_hdg * 180.0 / 3.141592653589793) % 360.0
                else:
                    out["heading_deg"] = _hdg % 360.0
            except Exception:
                pass
        if "!Gradient" in snap:
            out["gradient"] = snap["!Gradient"]
        elif "gradient" not in out:
            try:
                g = self.rd.get_current_gradient()
                out["gradient"] = g
            except Exception:
                pass
        if "!FuelLevel" in snap:
            out["fuel_level"] = snap["!FuelLevel"]
        elif "fuel_level" not in out:
            try:
                f = self.rd.get_current_fuel_level()
                out["fuel_level"] = f
            except Exception:
                pass
        if "!IsInTunnel" in snap:
            out["is_in_tunnel"] = bool(snap["!IsInTunnel"])
        elif "is_in_tunnel" not in out:
            try:
                it = self.rd.get_current_is_in_tunnel()
                out["is_in_tunnel"] = bool(it)
            except Exception:
                pass
        if "!Time" in snap:
            # !Time suele venir como datetime.time o [h,m,s]
            tval = snap["!Time"]
            if isinstance(tval, (list, tuple)) and len(tval) >= 3:
                out["time_ingame_h"], out["time_ingame_m"], out["time_ingame_s"] = tval[:3]
            else:
                out["time_ingame"] = str(tval)
        else:
            try:
                tobj = self.rd.get_current_time()
                out["time_ingame"] = str(tobj)
            except Exception:
                pass
        return out

    def read_controls(self, names: Iterable[str]) -> Dict[str, float]:
        snap = self._snapshot()
        res: Dict[str, float] = {}
        for n in names:
            if n in snap and snap[n] is not None:
                try:
                    res[n] = float(snap[n])
                    continue
                except Exception:
                    pass
            # fallback lectura directa (índice es más eficiente)
            idx = self.ctrl_index_by_name.get(n)
            if idx is not None:
                try:
                    res[n] = float(self.rd.get_current_controller_value(idx))
                except Exception:
                    # si falla, ignoramos ese control en esta pasada
                    pass
        return res

    def stream(self) -> Iterator[Dict[str, Any]]:
        """Genera dicts con specials + subset de controles comunes."""
        common_ctrls = self._common_controls()
        while True:
            row: Dict[str, Any] = self.read_specials()
            row.update(self.read_controls(common_ctrls))
            # Aliases and unified speedometer
            if "Throttle" not in row and "Regulator" in row:
                row["Throttle"] = row["Regulator"]
            if "SpeedometerKPH" in row:
                row["Speedometer"] = row["SpeedometerKPH"]
                row["speed_unit"] = "kmh"
            elif "SpeedometerMPH" in row:
                row["Speedometer"] = row["SpeedometerMPH"]
                row["speed_unit"] = "mph"
            # Derivar métricas útiles
            v = row.get("SpeedometerKPH") or row.get("SpeedometerMPH")
            if v is not None:
                if "SpeedometerMPH" in row and "SpeedometerKPH" not in row:
                    v_ms = float(v) * 0.44704
                else:
                    v_ms = float(v) / 3.6
                row["v_ms"], row["v_kmh"] = v_ms, v_ms * 3.6
            # Cacheo de última geo: si falta, usa la última válida
            for k in ("lat", "lon", "heading", "gradient"):
                if row.get(k) is None and self._last_geo.get(k) is not None:
                    row[k] = self._last_geo[k]
            for k in ("lat", "lon", "heading", "gradient"):
                if row.get(k) is not None:
                    self._last_geo[k] = row[k]
            # Alias prácticos para uniformar columnas del CSV
            if "Throttle" not in row and "Regulator" in row:
                row["Throttle"] = row["Regulator"]
            yield row
            time.sleep(self.poll_dt)

    def _common_controls(self) -> Iterable[str]:
        names = set(self.ctrl_index_by_name.keys())
        # Alias / variantes habituales y útiles
        preferred = {
            "SpeedometerKPH", "SpeedometerMPH",
            "Regulator", "Throttle",
            "TrainBrakeControl", "VirtualBrake", "TrainBrake",
            "LocoBrakeControl", "VirtualEngineBrakeControl", "EngineBrake",
            "DynamicBrake", "Reverser",
            # Seguridad y sistemas
            "Sifa", "SIFA", "SifaReset", "SifaLight", "SifaAlarm", "VigilEnable",
            "PZB_85", "PZB_70", "PZB_55", "PZB_1000Hz", "PZB_500Hz", "PZB_40", "PZB_B40", "PZB_Warning",
            "AFB", "AFB_Speed", "LZB_V_SOLL", "LZB_V_ZIEL", "LZB_DISTANCE",
            # Indicadores útiles
            "BrakePipePressureBAR", "TrainBrakeCylinderPressureBAR", "Ammeter", "ForceBar", "BrakeBar",
            # Auxiliares
            "Sander", "Headlights", "CabLight", "DoorsOpenCloseLeft", "DoorsOpenCloseRight", "VirtualPantographControl",
        }
        # Criterios por patrón para capturar familias comunes
        rx = re.compile(r"^(PZB_|Sifa|AFB|LZB_|BrakePipe|TrainBrake|VirtualBrake|VirtualEngineBrake|Headlights|CabLight|Doors)", re.I)
        chosen = {n for n in names if (n in preferred or rx.match(n))}
        return sorted(chosen)
