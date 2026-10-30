"""User-facing strings in every supported language."""
from __future__ import annotations

DEFAULT_LANGUAGE = "es"
LANGUAGES = {"es": "Español", "en": "English"}

STRINGS: dict[str, dict[str, str]] = {
    # --- process -----------------------------------------------------------
    "already_running": {
        "es": "{name} ya se está ejecutando (mira la bandeja del sistema).",
        "en": "{name} is already running (check the system tray).",
    },
    "crashed": {
        "es": "{name} se cerró por un error. Detalles en:\n{path}",
        "en": "{name} closed because of an error. Details in:\n{path}",
    },
    # --- tray menu ---------------------------------------------------------
    "menu_enabled": {"es": "Activado   ({hotkey})", "en": "Enabled   ({hotkey})"},
    "menu_calibrate": {"es": "Calibrar…   ({hotkey})", "en": "Calibrate…   ({hotkey})"},
    "menu_preview": {"es": "Vista previa de cámara", "en": "Camera preview"},
    "menu_delay": {"es": "Retardo antes de cambiar", "en": "Delay before switching"},
    "dwell_fast": {"es": "Rápido (200 ms)", "en": "Fast (200 ms)"},
    "dwell_normal": {"es": "Normal (350 ms)", "en": "Normal (350 ms)"},
    "dwell_slow": {"es": "Lento (600 ms)", "en": "Slow (600 ms)"},
    "menu_options": {"es": "Opciones", "en": "Options"},
    "opt_gaze_dot": {"es": "Mostrar punto de mirada", "en": "Show gaze dot"},
    "opt_flash": {"es": "Destello al cambiar de ventana", "en": "Flash on window switch"},
    "opt_learn": {"es": "Aprender de mis clics", "en": "Learn from my clicks"},
    "opt_fullscreen": {"es": "Pausar con apps a pantalla completa",
                       "en": "Pause for full-screen apps"},
    "opt_startup": {"es": "Iniciar con Windows", "en": "Start with Windows"},
    "menu_open_folder": {"es": "Abrir carpeta de datos", "en": "Open data folder"},
    "menu_quit": {"es": "Salir", "en": "Quit"},
    # --- notifications -----------------------------------------------------
    "displays_changed": {
        "es": "Tus pantallas han cambiado. Recalibra para mejor precisión.",
        "en": "Your displays have changed. Recalibrate for better accuracy.",
    },
    "recalibrate_new_version": {
        "es": "Nueva versión con mejor precisión: hay que calibrar otra vez.",
        "en": "New version with better accuracy: please calibrate again.",
    },
    "first_calibration": {
        "es": "Vamos a calibrar la mirada. Tarda unos 40 segundos.",
        "en": "Let's calibrate your gaze. It takes about 40 seconds.",
    },
    "calibration_saved": {
        "es": "Calibración guardada (precisión ≈ {accuracy:.0f} px).",
        "en": "Calibration saved (accuracy ≈ {accuracy:.0f} px).",
    },
    # --- status ------------------------------------------------------------
    "status_paused": {"es": "{name}: en pausa", "en": "{name}: paused"},
    "status_no_camera": {"es": "{name}: no se puede abrir la cámara",
                         "en": "{name}: cannot open the camera"},
    "status_dark": {"es": "{name}: la cámara se ve negra (¿tapa de privacidad?)",
                    "en": "{name}: the camera image is black (privacy shutter?)"},
    "status_needs_calibration": {"es": "{name}: falta calibrar", "en": "{name}: needs calibration"},
    "status_no_face": {"es": "{name}: no se detecta tu cara", "en": "{name}: no face detected"},
    "status_starting": {"es": "{name}: iniciando cámara…", "en": "{name}: starting camera…"},
    "status_active": {"es": "{name}: activo", "en": "{name}: active"},
    "block_mouse_button": {"es": "botón del ratón pulsado", "en": "mouse button pressed"},
    "block_mouse": {"es": "usando el ratón", "en": "using the mouse"},
    "block_typing": {"es": "escribiendo", "en": "typing"},
    "block_fullscreen": {"es": "app a pantalla completa", "en": "full-screen app"},
    # --- preview diagnostics (labels padded to line up in a fixed font) ------
    "preview_title": {"es": "Glance Switch · Vista previa", "en": "Glance Switch · Preview"},
    "diag_status": {"es": "Estado     ", "en": "Status     "},
    "diag_camera": {"es": "Cámara     ", "en": "Camera     "},
    "diag_head": {"es": "Cabeza     ", "en": "Head       "},
    "diag_blink": {"es": "  (parpadeo)", "en": "  (blink)"},
    "diag_eyes": {"es": "Ojos       mirada", "en": "Eyes       gaze"},
    "diag_gaze": {"es": "Mirada     ", "en": "Gaze       "},
    "diag_window": {"es": "Ventana    ", "en": "Window     "},
    "diag_blocked": {"es": "Bloqueo    ", "en": "Blocked    "},
    "diag_model": {
        "es": "Modelo     error ≈ {error:.0f} px  ·  {clicks} clics aprendidos  ·  {switches} cambios",
        "en": "Model      error ≈ {error:.0f} px  ·  {clicks} clicks learned  ·  {switches} switches",
    },
    "diag_tuning": {
        "es": "Ajuste     espera {dwell:.0f} ms  ·  radio {radius:.0f} px",
        "en": "Tuning     dwell {dwell:.0f} ms  ·  radius {radius:.0f} px",
    },
    # --- calibration -------------------------------------------------------
    "face_ok": {"es": "● Cara detectada", "en": "● Face detected"},
    "face_no_camera": {"es": "● No se puede abrir la cámara", "en": "● Cannot open the camera"},
    "face_dark": {"es": "● La cámara se ve negra: ¿está tapada la tapa de privacidad?",
                  "en": "● The camera image is black: is the privacy shutter closed?"},
    "face_starting": {"es": "● Iniciando cámara…", "en": "● Starting camera…"},
    "face_missing": {"es": "● No se detecta tu cara: colócate frente a la cámara",
                     "en": "● No face detected: sit in front of the camera"},
    "calib_title": {"es": "Calibración", "en": "Calibration"},
    "calib_intro": {
        "es": "Sigue con la mirada el punto azul y míralo fijamente hasta que se cierre.\n"
              "Mueve la cabeza con naturalidad, como cuando trabajas.",
        "en": "Follow the blue dot with your eyes and keep looking at it until it closes.\n"
              "Move your head naturally, as you do while working.",
    },
    "calib_length": {"es": "{points} puntos · unos {seconds} segundos",
                     "en": "{points} points · about {seconds} seconds"},
    "calib_start_keys": {"es": "Pulsa  Espacio  para empezar  ·  Esc  para cancelar",
                         "en": "Press  Space  to start  ·  Esc  to cancel"},
    "calib_validate_hint": {"es": "Ahora unos puntos más para medir la precisión real",
                            "en": "Now a few more points to measure the real accuracy"},
    "calib_too_few": {"es": "Solo se pudieron medir {measured} de {total} puntos.",
                      "en": "Only {measured} of {total} points could be measured."},
    "calib_fit_failed": {"es": "No se pudo calcular el modelo de mirada.",
                         "en": "Could not compute the gaze model."},
    "quality_excellent": {"es": "excelente", "en": "excellent"},
    "quality_good": {"es": "buena", "en": "good"},
    "quality_acceptable": {"es": "aceptable", "en": "acceptable"},
    "quality_low": {"es": "baja", "en": "low"},
    "accuracy_measured": {"es": "Precisión medida", "en": "Measured accuracy"},
    "accuracy_estimated": {"es": "Precisión estimada", "en": "Estimated accuracy"},
    "calib_done": {"es": "Calibración completada", "en": "Calibration complete"},
    "calib_follow": {"es": "Mira por la pantalla: el círculo sigue tu mirada.",
                     "en": "Look around the screen: the circle follows your gaze."},
    "calib_review_keys": {"es": "Espacio  guardar   ·   R  repetir   ·   Esc  cancelar",
                          "en": "Space  save   ·   R  repeat   ·   Esc  cancel"},
    "calib_failed": {"es": "La calibración no salió bien", "en": "Calibration did not succeed"},
    "calib_failed_hint": {"es": "Comprueba la luz y que la cámara te vea de frente.",
                          "en": "Check the lighting and that the camera sees you from the front."},
    "calib_failed_keys": {"es": "R  repetir   ·   Esc  cancelar", "en": "R  repeat   ·   Esc  cancel"},
}

_language = DEFAULT_LANGUAGE


def set_language(language: str) -> None:
    global _language
    _language = language if language in LANGUAGES else DEFAULT_LANGUAGE


def language() -> str:
    return _language


def t(key: str, **values) -> str:
    """Translated string for `key`, formatted with `values`."""
    entry = STRINGS[key]
    text = entry.get(_language) or entry[DEFAULT_LANGUAGE]
    return text.format(**values) if values else text
