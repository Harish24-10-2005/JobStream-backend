# ===========================================
# JobAI Backend - Production Dockerfile
# Multi-stage build for optimized image size
# ===========================================

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (let pip resolve versions)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim as runtime

WORKDIR /app

# Install runtime dependencies (Chrome for browser automation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome (using modern GPG key method, apt-key is deprecated)
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with home directory for browser_use config
RUN groupadd -r jobai && useradd -r -g jobai -m -d /home/jobai jobai

# Create browser_use config directory
RUN mkdir -p /home/jobai/.config/browseruse/profiles \
    && chown -R jobai:jobai /home/jobai

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=jobai:jobai . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/output /app/chrome_data \
    && chown -R jobai:jobai /app

# Switch to non-root user
USER jobai

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    HOME=/home/jobai \
    BROWSER_USE_CONFIG_DIR=/home/jobai/.config/browseruse

# Expose port
EXPOSE 8000

# Health check (longer start period for heavy imports)
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

# Run application - use shell form to expand $PORT from Render
CMD python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
