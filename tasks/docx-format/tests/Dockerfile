FROM python:3.13-slim-bookworm

# TWO independent renderers, both pinned. A document that renders differently
# under two engines does not determine its own appearance, and will look
# different in whatever the reader opens it with. That property cannot be seen
# from one rendering, and it is the failure this domain is about.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer fonts-liberation fonts-dejavu curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Second engine: a self-contained build of a much later version, PINNED. The
# cross-engine assertions run to an 8 px tolerance, so the second engine must be
# a fixed version, not a rolling release channel — otherwise the test image
# silently changes under the suite over time. Pinned to a specific 25.8 build
# and its md5 is verified, so a bad or swapped download fails the build loudly
# instead of quietly re-defining what the tests measure. This exact build is the
# one the oracle was confirmed to agree with across engines (7.4.7 vs 25.8.6).
ARG LO_APPIMAGE=LibreOffice-25.8.6.2.basic-x86_64.AppImage
ARG LO_APPIMAGE_MD5=fcb75d773649bc4594430a65c002684e
RUN curl -sL -o /tmp/lo.AppImage \
        "https://appimages.libreitalia.org/${LO_APPIMAGE}" \
    && echo "${LO_APPIMAGE_MD5}  /tmp/lo.AppImage" | md5sum -c - \
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
