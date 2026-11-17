"""Borra los datos de las pruebas de rendimiento (prefijos "LT" y "lt.").

Uso: python3 limpiar_datos.py  (desde pruebas/locust/)

Ejecuta SQL en el MySQL de cada servicio con `docker compose exec`, usando las
credenciales que el contenedor recibió de su .env; nunca las imprime. Orden:
ms-inventario (movimientos, traslados, saldos, bodegas), ms-productos
(productos, categorías) y gateway (tokens, sesiones y el usuario de prueba).
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent

INVENTARIO = [
    "DELETE FROM movimientos WHERE sku LIKE 'LT-%'",
    "DELETE FROM traslados WHERE sku LIKE 'LT-%'",
    "DELETE FROM saldos WHERE sku LIKE 'LT-%'",
    "DELETE FROM bodegas WHERE codigo LIKE 'LT-%'",
]
PRODUCTOS = [
    "DELETE FROM productos WHERE sku LIKE 'LT-%'",
    "DELETE FROM categorias WHERE nombre LIKE 'LT Cat %' AND id_categoria_padre IS NOT NULL",
    "DELETE FROM categorias WHERE nombre LIKE 'LT Cat %'",
]
USUARIOS = "SELECT id FROM users WHERE email LIKE 'lt.%'"
GATEWAY = [
    f"DELETE FROM personal_access_tokens WHERE tokenable_id IN ({USUARIOS}) AND tokenable_type LIKE '%User'",
    "DELETE FROM sessions WHERE user_id IN (SELECT id FROM (" + USUARIOS + ") AS u)",
    "DELETE FROM users WHERE email LIKE 'lt.%'",
]
CONTEOS = {
    "MS-Inventario": "SELECT (SELECT COUNT(*) FROM movimientos WHERE sku LIKE 'LT-%')"
                     " + (SELECT COUNT(*) FROM traslados WHERE sku LIKE 'LT-%')"
                     " + (SELECT COUNT(*) FROM saldos WHERE sku LIKE 'LT-%')"
                     " + (SELECT COUNT(*) FROM bodegas WHERE codigo LIKE 'LT-%')",
    "MS-Productos": "SELECT (SELECT COUNT(*) FROM productos WHERE sku LIKE 'LT-%')"
                    " + (SELECT COUNT(*) FROM categorias WHERE nombre LIKE 'LT Cat %')",
    "gateway": "SELECT COUNT(*) FROM users WHERE email LIKE 'lt.%'",
}


def sql(carpeta, sentencias):
    """Ejecuta las sentencias en una transacción y devuelve la salida sin encabezados."""
    texto = "START TRANSACTION; " + "; ".join(sentencias) + "; COMMIT;"
    comando = ['sh', '-c', 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" "$MYSQL_DATABASE" -N -e "$1"',
               'sh', texto]
    r = subprocess.run(["docker", "compose", "exec", "-T", "mysql", *comando],
                       cwd=RAIZ / carpeta, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Error en {carpeta}: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def main():
    sql("MS-Inventario", INVENTARIO)
    sql("MS-Productos", PRODUCTOS)
    sql("gateway", GATEWAY)
    env = Path(__file__).resolve().parent / ".env"
    if env.exists():
        env.unlink()  # la contraseña ya no sirve
    for carpeta, consulta in CONTEOS.items():
        print(f"{carpeta}: {sql(carpeta, [consulta]).splitlines()[-1]} filas de prueba")


if __name__ == "__main__":
    main()
