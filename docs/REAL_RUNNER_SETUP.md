# Configuración del runner self-hosted para tests `real`

Este documento describe los pasos recomendados para provisionar un runner self-hosted en Windows que pueda ejecutar los tests marcados `real` en este repositorio.

Resumen
--------
- Objetivo: disponer de un runner Windows con acceso a las bibliotecas nativas (RailDriver / Train Simulator DLLs) y con la etiqueta `real` para que GitHub Actions pueda ejecutar manualmente el workflow `.github/workflows/real.yml`.

Requisitos mínimos del host
---------------------------
- Windows 10/11 o Windows Server 2019/2022 (x64).
- Python 3.11 (preferido), pip y acceso de administrador para instalar el runner de GitHub Actions.
- Conexión de red estable y acceso al repositorio (token del runner configurado por GitHub).
- Espacio en disco suficiente para dependencias y artefactos de prueba.

Instalación del runner de GitHub Actions (resumen)
-------------------------------------------------
1. Crear una máquina Windows y entrar como usuario administrador.
2. En la página de `Settings -> Actions -> Runners` de tu repositorio/organización, generar un nuevo runner y copia la URL y el token.
3. En la máquina, descargar y extraer el runner, luego ejecutar `config.cmd` con el token. Ejemplo PowerShell (ejecutar como Admin):

```powershell
# extraer en C:\actions-runner
cd C:\actions-runner
.\config.cmd --url https://github.com/<OWNER>/<REPO> --token <TOKEN> --labels windows,real
```

4. Instalar como servicio (opcional) para persistencia y autorestart:

```powershell
.\svcinstall.cmd
Start-Service actions.runner.<OWNER>-<REPO>.<NAME>
```

Etiquetado
---------
Al configurar el runner, añade la etiqueta `real` (ej. `--labels windows,real`) para que el workflow `.github/workflows/real.yml` pueda apuntar a él.

Variables de entorno y configuración necesarias
---------------------------------------------
- `TSC_RD_DLL_DIR` (recomendado): directorio donde se encuentran las DLL del RailDriver/Train Simulator que el proceso `ingestion/rd_impl_real.py` requiere.
- `RAILWORKS_PLUGINS` (opcional): ruta alternativa usada por algunas instalaciones de RailWorks/Train Simulator.
- `TSC_RD` (opcional): si el entorno expone un endpoint RailDriver TCP, establecer `tcp://host:port`.

Recomendación de seguridad
-------------------------
- No poner rutas con credenciales en el repo. Configure las variables de entorno directamente en la máquina del runner o mediante `Environment variables` de la configuración del runner (no en el repositorio).
- Limitar acceso al runner: usar una cuenta de servicio con permisos mínimos necesarios y aplicar actualizaciones y un antivirus/endpoint adecuado.

Checks y preflight
-------------------
Antes de ejecutar la suite `real`, se recomienda comprobar:

- Python y dependencias (ejecutar `python -m pip install -r requirements.txt`).
- Que las DLL existen en `TSC_RD_DLL_DIR` y son accesibles por el usuario del runner.
- Que la red/puerto del RailDriver (si se usa) es accesible desde el runner.

Uso desde GitHub Actions
------------------------
El workflow `real.yml` en este repositorio usa `runs-on: [self-hosted, windows, real]`. El job será programado en cualquier runner que tenga las etiquetas `self-hosted`, `windows` y `real`.

Notas adicionales
----------------
- Si necesitas compartir el runner entre varios repositorios, considera crear un runner a nivel de organización y controlar el acceso mediante equipos.
- Para pruebas repetibles, documenta la versión exacta de las DLL y del juego utilizado; pequeñas diferencias de versión pueden afectar la API nativa.

Si quieres, puedo añadir un script de validación que verifique la presencia de las DLL y las variables de entorno; también puedo añadir un test de humo en `tests/` para que la suite `real` haga un skip controlado si falta la configuración.
