# Basis-Image
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# Systemabhängigkeiten
RUN apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    build-essential \
    patchelf \
    libgl1 \
    libglib2.0-0 \
    libglib2.0-dev \
    libxkbcommon-x11-0 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis
WORKDIR /app

# Alles aus dem Build-Kontext kopieren
COPY . /app

# Virtuelle Umgebung & Python-Abhängigkeiten
RUN python3 -m venv venv \
    && . venv/bin/activate \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install nuitka

# Build-Befehl
ENV NUITKA_EXTRA_OPTIONS="--nofollow-import-to=Cryptodome.SelfTest"

CMD ["/bin/bash", "-c", ". venv/bin/activate && python -m nuitka $NUITKA_EXTRA_OPTIONS --standalone --onefile --enable-plugin=pyqt5 --include-package=yt_dlp --include-package=Cryptodome  --follow-imports --output-filename=VideoDownloader downloader.py"]


