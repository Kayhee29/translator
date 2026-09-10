FROM python:3.10-slim
WORKDIR /app

# Copy toàn bộ code lên
COPY . /app/
RUN pip install -r requirements.txt

# Mở port 8000
EXPOSE 8000

# Khởi chạy server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
