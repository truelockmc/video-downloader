#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

BUILD_DIR="$PROJECT_DIR/linux-build"
DIST_DIR="$BUILD_DIR/dist"
DIST_DEPS="$BUILD_DIR/deps"
APPIMAGE_DIR="$BUILD_DIR/appimage"
CONTAINER_SCRIPT_PATH="$BUILD_DIR/container-script.sh"

# clean linux-build
rm -rf "$BUILD_DIR"
mkdir -p "$DIST_DIR" "$DIST_DEPS" "$APPIMAGE_DIR"

TOTAL_CPUS=$(nproc)
USE_CPUS=$(( TOTAL_CPUS * 75 / 100 ))
TOTAL_MEM=$(awk '/MemTotal/ {print $2}' /proc/meminfo)  # KB
USE_MEM=$(( TOTAL_MEM * 75 / 100 / 1024 ))             # MB

echo "→ Build mit $USE_CPUS CPUs und ${USE_MEM}MB RAM"

echo "→ Docker Image bauen"
docker build -f Dockerfile -t video-downloader-build "$PROJECT_DIR"

cat > "$CONTAINER_SCRIPT_PATH" <<'CONTAINER_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

EXCLUDED_IMPORTS=(
    PyQt6.QtMultimedia
    PyQt6.QtMultimediaWidgets
    PyQt6.QtQuick3D
    PyQt6.QtNfc
    PyQt6.QtTextToSpeech
    Cryptodome.SelfTest
)
EXCLUDE_ARGS=$(printf ' --exclude-module %s' "${EXCLUDED_IMPORTS[@]}")
echo "→ Starte PyInstaller Build mit ausgeschlossenen Modulen:" $EXCLUDE_ARGS

export PATH=/opt/venv/bin:$PATH

python3 -m PyInstaller \
    --noconfirm \
    --clean \
    --name VideoDownloader \
    --distpath /app/dist \
    --workpath /app/deps \
    --specpath /app/deps \
    --paths /opt/venv/lib/python3.9/site-packages \
    $EXCLUDE_ARGS \
    downloader.py

BINARY=/app/dist/VideoDownloader/VideoDownloader
if [ ! -f "$BINARY" ]; then
    echo 'ERROR: PyInstaller-Binary nicht gefunden!' >&2
    exit 1
fi

echo '→ RPATH Fix'
find /app/dist/VideoDownloader -type f -exec file -- {} \; \
    | grep 'ELF' \
    | cut -d: -f1 \
    | tr '\n' '\0' \
    | xargs -0 -r patchelf --set-rpath '$ORIGIN'

echo '→ AppImage Tools laden'
curl -L -o /app/appimage/linuxdeploy-x86_64.AppImage https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
chmod +x /app/appimage/linuxdeploy-x86_64.AppImage

echo '→ AppImage bauen (FUSE-frei)'
export APPIMAGE_EXTRACT_AND_RUN=1

(
  cd /app/appimage
  /app/appimage/linuxdeploy-x86_64.AppImage \
    --appdir /app/dist/VideoDownloader \
    -i /app/icon.png \
    -d /app/VideoDownloader.desktop \
    -e "$BINARY" \
    --output appimage
)

echo 'Cleaning up...'
shopt -s extglob || true

rm -rf /app/appimage/!(VideoDownloader-x86_64.AppImage)

rm -rf /app/dist/!(VideoDownloader)

rm -rf /app/dist/VideoDownloader/!(_internal|VideoDownloader)
echo '→ AppImage fertig, zu finden in /app/appimage/'
CONTAINER_SCRIPT

chmod +x "$CONTAINER_SCRIPT_PATH"

HOST_UID=$(id -u)
HOST_GID=$(id -g)

echo "→ Starte Container als UID:GID $HOST_UID:$HOST_GID und führe Build-Script aus (mount: $CONTAINER_SCRIPT_PATH -> /build/container-script.sh)"

docker run --rm \
    -v "$DIST_DIR:/app/dist" \
    -v "$DIST_DEPS:/app/deps" \
    -v "$APPIMAGE_DIR:/app/appimage" \
    -v "$CONTAINER_SCRIPT_PATH":/build/container-script.sh:ro \
    --cpus="$USE_CPUS" \
    --memory="${USE_MEM}m" \
    --user "$HOST_UID:$HOST_GID" \
    video-downloader-build \
    /bin/bash /build/container-script.sh

echo "→ Sicherstellen: Dateien im Build-Ordner gehören dir (UID:GID $HOST_UID:$HOST_GID)"
if chown -R "$HOST_UID:$HOST_GID" "$BUILD_DIR" 2>/dev/null; then
    echo "→ chown erfolgreich"
else
    echo "→ chown fehlgeschlagen (keine Rechte?). Versuch mit sudo..."
    if command -v sudo >/dev/null 2>&1 && sudo chown -R "$HOST_UID:$HOST_GID" "$BUILD_DIR"; then
        echo "→ chown mit sudo erfolgreich"
    else
        echo "WARN: Konnte Besitzrechte nicht ändern. Führe 'sudo chown -R $HOST_UID:$HOST_GID $BUILD_DIR' manuell aus."
    fi
fi

echo "→ Setze Standard-Permissions (dirs 755, files 644, behalte ausführbare Bits)"
find "$BUILD_DIR" -type d -exec chmod 755 {} \; || true

find "$BUILD_DIR" -type f -exec bash -c 'for f; do if [ -x "$f" ]; then chmod 755 "$f"; else chmod 644 "$f"; fi; done' _ {} +
echo "→ Berechtigungen gesetzt."
