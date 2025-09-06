# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# System build tools for native deps (e.g., fastuuid via maturin/cargo)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    pkg-config \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain for crates built via maturin
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y && \
    /root/.cargo/bin/rustc --version && \
    /root/.cargo/bin/cargo --version
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy the requirements file into the container at /app
COPY src/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run main.py when the container launches
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
