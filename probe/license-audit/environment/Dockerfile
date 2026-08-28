FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends curl git jq \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
