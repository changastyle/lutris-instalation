#!/usr/bin/env python3
"""
INSTALADOR-GENERICO-LUTRIS.py

Gestiona juegos retro de Windows desde una carpeta con subcarpetas de juegos.
Crea accesos directos en escritorio, menú, y opcionalmente en Lutris.
No necesitas abrir Lutris para jugar.

Estructura:
  INSTALADORES-JUEGOS/
  ├── INSTALADOR-GENERICO-LUTRIS.py
  ├── MI-JUEGO-1/
  │   ├── setup.exe
  │   ├── drive_c/
  │   └── ...
  ├── OTRO-JUEGO/
  │   └── ...
  └── PORTADAS/              ← se ignora

Para excluir una carpeta, crea dentro un archivo .lutris-ignore
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# ─── CONSTANTES ─────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
DB_PATH = SCRIPT_DIR / "instalaciones.db"
CARPETAS_IGNORADAS = {"PORTADAS", "__pycache__", ".git"}


def leer_lutris_ignore():
    """
    Lee el archivo .lutris-ignore en la carpeta base (si existe).
    Cada línea es una carpeta a ignorar (excluye líneas vacías y comentarios).
    """
    ignore_file = SCRIPT_DIR / ".lutris-ignore"
    ignoradas = set()
    if ignore_file.exists():
        for linea in ignore_file.read_text().splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#"):
                ignoradas.add(linea)
    return ignoradas


# ─── COLORES ────────────────────────────────────────────────────────────────

class C:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"


def titulo(texto):
    print(f"\n{C.BOLD}{C.CYAN}{'─'*60}{C.RESET}")
    print(f"{C.BOLD}{texto}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'─'*60}{C.RESET}")


def ok(msg):
    print(f"  {C.GREEN}✓{C.RESET} {msg}")


def warn(msg):
    print(f"  {C.YELLOW}⚠{C.RESET} {msg}")


def fail(msg):
    print(f"  {C.RED}✗{C.RESET} {msg}")


def info(msg):
    print(f"  {C.DIM}{msg}{C.RESET}")


# ─── BASE DE DATOS ──────────────────────────────────────────────────────────

def init_db():
    """Crea la BD con la tabla de instalaciones si no existe."""
    db = sqlite3.connect(str(DB_PATH))
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS instalaciones (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT NOT NULL,
            slug        TEXT NOT NULL UNIQUE,
            carpeta     TEXT NOT NULL,
            exe         TEXT,
            wine_prefix TEXT,
            win_version TEXT,
            directx     INTEGER DEFAULT 0,
            lutris      INTEGER DEFAULT 0,
            fecha_inst  TEXT,
            ultimo_juego TEXT,
            estado      TEXT DEFAULT 'sin_probar',
            notas       TEXT
        )
    """)
    db.commit()
    db.close()


def juego_instalado(slug):
    """Devuelve True si el juego ya está registrado en la BD."""
    db = sqlite3.connect(str(DB_PATH))
    cur = db.cursor()
    cur.execute("SELECT id FROM instalaciones WHERE slug = ?", (slug,))
    existe = cur.fetchone() is not None
    db.close()
    return existe


