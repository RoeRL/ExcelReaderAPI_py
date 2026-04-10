FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure the uploads directory exists
RUN mkdir -p uploads

# Copy your script (Make sure this matches your actual filename!)
COPY app.py . 

# Run it (Ensure host is 0.0.0.0 inside the script)
CMD ["python3", "app.py"]
