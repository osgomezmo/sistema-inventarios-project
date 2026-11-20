"""Servidor stub opcional de MS-Proveedores para aislar benchmarks de MS-Compras.

Permite ejecutar las pruebas de escritura (P11, P12, P14) apuntando PROVEEDORES_URL
a este stub local cuando se desea medir MS-Compras + MySQL + RabbitMQ sin levantar
el microservicio real MS-Proveedores.

Uso:
    python mock_proveedores.py --host 0.0.0.0 --port 3001
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re

PATRON_PROVEEDOR = re.compile(r"^/proveedores/(\d+)$")


class ManejadorProveedoresStub(BaseHTTPRequestHandler):
    """Responde GET /proveedores/{id} con un proveedor ACTIVO para IDs 1..1000."""

    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def _enviar_json(self, status: int, payload: dict) -> None:
        cuerpo = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self) -> None:  # noqa: N802
        ruta = self.path.split("?", 1)[0]
        if ruta == "/health":
            self._enviar_json(200, {"status": "ok", "service": "mock-proveedores"})
            return

        coincidencia = PATRON_PROVEEDOR.match(ruta)
        if not coincidencia:
            self._enviar_json(404, {"error": {"codigo": "NO_EXISTE", "mensaje": "Ruta no encontrada"}})
            return

        id_proveedor = int(coincidencia.group(1))
        if 1 <= id_proveedor <= 1000:
            self._enviar_json(
                200,
                {
                    "id_proveedor": id_proveedor,
                    "razon_social": f"Proveedor Stub {id_proveedor} S.A.S.",
                    "nit": f"900000{id_proveedor:03d}-1",
                    "estado": "ACTIVO",
                    "activo": True,
                },
            )
            return

        self._enviar_json(
            404,
            {"error": {"codigo": "NO_EXISTE", "mensaje": f"Proveedor {id_proveedor} no existe"}},
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stub HTTP ligero de MS-Proveedores para pruebas de rendimiento de MS-Compras."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Interfaz de escucha (defecto 127.0.0.1)")
    parser.add_argument("--port", type=int, default=3001, help="Puerto HTTP (defecto 3001)")
    args = parser.parse_args()

    servidor = ThreadingHTTPServer((args.host, args.port), ManejadorProveedoresStub)
    print(f"[mock-proveedores] Escuchando en http://{args.host}:{args.port} (Ctrl+C para detener)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[mock-proveedores] Detenido.")
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
