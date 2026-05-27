FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Hermes Agent
RUN curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Copy Hermes context files
RUN mkdir -p ~/.hermes/skills
RUN echo "WHATSAPP_ENABLED=false" >> ~/.hermes/.env
RUN cp SOUL.md ~/.hermes/SOUL.md
RUN cp .hermes.md ~/.hermes/.hermes.md
RUN cp skills/* ~/.hermes/skills/ 2>/dev/null || true

# Install Python dependencies
RUN pip install fastapi uvicorn anthropic python-dotenv apscheduler sqlalchemy twilio python-multipart

# Expose port
EXPOSE 8000

# FastAPI always starts; Hermes gateway is optional (errors suppressed)
CMD ["sh", "-c", "hermes gateway --no-whatsapp 2>/dev/null & python -m uvicorn agent.main:app --host 0.0.0.0 --port 8000"]
