"""
clock.py:Relógio Global, é uma thread separada).
"""
import threading, time
from config import TICK_S

class GlobalClock(threading.Thread):
    
    def __init__(self):
        super().__init__(daemon=True, name="GlobalClock")
        self._cond       = threading.Condition()
        self._tick_n     = 0
        self._started    = threading.Event()
        self._stop_flag  = False
        self.total_ticks = 0
        self._lights_ref = None

    # -- Interface para o semáforo acessar o relógio --------------------------------
    def set_lights(self, lights: dict):
        self._lights_ref = lights

    # -- Interface para as threads de carro sincronizarem com o relógio ----------------
    def wait_start(self):
        self._started.wait()

    # Carros chamam essa função para esperar o próximo tick do relógio.
    def wait_tick(self):
        n = self._tick_n
        with self._cond:
            while self._tick_n == n and not self._stop_flag:
                self._cond.wait(timeout=0.3)

    # -- Loop principal do relógio ------------------------------------------------------
    def run(self):
        self._started.set()
        while not self._stop_flag:
            time.sleep(TICK_S)
            if self._lights_ref:
                for lt in self._lights_ref.values(): 
                    lt.tick()
            with self._cond:
                self._tick_n    += 1
                self.total_ticks += 1
                self._cond.notify_all() # Acorda os carros esperando o próximo tick.
    
    # -- Parar o relógio (para encerrar a simulação) --------------------------------------
    def stop(self):
        self._stop_flag = True
        with self._cond:
            self._cond.notify_all()
