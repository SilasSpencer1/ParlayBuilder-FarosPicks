FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md /app/
COPY ev_parlay /app/ev_parlay
COPY api /app/api
COPY web /app/web
RUN pip install --no-cache-dir fastapi uvicorn requests pydantic pandas numpy pulp rich PyYAML
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
