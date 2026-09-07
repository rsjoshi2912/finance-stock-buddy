FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/app
COPY backend/requirements-lock.txt /srv/app/backend/requirements-lock.txt
RUN pip install --no-cache-dir -r backend/requirements-lock.txt && useradd --uid 10001 --create-home journal
COPY backend /srv/app/backend
RUN mkdir -p /srv/app/data && chown journal:journal /srv/app/data
USER journal
WORKDIR /srv/app/backend
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
