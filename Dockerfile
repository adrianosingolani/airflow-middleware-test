FROM python:3.9-slim
WORKDIR /app
COPY api_simulada.py .
RUN pip install Flask
CMD ["python", "api_simulada.py"]