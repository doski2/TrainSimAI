                    pass
            if e.get("odom_m") is None:
                e["odom_m"] = odom_m

            # De-dup básico: mismo tipo+identificador+tiempo ⇒ no reescribir
            ident = (
                e.get("marker")
                or e.get("name")
                or e.get("station")
                or e.get("payload")
            )
            sig = (e.get("type"), ident, e.get("time"))
            if sig == last_sig:
                drained += 1
                continue
            last_sig = sig
            # Skip incomplete marker events lacking coordinates
            if e.get("type") == "marker_pass" and (
                e.get("lat") in (None, "") or e.get("lon") in (None, "")
            ):
                drained += 1
                continue
            nrm = normalize(e)
            with open(EVT_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(nrm, ensure_ascii=False) + "\n")
            drained += 1


if __name__ == "__main__":
    run(12.0)  # 12 Hz objetivo ≈ 9–10 Hz efectivos
