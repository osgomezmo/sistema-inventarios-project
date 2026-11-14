# MS-Compras

Microservicio de gestion de ordenes de compra, recepciones de mercancia y devoluciones a proveedores del Sistema de Gestion de Inventarios.

## Requisitos

- Python 3.12+
- MySQL 8.x (base de datos `mscompras`)
- RabbitMQ (exchange `inventario.eventos` tipo `topic`)
- Acceso de red hacia `ms-proveedores`

## Configuracion

1. Copiar `.env.example` a `.env` y ajustar credenciales, URL de RabbitMQ, URL de `ms-proveedores` y `SERVICE_TOKEN`.
2. Instalar dependencias en un entorno virtual:
   ```bash
   python -m venv .venv
   pip install -r requirements.txt
   ```
3. Aplicar migraciones SQL:
   ```bash
   python db/aplicar_migraciones.py
   ```
4. Iniciar el servicio:
   ```bash
   python run.py
   ```

## Docker

```bash
docker build -t ms-compras:latest .
docker run --env-file .env -p 5003:5000 ms-compras:latest
```

Para detalles completos de endpoints, eventos RabbitMQ y reglas de negocio consultar [AGENTS.md](AGENTS.md).
