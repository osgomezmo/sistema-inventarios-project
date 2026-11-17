# Imagen base de Python
FROM python:3.12-slim

# Sin archivos .pyc y con la salida de logs sin búfer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias antes del código, para aprovechar la caché de capas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la aplicación (la configuración llega por variables de entorno)
COPY app/ app/
COPY db/ db/
COPY run.py .
COPY --chmod=755 entrypoint.sh .

# Usuario sin privilegios
RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 5000

# Espera a la base, migra y siembra si está vacía; luego ejecuta CMD
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:5000", "run:app"]
