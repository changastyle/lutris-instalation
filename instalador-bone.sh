#!/bin/bash
# Script para instalar un juego desde una ISO, usando el entorno Flatpak de Lutris.
# Esta versión utiliza un escritorio virtual para garantizar que todas las ventanas
# de instalación (Mono, Gecko y la del juego) sean visibles.
set -e 

# --- CONFIGURACIÓN: Modifica estas variables si es necesario ---

# ID de la aplicación Flatpak de Lutris. No debería cambiar.
LUTRIS_FLATPAK_ID="net.lutris.Lutris"

# Ruta completa al archivo ISO del juego.
ISO="$HOME/Desktop/GOG/roller-coaster-tycoon-deluxe/RollerCoaster Tycoon Deluxe.iso"

# Ruta donde se creará el prefijo de Wine y se instalará el juego.
WINEPREFIX="$HOME/GOG GAMES/roller-coaster"

# (Opcional) Nombre del ejecutable de instalación (p. ej., setup.exe).
# Dejar vacío si quieres que busque cualquier .exe
SETUP_EXE_NAME="setup.exe"

# --- FIN DE LA CONFIGURACIÓN ---

# Crear la carpeta del WINEPREFIX si no existe
mkdir -p "$WINEPREFIX"

echo "📀 Montando ISO..."
ISO_DEVICE=$(udisksctl loop-setup -f "$ISO" | awk '{print $NF}' | sed 's/\.$//')
udisksctl mount -b "$ISO_DEVICE" >/dev/null
MOUNT_POINT=$(findmnt -n -o TARGET --source "$ISO_DEVICE")
echo "   -> ISO montado en: $MOUNT_POINT"

echo "🛠️  Creando WINEPREFIX de 32 bits (win32) si no existe..."
if [ ! -f "$WINEPREFIX/system.reg" ]; then
    echo "    -> El prefijo no existe, creando uno nuevo..."
    flatpak run --command=wineboot \
        --filesystem="$WINEPREFIX" \
        --env=WINEPREFIX="$WINEPREFIX" \
        --env=WINEARCH=win32 \
        "$LUTRIS_FLATPAK_ID" -u
else
    echo "    -> El prefijo ya existe, omitiendo creación."
fi

echo "🛠️  Asegurando que el prefijo use Windows XP..."
flatpak run --command=winecfg \
    --filesystem="$WINEPREFIX" \
    --env=WINEPREFIX="$WINEPREFIX" \
    "$LUTRIS_FLATPAK_ID" -v winxp >/dev/null 2>&1

echo "🚀 Buscando instalador .exe en el ISO..."
if [ -n "$SETUP_EXE_NAME" ]; then
    SETUP_EXE=$(find "$MOUNT_POINT" -maxdepth 2 -iname "$SETUP_EXE_NAME")
fi

if [ -z "$SETUP_EXE" ]; then
    echo "    -> No se encontró con nombre específico, buscando cualquier .exe..."
    SETUP_EXE=$(find "$MOUNT_POINT" -maxdepth 2 -iname "*.exe" ! -iname "unins*.exe" | head -n 1)
fi

if [ -z "$SETUP_EXE" ]; then
    echo "❌ No se encontró ningún archivo de instalación .exe en el ISO."
    udisksctl unmount -b "$ISO_DEVICE" && udisksctl loop-delete -b "$ISO_DEVICE"
    exit 1
fi

echo "✅ Instalador encontrado: $SETUP_EXE"
echo "🚀 Lanzando el instalador. Aparecerá un escritorio virtual."
echo "   Interactúa con TODAS las ventanas que aparezcan DENTRO de él."

# Ejecutamos el instalador dentro de un escritorio virtual para capturar todas las ventanas
flatpak run --command=wine \
    --filesystem="$MOUNT_POINT" \
    --filesystem="$WINEPREFIX" \
    --env=WINEPREFIX="$WINEPREFIX" \
    "$LUTRIS_FLATPAK_ID" explorer /desktop=install,1024x768 "$SETUP_EXE" 2>&1 | tee "$HOME/instalacion_juego.log"

echo "🧹 Desmontando ISO..."
udisksctl unmount -b "$ISO_DEVICE" && udisksctl loop-delete -b "$ISO_DEVICE"

echo "✅ Proceso completado."
echo "El log de la instalación se guardó en: $HOME/instalacion_juego.log"
echo ""
echo "👉 Ahora puedes agregar el juego a Lutris:"
echo "   1. WINEPREFIX: $WINEPREFIX"
echo "   2. Busca el ejecutable del juego dentro de '$WINEPREFIX/drive_c/'"