#!/bin/bash
flatpak-builder --install-deps-from=flathub build-dir com.truelockmc.VideoDownloader.yaml --force-clean

flatpak-builder --user --install build-dir com.truelockmc.VideoDownloader.yaml --force-clean


