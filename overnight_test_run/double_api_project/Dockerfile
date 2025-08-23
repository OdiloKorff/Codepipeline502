FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY main.py .
RUN adduser --disabled-password appuser
USER appuser
EXPOSE 5000
CMD ["python", "main.py"]
