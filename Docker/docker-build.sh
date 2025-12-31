#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="video-downloader-build"
APP_NAME="VideoDownloader"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"
APPIMAGE_DIR="$PROJECT_DIR/appimage"

rm -rf "$DIST_DIR" "$BUILD_DIR" "$APPIMAGE_DIR"
mkdir -p "$DIST_DIR" "$APPIMAGE_DIR"

# Resources: 75 %
TOTAL_CPUS=$(nproc)
USE_CPUS=$(( TOTAL_CPUS * 75 / 100 ))
TOTAL_MEM=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
USE_MEM=$(( TOTAL_MEM * 75 / 100 / 1024 ))

echo "→ Build mit $USE_CPUS CPUs und ${USE_MEM}MB RAM"

docker build -t "$IMAGE_NAME" -f "$SCRIPT_DIR/Dockerfile" "$PROJECT_DIR"

docker run --rm \
  -v "$PROJECT_DIR:/app" \
  --cpus="$USE_CPUS" \
  --memory="${USE_MEM}m" \
  "$IMAGE_NAME" \
  bash -c "
set -e

echo '→ PyInstaller Build'

pyinstaller \
  --clean \
  --noconfirm \
  --onedir \
  --name $APP_NAME \
  --windowed \
  --collect-all PyQt6 \
  --collect-all yt_dlp \
  --hidden-import=yt_dlp.extractor \
  --hidden-import=yt_dlp.postprocessor \
  downloader.py

echo '→ RPATH Fix'
patchelf --set-rpath '\$ORIGIN' dist/$APP_NAME/$APP_NAME

echo '→ AppImage Tools laden'
cd /app
wget -q https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
wget -q https://github.com/linuxdeploy/linuxdeploy-plugin-qt/releases/download/continuous/linuxdeploy-plugin-qt-x86_64.AppImage
chmod +x linuxdeploy*.AppImage

echo '→ AppImage bauen'
./linuxdeploy-x86_64.AppImage \
  --appdir AppDir \
  -e dist/$APP_NAME/$APP_NAME \
  -d app.desktop \
  -i icon.png \
  --plugin qt \
  --output appimage
"

echo
echo "✔ Build abgeschlossen"
echo "→ AppImage befindet sich im Projektverzeichnis"
