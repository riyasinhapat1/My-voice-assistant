# Use a lightweight Python image
FROM python:3.10-slim  

# Install required system dependencies for PyAudio
RUN apt update && apt install -y gcc python3-dev portaudio19-dev  

# Set the working directory inside the container
WORKDIR /app  

# Copy the application files to the container
COPY . .  

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt  

# Expose port 8000 for the FastAPI server
EXPOSE 8000  

# Set the command to run the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
