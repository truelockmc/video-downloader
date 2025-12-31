FROM ubuntu:20.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    build-essential \
    patchelf \
    libgl1 \
    libglib2.0-0 \
    libxkbcommon-x11-0 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-sync1 \
    libxrender1 \
    libxi6 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libxinerama1 \
    libxss1 \
    libfontconfig1 \
    libfreetype6 \
    git \
    curl \
    wget \
    file \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy all required project files from build context
COPY requirements.txt downloader.py gui.py utils.py workers.py Docker/icon.png Docker/VideoDownloader.desktop /app/

RUN chmod -R a+rX /app

# Setup venv and install dependencies
RUN python3 -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install pyinstaller
