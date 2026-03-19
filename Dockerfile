FROM python:3.12-slim

# System deps for weasyprint (PDF generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY engine/requirements.txt requirements-engine.txt
COPY requirements-web.txt requirements-web.txt
RUN pip install --no-cache-dir -r requirements-engine.txt -r requirements-web.txt

# Copy application
COPY engine/ engine/
COPY web/ web/
COPY context/ context/

# Run as non-root
USER nobody

EXPOSE 8000
CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]