def guardar_instalacion(nombre, slug, carpeta, exe, wine_prefix, win_version, directx, lutris):
    """Guarda o actualiza la instalación en la BD."""
    db = sqlite3.connect(str(DB_PATH))
    cur = db.cursor()
    ahora = datetime.now().isoformat()

    if juego_instalado(slug):
        cur.execute("""
            UPDATE instalaciones SET
                nombre=?, exe=?, wine_prefix=?, win_version=?,
                directx=?, lutris=?, fecha_inst=?
            WHERE slug=?
        """, (nombre, str(exe), str(wine_prefix), win_version, int(directx), int(lutris), ahora, slug))
    else:
        cur.execute("""
            INSERT INTO instalaciones
            (nombre, slug, carpeta, exe, wine_prefix, win_version, directx, lutris, fecha_inst, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nombre, slug, str(carpeta), str(exe), str(wine_prefix), win_version, int(directx), int(lutris), ahora, "instalado"))

    db.commit()
    db.close()


def actualizar_estado(slug, estado, notas=""):
    """Marca un juego como funcionando / no funcionando."""
    db = sqlite3.connect(str(DB_PATH))
    cur = db.cursor()
    cur.execute("""
        UPDATE instalaciones SET estado=?, notas=? WHERE slug=?
    """, (estado, notas, slug))
    db.commit()
    db.close()


def actualizar_ultimo_juego(slug):
    db = sqlite3.connect(str(DB_PATH))
    cur = db.cursor()
    cur.execute("""
        UPDATE instalaciones SET ultimo_juego=? WHERE slug=?
    """, (datetime.now().isoformat(), slug))
    db.commit()
    db.close()


def listar_instalaciones():
    """Muestra el historial de instalaciones."""
    db = sqlite3.connect(str(DB_PATH))
    cur = db.cursor()
    cur.execute("""
        SELECT nombre, carpeta, win_version, directx, lutris, fecha_inst, estado, notas
        FROM instalaciones ORDER BY fecha_inst DESC
    """)
    filas = cur.fetchall()
    db.close()
    return filas


# ─── UTILIDADES ─────────────────────────────────────────────────────────────

def preguntar_si_no(pregunta, default="s"):
    while True:
        opts = "[s/N]" if default == "n" else "[S/n]"
        r = input(f"  {pregunta} {opts}: ").strip().lower()
        if r == "":
            return default == "s"
        if r in ("s", "si", "sí", "y", "yes"):
            return True
        if r in ("n", "no", "not"):
            return False
        print("  Responde 's' o 'n'")


def preguntar_opcion(pregunta, opciones, default=0):
    print(f"\n  {pregunta}")
    for i, (_, desc) in enumerate(opciones):
        marca = f" {C.CYAN}►{C.RESET}" if i == default else ""
        print(f"    {i}) {desc}{marca}")
    while True:
        r = input(f"  Elige [0-{len(opciones)-1}] (Enter = {default}): ").strip()
        if r == "":
            return opciones[default][0]
        if r.isdigit() and 0 <= int(r) < len(opciones):
            return opciones[int(r)][0]
        print(f"  Número inválido (0-{len(opciones)-1})")


def slugify(nombre):
    s = nombre.lower().strip()
    for c in "áéíóúàèìòùäëïöüñ":
        s = s.replace(c, "aeiouaeiouaeioun"["áéíóúàèìòùäëïöüñ".index(c)])
    s = "".join(c if c.isalnum() or c in " -_" else "" for c in s)
    return "-".join(s.split())


# ─── PASO 1: LISTAR JUEGOS ─────────────────────────────────────────────────

def obtener_carpetas_juego():
    """
    Busca subcarpetas en SCRIPT_DIR que parezcan juegos.
    Excluye:
      - carpetas_ignoradas fijas (PORTADAS, __pycache__, .git)
      - carpetas listadas en .lutris-ignore
      - carpetas que empiezan con .
    """
    ignoradas_por_archivo = leer_lutris_ignore()
    todas_ignoradas = CARPETAS_IGNORADAS | ignoradas_por_archivo

    carpetas = []
    for item in sorted(SCRIPT_DIR.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith("."):
            continue
        if item.name in todas_ignoradas:
            continue
        carpetas.append(item)
    return carpetas


def listar_juegos():
    titulo("JUEGOS DISPONIBLES")

    carpetas = obtener_carpetas_juego()

    if not carpetas:
        print(f"\n  {C.YELLOW}No se encontraron carpetas con juegos.{C.RESET}")
        print(f"  Copia cada juego a una subcarpeta dentro de:")
        print(f"  {SCRIPT_DIR}")
        print(f"\n  Para excluir carpetas, añádelas al archivo .lutris-ignore")
        sys.exit(1)

    # Mostrar menú con detección de si ya están instalados
    opciones = []
    for c in carpetas:
        nombre = c.name.replace("-", " ").replace("_", " ").title()
        slug = slugify(nombre)

        # Detectar si ya fue instalado antes
        instalado = juego_instalado(slug)
        marcador = f" {C.GREEN}[instalado]{C.RESET}" if instalado else ""

        # Detectar contenido
        extras = []
        if (c / "drive_c").exists():
            extras.append("drive_c")
        if (c / "setup.exe").exists() or (c / "Autorun.exe").exists():
            extras.append("instalador")
        if list(c.glob("*.exe")):
            extras.append(".exe")
        if list(c.glob("*.iso")):
            extras.append("ISO")

        desc = nombre + marcador
        if extras:
            desc += f"  {C.DIM}({', '.join(extras)}){C.RESET}"

        opciones.append((c, desc))

    # Añadir opción de historial
    opciones.append(("_historial", f"{C.DIM}Ver historial de instalaciones{C.RESET}"))
    opciones.append(("_salir", f"{C.DIM}Salir{C.RESET}"))

    sel = preguntar_opcion("¿Qué juego quieres instalar/configurar?", opciones, default=0)

    if sel == "_historial":
        mostrar_historial()
        print()
        input("  Presiona Enter para volver al menú...")
        return listar_juegos()
    if sel == "_salir":
        print("\n  Saliendo...")
        sys.exit(0)

    return sel


def mostrar_historial():
    titulo("HISTORIAL DE INSTALACIONES")
    filas = listar_instalaciones()
    if not filas:
        info("No hay instalaciones registradas aún.")
        return

    print(f"\n  {'Juego':<30} {'Windows':<10} {'DX':<4} {'Lutris':<7} {'Estado':<14} {'Fecha'}")
    print(f"  {'─'*30} {'─'*10} {'─'*4} {'─'*7} {'─'*14} {'─'*25}")
    for nombre, carpeta, win_ver, dx, lutris, fecha, estado, notas in filas:
        dx_str = f"{C.GREEN}si{C.RESET}" if dx else f"{C.DIM}no{C.RESET}"
        lut_str = f"{C.GREEN}si{C.RESET}" if lutris else f"{C.DIM}no{C.RESET}"
        est_str = {
            "instalado": f"{C.YELLOW}instalado{C.RESET}",
            "funciona": f"{C.GREEN}funciona{C.RESET}",
            "no_funciona": f"{C.RED}no funciona{C.RESET}",
            "sin_probar": f"{C.DIM}sin probar{C.RESET}",
        }.get(estado, estado)
        fec = fecha[:10] if fecha else "?"
        carp = Path(carpeta).name if carpeta else "?"
        print(f"  {carp:<30} {win_ver or '?':<10} {dx_str:<4} {lut_str:<7} {est_str:<14} {fec}")


# ─── PASO 2: NOMBRE ────────────────────────────────────────────────────────

def preguntar_nombre(game_dir):
    titulo("NOMBRE DEL JUEGO")
    sugerencia = game_dir.name.replace("-", " ").replace("_", " ").title()
    r = input(f"\n  Nombre [{sugerencia}]: ").strip()
    return r if r else sugerencia


# ─── PASO 3: DETECTAR IMÁGENES / ARCHIVOS / .EXE ───────────────────────────

def buscar_exe_en(game_dir):
    """Busca todos los .exe en la carpeta y dentro de drive_c/Program Files.
       Busca recursivamente en subcarpetas (hasta 3 niveles)."""
    candidatos = []
    vistos = set()

    def agregar(ruta, etiqueta=""):
        p = Path(ruta).resolve()
        if p.exists() and p.suffix.lower() == ".exe" and str(p) not in vistos:
            vistos.add(str(p))
            tam = p.stat().st_size
            desc = f"{p.name} ({tam//1024} KB)"
            if etiqueta:
                desc += f" {C.DIM}— {etiqueta}{C.RESET}"
            candidatos.append((p, desc))

    # Buscar recursivamente hasta 4 niveles de profundidad
    for root, dirs, files in os.walk(game_dir):
        root_p = Path(root)
        # Saltar drive_c (se busca aparte) y __pycache__
        rel = root_p.relative_to(game_dir)
        if "drive_c" in rel.parts or "__pycache__" in rel.parts:
            continue
        profundidad = len(rel.parts)
        if profundidad > 4:
            continue
        for f in files:
            if f.lower().endswith(".exe"):
                etiqueta = ""
                if profundidad > 0:
                    etiqueta = f"en {rel.parent.name}/" if profundidad == 1 else f"en .../{rel.name}/"
                agregar(root_p / f, etiqueta)

    prog = game_dir / "drive_c" / "Program Files"
    if prog.exists():
        for root, _, files in os.walk(prog):
            for f in files:
                if f.lower().endswith(".exe"):
                    ruta = Path(root) / f
                    tam = ruta.stat().st_size
                    if 100 * 1024 < tam < 200 * 1024 * 1024:
                        try:
                            rel = ruta.relative_to(prog)
                            if str(ruta) not in vistos:
                                vistos.add(str(ruta))
                                candidatos.append((ruta, f"{rel} ({tam//1024} KB) {C.DIM}[instalado]{C.RESET}"))
                        except ValueError:
                            pass
    candidatos.sort(key=lambda x: x[0].stat().st_size)
    return candidatos


def detectar_imagen_o_archivo(game_dir):
    """Busca imágenes de disco (.iso, .img, .ccd, .nrg, .mdf, .bin)
       y archivos comprimidos (.zip, .rar, .7z, .tar.gz, .tar.xz, .gz).
       También busca ISOs dentro de carpetas _extraido_.
       Devuelve el más pesado (mayor probabilidad de ser el juego)."""
    formatos_imagen = (".iso", ".img", ".ccd", ".nrg", ".mdf", ".bin")
    formatos_zip = (".zip", ".rar", ".7z", ".tar.gz", ".tar.xz", ".gz", ".z")

    candidatos = []
    # Buscar en game_dir y un nivel dentro de _extraido_
    busquedas = [game_dir]
    for sub in sorted(game_dir.iterdir()):
        if sub.is_dir() and sub.name.startswith("_extraido_"):
            busquedas.append(sub)

    for base in busquedas:
        for f in sorted(base.iterdir()):
            if not f.is_file():
                continue
            ext = "".join(f.suffixes).lower() if len(f.suffixes) > 1 else f.suffix.lower()
            if any(ext.endswith(fmt) for fmt in formatos_imagen + formatos_zip):
                peso = f.stat().st_size
                tipo = "imagen CD" if any(ext.endswith(fmt) for fmt in formatos_imagen) else "comprimido"
                candidatos.append((f, f"{f.name} ({peso//1024//1024} MB) — {tipo}"))

    candidatos.sort(key=lambda x: x[0].stat().st_size, reverse=True)
    return candidatos


def etiqueta_archivo(archivo):
    """Devuelve la acción correcta según el tipo de archivo."""
    ext = archivo.suffix.lower()
    if ext in (".iso",):
        return "Montar ISO"
    if ext == ".img":
        # Si tiene .ccd al lado es CloneCD, sino es raw
        if archivo.with_suffix(".ccd").exists():
            return "Convertir CloneCD y montar"
        return "Convertir a ISO y montar"
    if ext == ".bin":
        if archivo.with_suffix(".cue").exists():
            return "Convertir BIN/CUE y montar"
        return "Extraer con 7z"
    return "Extraer comprimido"


def instalar_si_falta(programa, paquete):
    """Instala un programa con apt si no está disponible."""
    if shutil.which(programa):
        return True
    warn(f"{programa} no está instalado.")
    if not preguntar_si_no(f"¿Instalar {paquete}? (sudo)", default="s"):
        return False
    r = subprocess.run(["sudo", "apt", "install", "-y", paquete],
                       capture_output=True, text=True)
    if r.returncode == 0:
        ok(f"{paquete} instalado")
        return True
    fail(f"Error: {r.stderr[-300:]}")
    return False


def extraer_con_7z(archivo, destino):
    """Extrae un archivo (.iso, .zip, .rar, .7z, etc.) con 7z o unrar."""
    if not instalar_si_falta("7z", "p7zip-full"):
        return False

    print(f"  Extrayendo {archivo.name}...")
    destino.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["7z", "x", str(archivo), f"-o{destino}", "-y"],
        capture_output=True, text=True
    )
    if r.returncode == 0:
        ok(f"Extraído en: {destino}")
        return True

    # RAR5 no es soportado completamente por 7z; intentar con unrar
    if archivo.suffix.lower() == ".rar" and instalar_si_falta("unrar", "unrar"):
        print(f"  7z falló con RAR5. Intentando con unrar...")
        r2 = subprocess.run(
            ["unrar", "x", "-y", str(archivo), str(destino) + "/"],
            capture_output=True, text=True
        )
        if r2.returncode == 0 or r2.returncode == 10:  # 10 = algunos errores no críticos
            ok(f"Extraído con unrar en: {destino}")
            return True
        fail(f"Error con unrar: {r2.stderr[-300:]}")
        return False

    fail(f"Error al extraer: {r.stderr[-300:]}")
    return False


def ccd_a_cue(archivo_ccd):
    """
    Convierte un .ccd (CloneCD) a .cue para usarlo con bchunk.
    Retorna la ruta del .cue generado.
    """
    archivo_img = archivo_ccd.with_suffix(".img")
    cue_path = archivo_ccd.with_suffix(".cue")

    if cue_path.exists():
        return cue_path

    # Parsear .ccd para obtener info de pistas
    track_mode = 2  # MODE=2 por defecto (CD-ROM XA)
    index = 0
    with open(archivo_ccd) as f:
        in_track = False
        for linea in f:
            linea = linea.strip()
            if linea == "[TRACK 1]":
                in_track = True
            elif in_track:
                if linea.startswith("MODE="):
                    track_mode = int(linea.split("=")[1])
                    continue
                if linea.startswith("INDEX 1="):
                    index = int(linea.split("=")[1])
                    break

    # Asignar modo CUE según el modo CloneCD
    if track_mode == 0:
        cue_mode = "MODE1/2352"
    elif track_mode == 1:
        cue_mode = "MODE1/2048"
    else:
        cue_mode = "MODE2/2352"

    # Calcular tiempo en MSF desde LBA
    minutos = index // (60 * 75)
    segundos = (index // 75) % 60
    frames = index % 75

    with open(cue_path, "w") as f:
        f.write(f'FILE "{archivo_img.name}" BINARY\n')
        f.write(f'  TRACK 01 {cue_mode}\n')
        f.write(f'    INDEX 01 {minutos:02d}:{segundos:02d}:{frames:02d}\n')

    return cue_path


def convertir_img_a_iso(archivo_img, game_dir):
    """
    Convierte una imagen CloneCD (.img + .ccd) a .iso usando bchunk.
    bchunk es la herramienta estándar para convertir .img/.bin a .iso.
    """
    if not instalar_si_falta("bchunk", "bchunk"):
        return None

    iso_destino = game_dir / f"{archivo_img.stem}.iso"
    if iso_destino.exists():
        ok(f"ISO ya existente: {iso_destino}")
        return iso_destino

    # Buscar o generar .cue
    ccd_path = archivo_img.with_suffix(".ccd")
    cue_path = archivo_img.with_suffix(".cue")
    if not cue_path.exists() and ccd_path.exists():
        ok("Generando .cue desde .ccd...")
        cue_path = ccd_a_cue(ccd_path)
    if not cue_path.exists():
        cue_path = archivo_img  # raw .img sin acompañante

    output_base = archivo_img.with_suffix("")

    print(f"  Convirtiendo {archivo_img.name} a ISO...")
    r = subprocess.run(
        ["bchunk", str(archivo_img), str(cue_path), str(output_base)],
        capture_output=True, text=True
    )
    # bchunk genera {output_base}01.iso (track number)
    iso_generado = game_dir / f"{archivo_img.stem}01.iso"
    if r.returncode == 0 and iso_generado.exists():
        iso_generado.rename(iso_destino)
        ok(f"Convertido a ISO: {iso_destino}")
        return iso_destino

    fail(f"Error al convertir: {r.stderr[-300:]}")
    return None


def montar_y_extraer_iso(iso_path, destino):
    """
    Monta un .iso con mount -o loop y copia los archivos a destino.
    Si mount falla, intenta extraer con 7z como fallback.
    Requiere sudo para mount.
    Retorna True si se copiaron archivos correctamente.
    """
    if not shutil.which("mount"):
        fail("mount no está disponible")
        return False

    punto_montaje = Path("/tmp") / f"_mounted_{iso_path.stem}"
    punto_montaje.mkdir(parents=True, exist_ok=True)

    print(f"  Montando {iso_path.name}... (se necesita sudo)")
    r = subprocess.run(
        ["sudo", "mount", "-o", "loop,ro", str(iso_path), str(punto_montaje)],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        warn(f"No se pudo montar: {r.stderr[-200:]}")
        ok("Intentando extraer con 7z como alternativa...")
        return extraer_con_7z(iso_path, destino)

    ok("ISO montado. Copiando archivos...")
    destino.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "-r", f"{punto_montaje}/.", str(destino)],
                   capture_output=True)

    subprocess.run(["sudo", "umount", str(punto_montaje)], capture_output=True)
    ok(f"Archivos copiados a: {destino}")
    return True


def elegir_exe_o_extraer(game_dir, wineprefix):
    """
    Busca .exe. Si no encuentra, busca imágenes/archivos y ofrece extraerlos.
    Devuelve la ruta del .exe o None si no se pudo determinar.
    """
    titulo("DETECTANDO EJECUTABLE")

    # Primera pasada: buscar .exe directamente
    exes = buscar_exe_en(game_dir)
    if exes:
        opciones = [(exe, desc) for exe, desc in exes]
        opciones.append((None, f"{C.DIM}Especificar ruta manualmente{C.RESET}"))
        sel = preguntar_opcion("¿Cuál es el ejecutable principal?", opciones, default=0)
        if sel is None:
            while True:
                r = input("  Ruta del .exe: ").strip()
                if r:
                    p = Path(r).resolve()
                    if p.exists():
                        return p
                    fail("No existe")
        return sel

    # No hay .exe → buscar imágenes/archivos
    warn("No se encontraron archivos .exe.")
    archivos = detectar_imagen_o_archivo(game_dir)

    if not archivos:
        fail("Tampoco se encontraron imágenes (.iso, .img) ni archivos (.zip, .rar).")
        while True:
            r = input("  Ruta manual del .exe o imagen: ").strip()
            if r:
                p = Path(r).resolve()
                if p.exists():
                    return p
                fail("No existe")
        return None

    print(f"\n  Se encontraron estos archivos:")
    opciones = []
    for archivo, desc in archivos:
        carpeta_extraccion = game_dir / f"_extraido_{archivo.stem}"
        ya_extraido = carpeta_extraccion.exists()
        accion = etiqueta_archivo(archivo)
        marcador = f" {C.GREEN}[ya extraído]{C.RESET}" if ya_extraido else ""
        opciones.append((archivo, f"{accion} '{desc}'{marcador}"))

    opciones.append((None, f"{C.DIM}Especificar ruta manualmente{C.RESET}"))

    sel = preguntar_opcion("¿Qué archivo contiene el juego?", opciones, default=0)

    if sel is None:
        while True:
            r = input("  Ruta del .exe o imagen: ").strip()
            if r:
                p = Path(r).resolve()
                if p.exists():
                    return p
                fail("No existe")
        return None

    archivo = sel
    carpeta_extraccion = game_dir / f"_extraido_{archivo.stem}"

    if carpeta_extraccion.exists():
        ok(f"Ya extraído antes en: {carpeta_extraccion}")
    else:
        # Según el tipo de archivo, elegir método de extracción
        ext = archivo.suffix.lower()

        # .img (con o sin .ccd) → convertir a ISO y montar
        if ext == ".img":
            if (game_dir / f"{archivo.stem}.ccd").exists():
                warn("Imagen CloneCD detectada (.img + .ccd + .sub)")
            else:
                warn("Imagen .img detectada, convirtiendo a ISO...")
            iso = convertir_img_a_iso(archivo, game_dir)
            if iso and iso.exists():
                ok("ISO generado. Extrayendo contenido...")
                if not montar_y_extraer_iso(iso, carpeta_extraccion):
                    return None
            else:
                fail("No se pudo convertir la imagen a ISO.")
                return None

        # .iso → montar y extraer
        elif ext == ".iso":
            if not montar_y_extraer_iso(archivo, carpeta_extraccion):
                return None

        # .bin → buscar .cue asociado, convertir con bchunk
        elif ext == ".bin":
            cue = game_dir / f"{archivo.stem}.cue"
            if cue.exists():
                warn("Imagen BIN/CUE detectada")
                iso = convertir_img_a_iso(archivo, game_dir)
                if iso and iso.exists():
                    if not montar_y_extraer_iso(iso, carpeta_extraccion):
                        return None
                else:
                    return None
            else:
                warn(".bin sin .cue, intentando extraer con 7z...")
                if not extraer_con_7z(archivo, carpeta_extraccion):
                    return None

        # .zip, .rar, .7z, etc. → extraer con 7z
        else:
            if not extraer_con_7z(archivo, carpeta_extraccion):
                return None

    # Re-buscar .exe dentro de lo extraído
    print("\n  Buscando .exe en los archivos extraídos...")
    exes = buscar_exe_en(carpeta_extraccion)

    # Si no hay .exe, buscar ISOs dentro y montarlos
    if not exes:
        isos_internos = sorted(carpeta_extraccion.rglob("*.iso")) + sorted(carpeta_extraccion.rglob("*.ISO"))
        isos_internos += sorted(carpeta_extraccion.rglob("*.img")) + sorted(carpeta_extraccion.rglob("*.IMG"))
        for iso_int in isos_internos:
            sub_destino = carpeta_extraccion / f"_disc_{iso_int.stem}"
            if not sub_destino.exists() and montar_y_extraer_iso(iso_int, sub_destino):
                exes = buscar_exe_en(sub_destino)
                if exes:
                    carpeta_extraccion = sub_destino
                    break

    if exes:
        exes = [(exe, desc) for exe, desc in exes
                if "setup" in exe.stem.lower() or "install" in exe.stem.lower()
                or exe.stat().st_size > 500 * 1024]
        if not exes:
            exes = buscar_exe_en(carpeta_extraccion)
        if len(exes) == 1:
            ok(f"Encontrado: {exes[0][0].name}")
            return exes[0][0]
        opciones = [(exe, desc) for exe, desc in exes]
        opciones.append((None, f"{C.DIM}Especificar ruta manualmente{C.RESET}"))
        sel = preguntar_opcion("¿Cuál es el ejecutable?", opciones, default=0)
        if sel is None:
            while True:
                r = input("  Ruta del .exe: ").strip()
                if r:
                    p = Path(r).resolve()
                    if p.exists():
                        return p
                    fail("No existe")
        return sel

    # Si sigue sin encontrar, ofrecer recorrer todo
    warn("No se encontraron .exe en lo extraído.")
    r = input("  Ruta manual del .exe (Enter para cancelar): ").strip()
    if r:
        p = Path(r).resolve()
        if p.exists():
            return p
    return None


# ─── PASO 4: WINE PREFIX ───────────────────────────────────────────────────

def configurar_wine_prefix(game_dir):
    titulo("WINE PREFIX")

    prefix_local = game_dir / "drive_c"

    if prefix_local.exists():
        ok("drive_c/ encontrado en la carpeta del juego")
        if preguntar_si_no("¿Usar este Wine prefix?", default="s"):
            return prefix_local

    op = preguntar_opcion("¿Qué quieres hacer?", [
        ("crear_local", f"Crear drive_c/ dentro de la carpeta {C.DIM}(recomendado){C.RESET}"),
        ("compartido", "Usar ~/.wine u otro existente"),
    ], default=0)

    if op == "crear_local":
        prefix_local.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "WINEPREFIX": str(prefix_local), "WINEARCH": "win32"}
        print("  Inicializando Wine prefix...")
        subprocess.run(["wineboot", "-u"], env=env, capture_output=True, check=False)
        ok("Wine prefix creado")
        return prefix_local

    if Path.home().joinpath(".wine").exists():
        return Path.home() / ".wine"
    r = input("  Ruta del Wine prefix: ").strip()
    p = Path(r).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


# ─── PASO 5: VERSIÓN DE WINDOWS ────────────────────────────────────────────

def elegir_version_windows():
    titulo("VERSIÓN DE WINDOWS")
    return preguntar_opcion("¿Qué versión simular?", [
        ("winxp", "Windows XP (2001, recomendado para juegos 2000s)"),
        ("win98", "Windows 98 (1998, para juegos pre-2000)"),
        ("win7", "Windows 7 (2009, alternativa)"),
        ("win2k", "Windows 2000"),
    ], default=0)


# ─── PASO 6: INSTALAR ──────────────────────────────────────────────────────

def ejecutar_instalador(game_dir, wineprefix):
    instaladores = []
    for n in ["setup.exe", "SETUP.EXE", "Autorun.exe", "AUTORUN.EXE", "install.exe"]:
        p = game_dir / n
        if p.exists():
            instaladores.append(p)

    if not instaladores:
        return

    titulo("INSTALACIÓN")
    warn("El juego parece no estar instalado en el Wine prefix.")
    if preguntar_si_no(f"¿Ejecutar {instaladores[0].name} para instalarlo?", default="s"):
        env = {**os.environ, "WINEPREFIX": str(wineprefix), "WINEARCH": "win32"}
        print("\n  Ejecutando instalador... (sigue las instrucciones en pantalla)")
        print("  Cuando termine, cierra la ventana del instalador.")
        subprocess.run(["wine", str(instaladores[0])], env=env, check=False)
        print()
        ok("Instalador cerrado.")


# ─── PASO 7: DIRECTX ───────────────────────────────────────────────────────

def instalar_directx(wineprefix):
    titulo("DIRECTX 9 (OPCIONAL)")

    dll = wineprefix / "drive_c" / "windows" / "system32" / "d3d9.dll"
    if dll.exists():
        ok("DirectX 9 ya está instalado en este Wine prefix")
        return True

    warn("No se detectó DirectX 9. Muchos juegos lo necesitan.")
    print("  winetricks lo descarga e instala dentro del Wine prefix.")
    info("⏱ Puede tardar 5-15 minutos.")

    if not preguntar_si_no("¿Instalar DirectX 9 ahora?", default="s"):
        return False

    env = {**os.environ, "WINEPREFIX": str(wineprefix), "WINEARCH": "win32"}
    print("\n  Instalando DirectX 9... (no cierres el terminal)")
    sys.stdout.flush()
    r = subprocess.run(["winetricks", "-q", "directx9"], env=env, capture_output=True, text=True)
    if r.returncode == 0:
        ok("DirectX 9 instalado")
        return True
    else:
        warn(f"Error: {r.stderr[-300:]}")
        return False


# ─── PASO 8: PORTADA ───────────────────────────────────────────────────────

def elegir_portada(game_dir):
    titulo("PORTADA / CARÁTULA")

    fmt = ("*.jpg", "*.jpeg", "*.png", "*.ico", "*.bmp")
    imgs = []
    for f in fmt:
        imgs.extend(sorted(game_dir.glob(f)))
        imgs.extend(sorted(game_dir.glob(f.upper())))
    imgs = [i for i in imgs if i.stat().st_size > 10000]

    if not imgs:
        for sub in game_dir.iterdir():
            if sub.is_dir() and sub.name not in ("drive_c", "__pycache__"):
                for f in fmt:
                    imgs.extend(sub.glob(f))
        imgs = [i for i in imgs if i.stat().st_size > 10000]

    if not imgs:
        print("  No se encontraron imágenes.")
        r = input("  Ruta o URL de portada (Enter = saltar): ").strip()
        if not r:
            return None
        p = Path(r)
        if p.exists():
            return p
        if r.startswith(("http://", "https://")):
            return descargar_portada(r, game_dir)
        return None

    imgs = [i for i in imgs if "thumb" not in i.stem.lower()]
    imgs.sort(key=lambda x: x.stat().st_size, reverse=True)

    op = [(i, f"{i.name} ({i.stat().st_size//1024} KB)") for i in imgs[:8]]
    op.append((None, "Elegir otra manualmente"))
    op.append(("skip", "No usar portada"))

    sel = preguntar_opcion("¿Cuál usar como portada?", op, default=0)
    if sel == "skip":
        return None
    if sel is None:
        r = input("  Ruta o URL de la imagen: ").strip()
        if not r:
            return None
        p = Path(r)
        if p.exists():
            return p
        if r.startswith(("http://", "https://")):
            return descargar_portada(r, game_dir)
        return None
    return sel


def descargar_portada(url, game_dir):
    """Descarga una imagen desde una URL y la guarda en game_dir."""
    import urllib.request
    print(f"  Descargando portada...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            ct = r.headers.get("Content-Type", "")
    except Exception as e:
        warn(f"Error al descargar: {e}")
        return None

    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
               "image/bmp": ".bmp", "image/gif": ".gif"}
    ext = ext_map.get(ct, ".jpg")

    destino = game_dir / f"portada{ext}"
    destino.write_bytes(data)
    ok(f"Portada descargada: {destino} ({len(data)//1024} KB)")
    return destino


def copiar_portada(imagen, nombre_juego):
    slug = slugify(nombre_juego)
    dst = Path.home() / ".local" / "share" / "lutris" / "coverart"
    dst.mkdir(parents=True, exist_ok=True)
    dest = dst / f"{slug}{imagen.suffix.lower()}"
    shutil.copy2(imagen, dest)
    ok(f"Portada copiada: {dest}")
    return dest


# ─── ACCIONES ───────────────────────────────────────────────────────────────

def verificar_dependencias():
    faltan = []
    for cmd, pkg in [("wine", "wine"), ("winecfg", "wine"), ("winetricks", "winetricks")]:
        if shutil.which(cmd) is None:
            faltan.append(pkg)
    if shutil.which("lutris") is None:
        faltan.append("lutris")

    if faltan:
        unicos = sorted(set(faltan))
        print(f"\n  {C.YELLOW}Faltan: {', '.join(unicos)}{C.RESET}")
        if preguntar_si_no("¿Instalar con apt? (sudo)", default="s"):
            r = subprocess.run(["sudo", "apt", "install", "-y"] + unicos, capture_output=True, text=True)
            if r.returncode != 0:
                fail(f"Error: {r.stderr[-300:]}")
                sys.exit(1)
            ok("Instalado")
        else:
            sys.exit(1)

    print()
    for cmd in ["wine", "lutris", "winetricks"]:
        if shutil.which(cmd):
            try:
                v = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
                print(f"  {C.DIM}{cmd}: {(v.stdout or v.stderr).strip()[:60]}{C.RESET}")
            except Exception:
                pass


def configurar_wine(wineprefix, version):
    env = {**os.environ, "WINEPREFIX": str(wineprefix), "WINEARCH": "win32"}
    subprocess.run(["winecfg", "-v", version], env=env, capture_output=True, check=False)
    ok(f"Windows {version.upper()}")


def listar_runners_lutris():
    """Lista los Wine runners instalados por Lutris."""
    runners = Path.home() / ".local" / "share" / "lutris" / "runners" / "wine"
    if not runners.is_dir():
        return []
    return sorted(
        (v for v in runners.iterdir() if v.is_dir()),
        key=lambda x: x.name, reverse=True
    )


def buscar_recomendacion_lutris(nombre_juego):
    """
    Consulta la API de Lutris para obtener info del juego.
    Retorna dict con datos útiles o None.
    """
    import urllib.request, urllib.parse, json
    q = urllib.parse.quote(nombre_juego)
    url = f"https://lutris.net/api/games?search={q}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        warn(f"No se pudo consultar Lutris: {e}")
        return None

    results = data.get("results", [])
    if not results:
        return None

    # Filtrar Windows
    windows = [g for g in results if g.get("platform") in ("windows", None)]
    if not windows:
        windows = results

    game = windows[0]
    slug = game.get("slug")
    year = game.get("year", "?")

    # Obtener detalle
    try:
        du = f"https://lutris.net/api/games/{slug}"
        with urllib.request.urlopen(du, timeout=10) as r2:
            detail = json.loads(r2.read().decode())
    except Exception:
        detail = {}

    installers = detail.get("installers", [])
    # Extraer configs destacables de los scripts
    system_configs = {}
    for inst in installers[:5]:
        scr = inst.get("script", {})
        for key in ("wine", "system", "game"):
            val = scr.get(key)
            if isinstance(val, dict):
                for k, v in val.items():
                    if k not in system_configs:
                        system_configs[k] = v

    return {
        "name": game.get("name", nombre_juego),
        "slug": slug,
        "year": year,
        "installers": [{"name": i.get("name"), "version": i.get("version", "?")}
                       for i in installers[:5]],
        "config": system_configs,
    }


def recomendar_wine_y_runner(nombre_juego):
    """
    Busca info en Lutris y muestra al usuario recomendaciones de Wine.
    Retorna la ruta del Wine runner elegido (o None para usar el del sistema).
    """
    titulo("RECOMENDACIÓN DE WINE / RUNNER")

    # 1. Consultar Lutris API
    lutris_data = buscar_recomendacion_lutris(nombre_juego)
    if lutris_data:
        print(f"  {C.CYAN}Información desde Lutris.net:{C.RESET}")
        print(f"    Juego:    {lutris_data['name']} ({lutris_data['year']})")
        print(f"    Slug:     {lutris_data['slug']}")
        if lutris_data['installers']:
            print(f"    Versiones disponibles:")
            for v in lutris_data['installers'][:3]:
                print(f"      • {v['name']} ({v['version']})")
    else:
        info("Sin resultados en Lutris.")

    # 2. Listar runners instalados
    runners = listar_runners_lutris()
    if runners:
        print(f"\n  {C.CYAN}Wine runners instalados (Lutris):{C.RESET}")
        for r in runners:
            print(f"    • {r.name}")
    else:
        info("No hay Wine runners de Lutris instalados.")

    # 3. Elegir Wine binary
    opciones = [("sistema", f"Usar Wine del sistema ({shutil.which('wine') or 'wine'})")]
    for r in runners:
        wine_bin = r / "bin" / "wine"
        if wine_bin.exists():
            opciones.append((str(wine_bin), f"Usar {r.name} (Lutris runner)"))
    opciones.append(("ninguno", "Preguntar después"))

    sel = preguntar_opcion("¿Qué versión de Wine usar?", opciones, default=0)
    if sel == "ninguno":
        return None
    if sel == "sistema":
        return None  # None = usar wine del PATH
    return sel


def crear_lanzador(game_dir, wineprefix, exe_path, nombre_juego, wine_binary=None):
    slug = slugify(nombre_juego)
    launcher = game_dir / f"{slug}.sh"
    wine_cmd = wine_binary or "wine"
    launcher.write_text(f"""#!/bin/bash
# Lanzador: {nombre_juego}
export WINEPREFIX="{wineprefix}"
export WINEARCH="win32"
LOG="{launcher}.log"
cd "{exe_path.parent}"
echo "[$(date)] Iniciando: {wine_cmd} '{exe_path}'" >> "$LOG"
{wine_cmd} "{exe_path}" >> "$LOG" 2>&1
EXIT=$?
echo "[$(date)] Salida: codigo $EXIT" >> "$LOG"
exit $EXIT
""")
    launcher.chmod(0o755)
    ok(f"Script lanzador: {launcher}")
    return launcher


def detectar_lutris_wine():
    """Devuelve la ruta al Wine de Lutris más reciente, o None."""
    runners = Path.home() / ".local" / "share" / "lutris" / "runners" / "wine"
    if not runners.exists():
        return None
    vers = sorted(runners.iterdir(), reverse=True) if runners.is_dir() else []
    for v in vers:
        wine_bin = v / "bin" / "wine"
        if wine_bin.exists():
            return str(wine_bin)
    return None


def crear_accesos(game_dir, wineprefix, exe_path, nombre_juego, portada, launcher):
    slug = slugify(nombre_juego)
    icono = str(portada) if portada else "applications-other"

    desktop = f"""[Desktop Entry]
Type=Application
Name={nombre_juego}
Comment=Lanzador para {nombre_juego}
Exec="{launcher}"
Path={exe_path.parent}
Icon={icono}
Terminal=false
Categories=Game;
StartupNotify=true
"""

    # Guardar .desktop en la carpeta del juego
    juego_desktop = game_dir / f"INSTALADOR-{slug}.desktop"
    juego_desktop.write_text(desktop)
    juego_desktop.chmod(0o755)
    ok(f"Local: {juego_desktop}")

    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    menu = apps / f"INSTALADOR-{slug}.desktop"
    menu.write_text(desktop)
    menu.chmod(0o755)
    ok(f"Menú: {menu}")

    for d in [Path.home() / "Escritorio", Path.home() / "Desktop"]:
        if d.exists():
            desk = d / f"INSTALADOR-{slug}.desktop"
            desk.write_text(desktop)
            desk.chmod(0o755)
            ok(f"Escritorio: {desk}")
            break
    else:
        warn("Carpeta de escritorio no encontrada")


def registrar_en_lutris(nombre_juego, slug, game_dir, exe_path, portada=None):
    titulo("LUTRIS (OPCIONAL)")
    if not preguntar_si_no("¿Registrar también en Lutris?", default="s"):
        print("  No se registrará. Los accesos directos funcionan igual.")
        return False

    if shutil.which("lutris") is None:
        warn("Lutris no está instalado.")
        return False

    cfg_dir = Path.home() / ".config" / "lutris" / "games"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    config_name = f"{slug}-{int(time.time())}"

    yaml = f"""game:
  exe: {exe_path}
  prefix: {game_dir}/drive_c
system:
  env:
    WINEPREFIX: {game_dir}/drive_c
    WINEARCH: win32
wine:
  version: lutris-ge-8-26-x86_64
  dxvk: false
  vkd3d: false
  Desktop: false
"""
    (cfg_dir / f"{config_name}.yml").write_text(yaml)

    db_path = Path.home() / ".local" / "share" / "lutris" / "pga.db"
    if not db_path.exists():
        return False

    try:
        db = sqlite3.connect(str(db_path))
        c = db.cursor()
        c.execute("DELETE FROM games WHERE slug = ?", (slug,))
        c.execute('''INSERT INTO games
            (name, sortname, slug, installer_slug, platform, runner,
             executable, directory, installed, installed_at, lastplayed,
             updated, configpath, year)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (nombre_juego, slug[:8], slug, slug, "Windows", "wine",
             str(exe_path), str(game_dir), 1, int(time.time()), 0,
             datetime.now().isoformat(), config_name, 0))
        db.commit()
        db.close()
        ok("Registrado en Lutris")

        # Copiar portada si existe
        if portada and portada.exists():
            cover_dir = Path.home() / ".local" / "share" / "lutris" / "coverart"
            cover_dir.mkdir(parents=True, exist_ok=True)
            ext = portada.suffix
            shutil.copy2(portada, cover_dir / f"{slug}{ext}")
            ok(f"Portada copiada a Lutris: {slug}{ext}")

        warn("NO uses 'Desinstalar' desde Lutris: borraría la carpeta del juego.")
        return True
    except Exception as e:
        warn(f"Error: {e}")
        return False


def preguntar_estado(slug, nombre):
    """Pregunta al usuario si el juego funciona o no."""
    titulo("¿CÓMO FUE?")
    print(f"  ¿{nombre} funcionó correctamente?")
    op = preguntar_opcion("Selecciona:", [
        ("funciona", f"{C.GREEN}Funciona correctamente{C.RESET}"),
        ("no_funciona", f"{C.RED}No funciona / tiene errores{C.RESET}"),
        ("sin_probar", f"{C.DIM}Todavía no lo probé{C.RESET}"),
    ], default=2)

    notas = ""
    if op == "no_funciona":
        notas = input("  Describe el problema (opcional): ").strip()

    actualizar_estado(slug, op, notas)
    if op == "funciona":
        ok("¡Genial! Marcado como funcionando.")
    elif op == "no_funciona":
        warn("Marcado como no funcional. Revisa las notas más tarde.")
    else:
        info("Sin problema. Puedes marcarlo después desde el historial.")


# ─── MAIN ───────────────────────────────────────────────────────────────────

def main():
    print()
    print(f"{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}║    INSTALADOR GENERICO DE JUEGOS RETRO                  ║{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}║    Linux Mint / Ubuntu / Debian                        ║{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════════════╝{C.RESET}")
    print()
    info(f"Carpeta de juegos: {SCRIPT_DIR}")
    info(f"Base de datos:    {DB_PATH}")
    print()

    init_db()
    verificar_dependencias()

    # 1. Elegir juego (o ver historial)
    game_dir = listar_juegos()
    print(f"\n  {C.BOLD}Juego seleccionado:{C.RESET} {game_dir.name}")

    # 2. Nombre
    nombre_juego = preguntar_nombre(game_dir)
    slug = slugify(nombre_juego)

    # 3. Detectar .exe o extraer imágenes/archivos
    exe_path = elegir_exe_o_extraer(game_dir, None)

    # 4. Wine prefix
    wineprefix = configurar_wine_prefix(game_dir)

    # 5. Si el exe no está disponible, ofrecer instalador
    if exe_path is None or not exe_path.exists():
        ejecutar_instalador(game_dir, wineprefix)
        exe_path = elegir_exe_o_extraer(game_dir, wineprefix)

    if not exe_path.exists():
        fail("No se pudo determinar el ejecutable del juego.")
        guardar_instalacion(nombre_juego, slug, game_dir, "", wineprefix, "", False, False)
        actualizar_estado(slug, "no_funciona", "No se encontró el .exe")
        sys.exit(1)

    # 6. Versión de Windows
    win_ver = elegir_version_windows()
    configurar_wine(wineprefix, win_ver)

    # 7. DirectX
    dx_instalado = instalar_directx(wineprefix)

    # 8. Portada
    portada = elegir_portada(game_dir)
    if portada:
        portada = copiar_portada(portada, nombre_juego)

    # 9. Recomendar Wine runner (consulta Lutris API)
    lutris_wine = recomendar_wine_y_runner(nombre_juego)

    # 10. Crear lanzador y accesos directos
    launcher = crear_lanzador(game_dir, wineprefix, exe_path, nombre_juego, lutris_wine)
    crear_accesos(game_dir, wineprefix, exe_path, nombre_juego, portada, launcher)

    # 11. Lutris (opcional)
    lutris_ok = registrar_en_lutris(nombre_juego, slug, game_dir, exe_path, portada)

    # 12. Guardar en BD
    guardar_instalacion(nombre_juego, slug, game_dir, exe_path, wineprefix, win_ver, dx_instalado, lutris_ok)

    # 12. Preguntar estado
    preguntar_estado(slug, nombre_juego)

    # ─── Fin ─────────────────────────────────────────────────────────
    print()
    print(f"{C.BOLD}{C.GREEN}╔══════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}{C.GREEN}║   ¡JUEGO LISTO PARA JUGAR!                             ║{C.RESET}")
    print(f"{C.BOLD}{C.GREEN}╚══════════════════════════════════════════════════════════╝{C.RESET}")
    print()
    print(f"  {C.BOLD}{nombre_juego}{C.RESET} está configurado.")
    print()
    print("  Puedes jugar desde:")
    print(f"    {C.GREEN}•{C.RESET} El escritorio (acceso directo)")
    print(f"    {C.GREEN}•{C.RESET} El menú de aplicaciones")
    print(f"    {C.GREEN}•{C.RESET} Terminal:  {game_dir}/{slug}.sh")
    if lutris_ok:
        print(f"    {C.GREEN}•{C.RESET} Lutris")
        warn("NO uses 'Desinstalar' desde Lutris: borra toda la carpeta.")
    print()


if __name__ == "__main__":
    main()
