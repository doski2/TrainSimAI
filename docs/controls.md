# Nombres y aliases de controles

Este documento explica la lista centralizada de controles y aliases exportada
en `profiles.controls`. El objetivo es mantener un único lugar donde buscar
los nombres canónicos y las variantes que aparecen en distintos perfiles
de locomotoras o en distintas versiones de `RailDriver`.

Uso rápido

- Importar: `from profiles.controls import canonicalize, CONTROLS`
- `canonicalize(name)` devuelve el nombre canónico (`"brake"`, `"throttle"`, etc.)
  o `None` si el nombre no se reconoce.

Extender la tabla

Para añadir nuevos aliases, edita `profiles/controls.py` y añade la entrada
en `CONTROLS`. Incluye tanto la forma canónica como las variantes conocidas.

Ejemplo

```python
from profiles.controls import canonicalize

>>> canonicalize('BrakeCmd')
'brake'
```
