# Locust con la interfaz web del bloque B, para el docker-compose de la raíz
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias antes del código; mysql-connector-python solo lo usa limpiar_datos.py
# cuando recibe las variables LT_DB_* (conexión directa a cada base)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt mysql-connector-python==26.10.0

# Solo los archivos del bloque B
COPY bloque_b.py forma_estres.py preparar_datos.py limpiar_datos.py interfaz.py ./

# Usuario sin privilegios. La contraseña del usuario de prueba (.env) vive en el
# volumen /app/estado, para que no se pierda si el contenedor se recrea.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/estado \
    && ln -s /app/estado/.env /app/.env \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8089

CMD ["python", "interfaz.py"]
