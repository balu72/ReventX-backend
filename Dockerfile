FROM python:3.11-alpine

# Create non-root user
RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -u 1001 -G appgroup

# Install system and Python build dependencies
RUN apk add --no-cache \
    g++ \
    libstdc++ \
    build-base \
    gcc \
    musl-dev \
    postgresql-dev \
    python3-dev \
    libffi-dev \
    postgresql-client \
    curl

# Set working directory
WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies directly in final image
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Entrypoint setup
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Change ownership
RUN chown -R appuser:appgroup /app

# Switch to appuser
USER appuser

# Set PATH just in case any scripts end up under .local/bin
ENV PATH=/home/appuser/.local/bin:$PATH

# Expose and health check
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "run.py"]
