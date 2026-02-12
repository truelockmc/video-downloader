#!/bin/bash
flatpak-builder --install-deps-from=flathub build-dir io.github.truelockmc.video-downloader.yml --force-clean

flatpak-builder --user --install build-dir io.github.truelockmc.video-downloader.yml --force-clean
