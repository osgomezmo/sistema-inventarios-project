"""Borra los datos de las pruebas de rendimiento (prefijos "LT" y "lt.").

Uso: python limpiar_datos.py  (desde pruebas/locust/)

Orden: ms-inventario (movimientos, traslados, saldos, bodegas), ms-productos
(productos, categorías) y gateway (tokens, sesiones y el usuario de prueba).
Nunca imprime credenciales. Cada base se alcanza de una de dos formas:

- Con las variables LT_DB_<BASE>_HOST, _PORT, _USER, _PASSWORD y _NAME (BASE es
  PRODUCTOS, INVENTARIO o GATEWAY): conexión directa con mysql-connector-python.
  Es lo que usa el contenedor de Locust del docker-compose de la raíz.
- Sin ellas: `docker exec` al contenedor MySQL de cada servicio, con las
  credenciales que ese contenedor recibió de su .env. Sirve con los compose de
  cada servicio y con el de la raíz, porque los contenedores se llaman igual.
"""

import os
import subprocess
import sys
from pathlib import Path

# Base -> contenedor MySQL (mismo nombre en los compose de cada servicio y en el de la raíz)
CONTENEDORES = {
    "INVENTARIO": "ms-inventario-mysql",
    "PRODUCTOS": "ms-productos-mysql",
    "GATEWAY": "api-gateway-mysql",
}

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
    "INVENTARIO": "SELECT (SELECT COUNT(*) FROM movimientos WHERE sku LIKE 'LT-%')"
                     " + (SELECT COUNT(*) FROM traslados WHERE sku LIKE 'LT-%')"
                     " + (SELECT COUNT(*) FROM saldos WHERE sku LIKE 'LT-%')"
                     " + (SELECT COUNT(*) FROM bodegas WHERE codigo LIKE 'LT-%')",
    "PRODUCTOS": "SELECT (SELECT COUNT(*) FROM productos WHERE sku LIKE 'LT-%')"
                    " + (SELECT COUNT(*) FROM categorias WHERE nombre LIKE 'LT Cat %')",
    "GATEWAY": "SELECT COUNT(*) FROM users WHERE email LIKE 'lt.%'",
}


def datos_conexion(base):
    """Datos de conexión de LT_DB_<BASE>_*, o None si no están todos."""
    claves = ("HOST", "PORT", "USER", "PASSWORD", "NAME")
    valores = {c: os.getenv(f"LT_DB_{base}_{c}", "").strip() for c in claves}
    return valores if all(valores.values()) else None


def sql_directo(base, datos, sentencias):
    import mysql.connector  # solo hace falta en el contenedor

    try:
        conexion = mysql.connector.connect(
            host=datos["HOST"], port=int(datos["PORT"]), user=datos["USER"],
            password=datos["PASSWORD"], database=datos["NAME"], connection_timeout=10)
    except mysql.connector.Error as error:
        sys.exit(f"No se pudo conectar a la base de {base.lower()}: {type(error).__name__}")
    try:
        cursor = conexion.cursor()
        ultimo = None
        for sentencia in sentencias:
            cursor.execute(sentencia)
            if cursor.with_rows:
                ultimo = cursor.fetchall()
        conexion.commit()
        return str(ultimo[-1][0]) if ultimo else ""
    finally:
        conexion.close()


def sql_docker(base, sentencias):
    texto = "START TRANSACTION; " + "; ".join(sentencias) + "; COMMIT;"
    comando = ['sh', '-c', 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" "$MYSQL_DATABASE" -N -e "$1"',
               'sh', texto]
    try:
        r = subprocess.run(["docker", "exec", CONTENEDORES[base], *comando], capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit(f"Faltan las variables LT_DB_{base}_* y no hay Docker para llegar a la base de {base.lower()}.")
    if r.returncode != 0:
        sys.exit(f"Error en la base de {base.lower()}: {r.stderr.strip()[:200]}")
    salida = r.stdout.strip().splitlines()
    return salida[-1] if salida else ""


def sql(base, sentencias):
    """Ejecuta las sentencias en una transacción y devuelve el último valor leído."""
    datos = datos_conexion(base)
    return sql_directo(base, datos, sentencias) if datos else sql_docker(base, sentencias)


def main():
    sql("INVENTARIO", INVENTARIO)
    sql("PRODUCTOS", PRODUCTOS)
    sql("GATEWAY", GATEWAY)
    # La contraseña ya no sirve. En el contenedor .env es un enlace al volumen: se
    # borra el archivo real y el enlace queda listo para la próxima preparación.
    env = (Path(__file__).resolve().parent / ".env").resolve()
    if env.exists():
        env.unlink()
    nombres = {"INVENTARIO": "ms-inventario", "PRODUCTOS": "ms-productos", "GATEWAY": "gateway"}
    for base, consulta in CONTEOS.items():
        print(f"{nombres[base]}: {sql(base, [consulta])} filas de prueba")


if __name__ == "__main__":
    main()
