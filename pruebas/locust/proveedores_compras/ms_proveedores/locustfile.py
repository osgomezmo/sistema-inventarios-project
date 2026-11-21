"""Punto de entrada unificado de la suite de rendimiento para MS-Proveedores (P01..P07).

Permite ejecutar cualquier escenario por etiqueta (--tags p01 .. --tags p07) o seleccionar
clases individuales desde la interfaz web de Locust (--class-picker).

Nota sobre estres (P05 y P06):
- Este archivo importa unicamente las clases HttpUser para no imponer un LoadTestShape
  global sobre las pruebas de carga (P01..P04) y capacidad (P07).
- Para ejecutar P05 o P06 con su rampa escalonada LoadTestShape y corte automatico al 5%
  de errores, invoque directamente `p05_estres_lectura.py` o
  `p06_estres_escritura.py` (o use `./ejecutar.sh P05` / `python ejecutar.py P05`).
"""

from __future__ import annotations

import sys
from pathlib import Path

_DIR_ACTUAL = str(Path(__file__).resolve().parent)
if _DIR_ACTUAL not in sys.path:
    sys.path.insert(0, _DIR_ACTUAL)

from p01_carga_lectura import UsuarioP01CargaLectura
from p02_carga_mixta import UsuarioP02CargaMixta
from p03_carga_ciclo_vida import UsuarioP03CicloVidaContactos
from p04_carga_productos import UsuarioP04ProductosSuministrados
from p05_estres_lectura import UsuarioP05EstresBusquedas
from p06_estres_escritura import UsuarioP06EstresEscrituras
from p07_capacidad_soak import UsuarioP07CapacidadSoak

__all__ = [
    "UsuarioP01CargaLectura",
    "UsuarioP02CargaMixta",
    "UsuarioP03CicloVidaContactos",
    "UsuarioP04ProductosSuministrados",
    "UsuarioP05EstresBusquedas",
    "UsuarioP06EstresEscrituras",
    "UsuarioP07CapacidadSoak",
]
