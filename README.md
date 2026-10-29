# Glance Switch (prototipo Windows)

Mueve el foco del teclado a la ventana que estás mirando, sin hacer clic.
Usa la webcam para estimar la orientación de la cabeza y la posición del iris,
todo en local y en memoria: ningún fotograma se guarda ni sale del equipo.

## Uso

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m glance          # con consola (logs visibles)
.\.venv\Scripts\pythonw run_glance.pyw    # sin consola, solo icono en la bandeja
```

La primera vez se abre la calibración: sigue el punto azul con la mirada
(~20 s). Al final verás un círculo que sigue tu mirada para comprobar la
precisión; pulsa **Espacio** para guardar o **R** para repetir.

| Atajo | Acción |
|---|---|
| `Ctrl+Alt+G` | Activar / pausar |
| `Ctrl+Alt+K` | Recalibrar |

Desde el icono de la bandeja: retardo (rápido / normal / lento), vista previa
de la cámara con diagnóstico, punto de mirada, destello al cambiar, iniciar
con Windows, etc.

## Llevarlo a otro PC (sin instalar Python)

```powershell
.\build.ps1        # genera dist\GlanceSwitch-windows.zip (~126 MB)
```

Copia el zip, descomprímelo en cualquier carpeta y abre `GlanceSwitch.exe`.
Windows SmartScreen avisará porque el ejecutable no está firmado:
«Más información» → «Ejecutar de todas formas».

## Cómo funciona

1. **`tracker.py`** — captura a 720p/15 fps y pasa cada fotograma por
   MediaPipe Face Landmarker (478 puntos + matriz de pose).
2. **`features.py`** — yaw/pitch de la cabeza, posición del iris dentro de
   cada ojo, posición de la cabeza y detección de parpadeo.
3. **`model.py`** — regresión ridge (con términos cuadráticos) de esas
   características a coordenadas de pantalla. La fuerza se elige por
   validación cruzada dejando fuera un punto de calibración, lo que da un
   error estimado honesto en píxeles.
4. **Aprendizaje con clics** — cada clic es una muestra gratis («miras donde
   haces clic»); el modelo se reajusta solo cada 5 clics válidos.
5. **`app.py` / `decider.py`** — filtro One Euro, votación difusa de la
   ventana bajo la mirada (respetando qué ventana tapa a cuál), y cambio solo
   tras un tiempo de permanencia, con tolerancia a parpadeos y enfriamiento.
6. **No molesta**: no cambia mientras usas el ratón, mientras escribes
   (para que puedas copiar mirando otro documento), con un botón pulsado o con
   una app a pantalla completa.
7. **`win32.py`** — enumeración de ventanas en orden Z (ignorando ventanas
   ocultas, de otros escritorios virtuales y de la shell) y activación
   robusta pese a las restricciones de foco de Windows.

Datos (ajustes, calibración, log): `%APPDATA%\GlanceSwitch`.

## Tests

```powershell
.\.venv\Scripts\python -m pytest -q
```

## Limitaciones conocidas

- La precisión con webcam ronda 100–200 px: perfecto entre monitores o
  ventanas grandes, no para paneles pequeños dentro de una misma ventana
  (pendiente: UI Automation para paneles divididos).
- Si mueves mucho la silla respecto a la calibración, recalibra (o deja que
  aprenda de tus clics).
- Apps que se ejecutan como administrador no aceptan el foco desde un
  proceso normal.
