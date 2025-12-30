#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

mkdir -p "$PROJECT_DIR/dist"

docker build -t video-downloader-build "$PROJECT_DIR" -f "$SCRIPT_DIR/Dockerfile"

docker run --rm -v "$PROJECT_DIR/dist:/app/dist" video-downloader-build

echo "Build abgeschlossen. Binary befindet sich in $PROJECT_DIR/dist/"
