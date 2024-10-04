# celery_gpt_service/Dockerfile
FROM python:3.10

# Set the working directory
WORKDIR /app



COPY requirements.txt .
# Copy the requirements file and install dependencies
RUN pip install -r requirements.txt

# Copy the application code and .env file
COPY . .

# Start Celery worker
CMD ["python", "-m", "handle_calls"]