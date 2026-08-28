FROM python:3.13-slim-bookworm

# TWO independent renderers, both pinned. A document that renders differently
# under two engines does not determine its own appearance, and will look
# different in whatever the reader opens it with. That property cannot be seen
# from one rendering, and it is the failure this domain is about.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer fonts-liberation fonts-dejavu curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Second engine: a self-contained build of a much later version.
RUN curl -sL -o /tmp/lo.AppImage \
        "https://appimages.libreitalia.org/LibreOffice-still.basic-x86_64.AppImage" \
    && chmod +x /tmp/lo.AppImage \
    && cd /opt && /tmp/lo.AppImage --appimage-extract >/dev/null \
    && mv squashfs-root libreoffice-second \
    && rm /tmp/lo.AppImage \
    && ln -s "$(find /opt/libreoffice-second -name soffice -type f | head -1)" /usr/local/bin/soffice2

RUN pip install --no-cache-dir \
        pytest==9.1.1 pytest-json-ctrf==0.5.2 \
        pymupdf==1.28.2 numpy==2.2.3 scipy==1.15.2

COPY . /tests/
RUN mkdir -p /app /logs/verifier
