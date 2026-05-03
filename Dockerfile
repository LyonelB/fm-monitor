FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Dépendances système
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    rtl-sdr \
    ffmpeg \
    icecast2 \
    git \
    openssl \
    build-essential \
    libopenblas-dev \
    meson ninja-build \
    libsndfile1-dev libliquid-dev \
    gnuradio gr-osmosdr \
    libfftw3-dev libsamplerate0-dev \
    udev \
    && rm -rf /var/lib/apt/lists/*

# Règles udev RTL-SDR
RUN echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0666"' \
    > /etc/udev/rules.d/20-rtlsdr.rules && \
    echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", GROUP="plugdev", MODE="0666"' \
    >> /etc/udev/rules.d/20-rtlsdr.rules

# Compiler redsea
RUN git clone --quiet https://github.com/windytan/redsea.git /tmp/redsea && \
    cd /tmp/redsea && \
    meson setup build && \
    ninja -C build -j$(nproc) && \
    ninja -C build install && \
    rm -rf /tmp/redsea

# Configurer Icecast2
COPY docker/icecast.xml /etc/icecast2/icecast.xml

# Répertoire de travail
WORKDIR /app

# Installer les dépendances Python
COPY requirements.txt .
RUN python3 -m venv venv && \
    venv/bin/pip install --quiet --upgrade pip setuptools wheel && \
    venv/bin/pip install --quiet -r requirements.txt

# Copier le code
COPY . .

# Générer les certificats SSL si absents
RUN if [ ! -f cert.pem ]; then \
    openssl req -x509 -newkey rsa:4096 -nodes \
    -out cert.pem -keyout key.pem -days 3650 \
    -subj "/C=FR/ST=France/L=Paris/O=FM Monitor/CN=fm-monitor.local" 2>/dev/null; \
    fi

# Script de démarrage
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000 8000

ENTRYPOINT ["/entrypoint.sh"]
