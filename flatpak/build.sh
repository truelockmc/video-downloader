#!/bin/bash
flatpak-builder --install-deps-from=flathub build-dir io.github.truelockmc.video-downloader.yaml --force-clean

flatpak-builder --user --install build-dir io.github.truelockmc.video-downloader.yaml --force-clean


