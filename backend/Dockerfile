FROM python:3.11-slim

WORKDIR /app

# system deps (optional but safe)
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000