Vendor management recommendations
===============================

Este repositorio contiene copias vendorizadas de dependencias en:

- `py-raildriver-master/`
- `vendor/`

Mantener copias de terceros dentro del árbol del repo facilita pruebas locales pero complica:

- Revisiones de código (diffs más grandes).
- Actualizaciones de seguridad y dependencias.
- Trazabilidad de licencias.

Recomendación:

1. Preferir una dependencia instalada desde PyPI (p.ej. `py-raildriver>=0.6`) y eliminar la copia vendorizada si es posible.
2. Si necesitas mantener el código localmente por razones técnicas, usar un submódulo Git (`git submodule add ...`) para mantener historial separado.
3. Incluir la licencia y una nota en `docs/licenses/` para cada paquete vendorizado.

Ejemplo rápido para usar PyPI:

1. Añadir a `requirements.txt`: `py-raildriver>=0.6` (ya presente en este repo).
2. Ejecutar `pip install -r requirements.txt` en el entorno virtual.
3. Probar y, si todo funciona, eliminar la carpeta `py-raildriver-master/` del árbol y crear un PR.

Si quieres, puedo:

- Proponer un PR que mueva `py-raildriver-master/LICENSE` a `docs/licenses/` y añada una nota en `docs/VENDORING.md` (esto es seguro y no borra nada).
- Convertir `py-raildriver-master` en submódulo si me das la URL upstream.
