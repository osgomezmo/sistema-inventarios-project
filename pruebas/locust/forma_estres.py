"""Forma del escenario de estrés (E): de 20 a 200 usuarios, sumando 20 cada 30 s.

Se detiene al terminar el escalón de 200 usuarios o en cuanto los errores
superan el 5 %. ejecutar.sh la carga junto con bloque_b.py solo en el escenario E.
"""

from locust import LoadTestShape

PASO_USUARIOS = 20
PASO_SEGUNDOS = 30
MAXIMO = 200
LIMITE_ERRORES = 0.05


class FormaEstres(LoadTestShape):
    def tick(self):
        tiempo = self.get_run_time()
        if self.runner.stats.total.fail_ratio > LIMITE_ERRORES:
            return None  # punto de quiebre: más de 5 % de errores
        escalon = int(tiempo // PASO_SEGUNDOS) + 1
        usuarios = escalon * PASO_USUARIOS
        if usuarios > MAXIMO:
            return None  # ya se sostuvo el escalón de 200 durante 30 s
        return usuarios, PASO_USUARIOS
