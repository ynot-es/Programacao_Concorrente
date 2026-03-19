"""
vehicle.py: movimento célula a célula com troca de faixa.

Regras:
  1. SEM MEIA-VOLTA.
  2. Um carro NUNCA abandona o segmento atual. Se bloqueado, espera
     na posição atual até conseguir avançar. Nunca retorna ao cruzamento
     anterior nem escolhe outro destino no meio do caminho.
  3. TROCA DE FAIXA:
     - Ao tentar avançar e a célula-alvo (mesma faixa) estiver ocupada,
       tenta a faixa oposta (non-blocking).
     - Se a oposta também estiver ocupada, espera 1 tick e repete.
     - Ambulância: sempre tenta trocar, independente da velocidade do bloqueador.
     - Outros: só troca se for mais rápido que o bloqueador.
  4. SEMÁFORO:
     - Carros normais: param na penúltima célula e dormem até verde.
     - Ambulância: força verde. Só dorme se AMBAS as faixas de chegada
       do cruzamento estiverem fisicamente ocupadas.
  5. IMPENETRABILIDADE: Lock por célula (pixel arredondado).
     Faixas distintas -> chaves distintas -> andam em paralelo sem colisão.
"""

import threading, random
from config import (
    Dir, CarType, CELL_TICKS, CELLS_PER_SEGMENT, LANES,
    cell_pixel, intersection_pixel,
    C_AMB, C_SLOW, C_MED, C_FAST, C_WHITE, C_YELLOW,
)

SPEED_RANK = {
    CarType.AMBULANCE: 0,
    CarType.FAST:      1,
    CarType.MEDIUM:    2,
    CarType.SLOW:      3,
}


