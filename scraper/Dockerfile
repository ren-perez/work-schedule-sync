# Scraper image - includes headless Chromium and chromedriver
FROM python:3.13.7-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies for Chromium + fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    gnupg2 \
    unzip \
    chromium \
    chromium-driver \
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libcups2 \
    libxext6 \
    libxrender1 \
    libgtk-3-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# Set Chrome to run in no-sandbox mode (required for containers)
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default port for Cloud Run (can be overridden)
ENV PORT=8080
EXPOSE 8080

# Use exec form for better signal handling
ENTRYPOINT ["python", "scraper.py"]