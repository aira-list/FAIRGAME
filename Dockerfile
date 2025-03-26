FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy everything in the current folder (where Dockerfile resides) to /LLMFactory in the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set PYTHONPATH to include the current working directory (i.e., /LLMFactory)
ENV PYTHONPATH=/app

# Set environment variables to optimize Python and Docker behavior
ENV DOCKER_ENV=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir -r requirements.txt

RUN export $(grep -v '^#' /app/.env | xargs)

EXPOSE 5003

CMD ["python", "api.py"]
