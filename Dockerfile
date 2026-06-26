# Deploy image for AI Circuit Architect.
#
# kicad-cli is a product runtime tool (real validation: open/export + ERC, and the
# server-side schematic preview rendered to SVG). Our templates emit the KiCad 9
# schematic format (version 20250114, generator_version 9.0), so the container needs
# KiCad >= 9. Ubuntu 24.04's repo only ships KiCad 7 (can't load 9-format files) and
# KiCad 6 has no kicad-cli at all, so we add the official KiCad 9 stable PPA.
#
# We use only schematic operations (sch export pdf/svg, sch erc) — no PCB, no 3D —
# so we install without recommends and strip 3D models / demos / docs to keep the
# image lean (~1.3 GB). Everything still degrades gracefully if kicad-cli were absent
# (structural checks still run; preview shows "render unavailable"), same principle as
# Mock Mode — the app always works.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp

RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common gpg-agent ca-certificates \
    && add-apt-repository -y ppa:kicad/kicad-9.0-releases \
    && apt-get update && apt-get install -y --no-install-recommends \
        kicad \
        python3 \
        python3-pip \
        fonts-dejavu-core \
        fontconfig \
    && apt-get purge -y software-properties-common gpg-agent \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/share/kicad/3dmodels \
              /usr/share/kicad/demos \
              /usr/share/doc/kicad*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
