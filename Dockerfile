FROM python:3.12-slim

# Install git and curl
RUN apt-get update && apt-get install -y git curl && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /workspace/radio-telemetry-tracker-drone-fds


