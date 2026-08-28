FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc g++ make time procps curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
