"""
semaphore.py: Semáforos e travas de células.
  - Ambulância só fica parada no sinal se ambas as
    faixas de chegada estiverem ocupadas por carros normais.
  - Se pelo menos uma faixa estiver livre, ela força verde e passa.
  - Lock por (célula, faixa).
"""
import threading, random
from config import Dir, GREEN_DUR, C_GREEN, C_RED, C_YELLOW, LANES

# --- Semáforo de cruzamento ----------------------------------------------
class TrafficLight:
    # Cada semáforo controla um nó do grafo, ou seja, um cruzamento.
    def __init__(self, node):
        self.node      = node
        self.green_h   = random.choice([True, False])
        self.timer     = random.randint(0, GREEN_DUR - 1)
        self.GREEN_DUR = GREEN_DUR
        self._lock     = threading.Lock()
        self.cond      = threading.Condition(self._lock)

    def tick(self):
        with self._lock:
            self.timer += 1
            if self.timer >= self.GREEN_DUR:
                self.timer   = 0
                self.green_h = not self.green_h
                self.cond.notify_all()

    def force_green(self, direction: Dir):
        #Força verde imediato para a direção pedida (ambulância).
        with self._lock:
            want_h = direction in (Dir.LEFT, Dir.RIGHT)
            if self.green_h != want_h:
                self.green_h = want_h
                self.timer   = 0
                self.cond.notify_all()

    def is_green_for(self, direction: Dir) -> bool:
        return self.green_h == (direction in (Dir.LEFT, Dir.RIGHT))

    def wait_green(self, direction: Dir, stop_flag):
        # Carro normal DORME até o sinal abrir.
        with self.cond:
            while not self.is_green_for(direction) and not stop_flag():
                self.cond.wait(timeout=0.4)

    def wait_green_ambulance(self, direction: Dir, stop_flag,
                             cell_locks: dict, n1, n2):
        """
        Ambulância:
          - Sempre força o sinal verde para a sua direção.
          - Só aguarda se AMBAS as faixas da célula de entrada do cruzamento
            (step = CELLS_PER_SEGMENT - 1) estiverem ocupadas.
          - Se ao menos uma faixa estiver livre, passa imediatamente.
        """
        from config import cell_pixel, CELLS_PER_SEGMENT
        self.force_green(direction)

        with self.cond:
            while not stop_flag():
                if not self.is_green_for(direction):
                    self.force_green(direction)

                # Verifica se ao menos uma faixa da última célula está livre.
                approach_step = CELLS_PER_SEGMENT - 1
                any_lane_free = False
                for lane in range(LANES):
                    cx, cy = cell_pixel(n1, n2, approach_step, lane)
                    key = (int(round(cx)), int(round(cy)))
                    lk  = cell_locks.get(key)
                    if lk is None:
                        any_lane_free = True
                        break
                    # Tenta acquire sem bloquear.
                    got = lk.acquire(blocking=False)
                    if got:
                        lk.release()
                        any_lane_free = True
                        break

                if any_lane_free:
                    return   # Pode passar.
                # Ambas as faixas ocupadas: dorme 1 tick e reavalia.
                self.cond.wait(timeout=0.1)

    @property
    def color_h(self): return C_GREEN if self.green_h else C_RED
    @property
    def color_v(self): return C_RED   if self.green_h else C_GREEN
    @property
    def phase_fraction(self): return self.timer / max(self.GREEN_DUR, 1)

# --- Construção dos semáforos ------------------------------------------------------
def build_lights(nodes) -> dict:
    return {n: TrafficLight(n) for n in nodes}


# -- Travas de célula -----------------------------------------------------------
def build_cell_locks(nodes, edges) -> dict:
    """
    Lock por (célula, faixa). Chave = pixel central inteiro arredondado.
    Células de faixas distintas têm chaves distintas -> carros lado a lado
    não se bloqueiam mutuamente.
    """
    from config import cell_pixel, CELLS_PER_SEGMENT, intersection_pixel
    locks = {}

    # Registra a trava para a célula da faixa, se ainda não existir.
    def reg(cx, cy):
        k = (int(round(cx)), int(round(cy)))
        if k not in locks:
            locks[k] = threading.Lock()

    # Para cada segmento, registra as travas das células de faixa.
    for (n1, n2, _dir) in edges:
        for step in range(1, CELLS_PER_SEGMENT):
            for lane in range(LANES):
                cx, cy = cell_pixel(n1, n2, step, lane)
                reg(cx, cy)

    for node in nodes:
        px, py = intersection_pixel(*node)
        reg(px, py)

    return locks
