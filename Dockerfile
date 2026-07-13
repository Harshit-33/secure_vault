# Use an official lightweight Python base image
FROM python:3.11-slim

# Set system environment optimization variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container runtime environment
WORKDIR /app

# Install system dependencies required for compiling heavy C/C++ dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first to optimize Docker layer caching definitions
COPY requirements.txt /app/

# Install the Python package dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application source code into the working folder matrix
COPY . /app/

# Expose the network socket interface port that Uvicorn binds to
EXPOSE 8088

# Run the Uvicorn application service server instance
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8088"]
