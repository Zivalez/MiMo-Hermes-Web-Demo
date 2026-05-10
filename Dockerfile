FROM python:3.11-slim

# Install git and nodejs/npm for the sandbox to be able to clone repos and run validation natively
RUN apt-get update && \
    apt-get install -y git curl apt-transport-https ca-certificates gnupg lsb-release && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files
COPY . .

# Expose the port for FastAPI
EXPOSE 8000

# Command to run the application
# Note: To use the Docker-based sandbox, you must mount the Docker socket when running this container:
# docker run -v /var/run/docker.sock:/var/run/docker.sock -p 8000:8000 mimo-web-demo
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