class Car(threading.Thread):
    _id_counter = 0
    _id_lock    = threading.Lock()

    # Mapa global célula -> Carro ocupante (para detectar bloqueador).
    _cell_occupant: dict = {}
    _occupant_lock = threading.Lock()

    def __init__(self, car_type, nodes, adj, lights, cell_locks, clock):
        super().__init__(daemon=True)
        with Car._id_lock:
            Car._id_counter += 1
            self.car_id = Car._id_counter

        self.car_type   = car_type
        self.cell_ticks = CELL_TICKS[car_type.name]
        self._stop      = False

        self._nodes      = nodes
        self._adj        = adj
        self._lights     = lights
        self._cell_locks = cell_locks
        self._clock      = clock

        self.current_node  = random.choice(nodes)
        self.direction     = Dir.RIGHT
        self.lane          = 0

        px, py = intersection_pixel(*self.current_node)
        self.px = float(px)
        self.py = float(py)

        self.waiting       = False
        self.changing_lane = False
        self.distance      = 0

        self._held_lock     = None
        self._held_cell_key = None

    def stop(self):
        self._stop = True

    def _stopped(self):
        return self._stop

    # -- Registro de ocupação -----------------------------------------------
    def _register(self, key):
        with Car._occupant_lock:
            Car._cell_occupant[key] = self

    def _unregister(self, key):
        with Car._occupant_lock:
            if Car._cell_occupant.get(key) is self:
                del Car._cell_occupant[key]

    def _occupant_of(self, cx, cy):
        key = (int(round(cx)), int(round(cy)))
        with Car._occupant_lock:
            return Car._cell_occupant.get(key)

    # -- Helpers de lock ----------------------------------------------------
    def _cell_key(self, cx, cy):
        return (int(round(cx)), int(round(cy)))

    def _try_acquire_nb(self, cx, cy):
        """Non-blocking acquire. Retorna (ok, lock, key)."""
        key = self._cell_key(cx, cy)
        lk  = self._cell_locks.get(key)
        if lk is None:
            return True, None, key
        ok = lk.acquire(blocking=False)
        return ok, lk if ok else None, key

    def _acquire_blocking(self, cx, cy):
        """Blocking acquire (sem timeout: espera para sempre se necessário)."""
        key = self._cell_key(cx, cy)
        lk  = self._cell_locks.get(key)
        if lk is None:
            return None, key
        lk.acquire()
        return lk, key

    def _release_current(self):
        if self._held_lock is not None:
            self._held_lock.release()
            self._held_lock = None
        if self._held_cell_key is not None:
            self._unregister(self._held_cell_key)
            self._held_cell_key = None

    def _commit(self, lk, key, cx, cy):
        """Libera célula anterior, assume posse da nova."""
        self._release_current()
        self._held_lock     = lk
        self._held_cell_key = key
        if key is not None:
            self._register(key)
        self.px = float(cx)
        self.py = float(cy)
        self.distance += 1

    # -- Decisão de ultrapassagem ----------------------------------------------
    def _should_overtake(self, blocker) -> bool:
        if self.car_type == CarType.AMBULANCE:
            return True
        return SPEED_RANK[self.car_type] < SPEED_RANK[blocker.car_type]

    # --- Avança UMA célula (com lógica de faixa) --------------------------------
    def _advance_one(self, n1, n2, step, lane) -> int:
        """
        Tenta mover para a célula `step` na faixa `lane` do segmento n1 para n2.
        Se bloqueado, tenta trocar de faixa ou espera, mas NUNCA desiste.
        Retorna a faixa final em que o carro ficou.
        """
        while not self._stop:
            if step < CELLS_PER_SEGMENT:
                cx, cy = cell_pixel(n1, n2, step, lane)
            else:
                cx, cy = intersection_pixel(*n2)

            ok, lk, key = self._try_acquire_nb(cx, cy)

            if ok:
                # Célula livre: move.
                self.changing_lane = False
                self._commit(lk, key, cx, cy)
                return lane

            # Célula ocupada.
            blocker = self._occupant_of(cx, cy)
            can_overtake = (blocker is not None and
                            self._should_overtake(blocker) and
                            step < CELLS_PER_SEGMENT)   # Não troca no cruzamento

            if can_overtake:
                other = 1 - lane
                other_cx, other_cy = cell_pixel(n1, n2, step, other)
                ok2, lk2, key2 = self._try_acquire_nb(other_cx, other_cy)
                if ok2:
                    # Faixa oposta livre: troca!
                    self.changing_lane = True
                    self._commit(lk2, key2, other_cx, other_cy)
                    return other
                # Faixa oposta também ocupada: aguarda 1 tick e retenta.
                self.changing_lane = False
                self._clock.wait_tick()
                # Após esperar, retenta na faixa atual primeiro,
                # Depois na oposta (loop vai recalcular).
            else:
                # Sem ultrapassagem: aguarda 1 tick e retenta.
                self.changing_lane = False
                self._clock.wait_tick()

        return lane   # Encerramento forçado

    # -- Semáforo (penúltima célula) --------------------------------------------------
    def _wait_signal(self, next_n, direction, n1, n2):
        """
        Para carros normais: dorme até verde.
        Para ambulância: força verde. Dorme apenas se ambas as faixas.
        de chegada estiverem ocupadas (verifica sem bloquear).
        """
        if self.car_type == CarType.AMBULANCE:
            self._lights[next_n].force_green(direction)
            # Verifica se ao menos uma faixa de chegada está livre.
            approach = CELLS_PER_SEGMENT - 1
            while not self._stop:
                if not self._lights[next_n].is_green_for(direction):
                    self._lights[next_n].force_green(direction)
                both_blocked = True
                for lane_check in range(LANES):
                    cx, cy = cell_pixel(n1, n2, approach, lane_check)
                    ok, lk, _ = self._try_acquire_nb(cx, cy)
                    if ok:
                        if lk is not None:
                            lk.release()
                        both_blocked = False
                        break
                if not both_blocked:
                    return   # Ao menos uma faixa livre: pode ir.
                # Ambas ocupadas: dorme 1 tick e reavalia.
                self._clock.wait_tick()
        else:
            if not self._lights[next_n].is_green_for(direction):
                self.waiting = True
                self._lights[next_n].wait_green(direction, self._stopped)
                self.waiting = False

    # --- Percurso completo de um segmento ---------------------------------------
    def _traverse_segment(self, next_n, direction, start_lane):
        """
            Percorre todas as células do segmento nó_atual -> Prox_nó.
            Nunca abandona: fica no loop até completar ou ser parado.
        """
        n1, n2 = self.current_node, next_n
        lane   = start_lane

        for step in range(1, CELLS_PER_SEGMENT + 1):
            if self._stop:
                self._release_current()
                return

            # -- Espera os ticks de velocidade ---------------------------------
            for _ in range(self.cell_ticks):
                self._clock.wait_tick()
                if self._stop:
                    self._release_current()
                    return

            # --- Semáforo: verifica na penúltima célula ------------------------
            if step == CELLS_PER_SEGMENT - 1:
                self._wait_signal(next_n, direction, n1, n2)
                if self._stop:
                    self._release_current()
                    return

            # --- Avança a célula (nunca desiste) --------------------------------
            lane = self._advance_one(n1, n2, step, lane)

        # Chegou no cruzamento. Atualiza estado e segue para o próximo.
        self.current_node = next_n
        self.direction    = direction
        self.lane         = lane
        self._release_current()

    # --- Laço Principal ---------------------------------------------------------
    def run(self):
        self._held_lock     = None
        self._held_cell_key = None
        self._clock.wait_start()

        while not self._stop:
            opts = self._adj.get(self.current_node, [])
            if not opts:
                self._clock.wait_tick()
                continue
            next_n, direction = random.choice(opts)
            lane = random.randint(0, LANES - 1)
            self._traverse_segment(next_n, direction, lane)

    #--- Visuais ----------------------------------------------------------------
    @property
    def color(self):
        return {CarType.AMBULANCE: C_AMB,
                CarType.SLOW:      C_SLOW,
                CarType.MEDIUM:    C_MED,
                CarType.FAST:      C_FAST}[self.car_type]

    @property
    def label(self):
        return "A" if self.car_type == CarType.AMBULANCE else str(self.car_id)
