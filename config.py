"""
config.py - define Constantes, cores, enums e malha viária

Modelo de vias:
  - TODAS as vias são mão única com LANES=2 faixas lado a lado.
  - O grafo de cruzamentos é DIRIGIDO: cada aresta tem uma direção fixa.
  - Carros NÃO podem dar meia-volta (não existe aresta de volta).
  - Entre dois cruzamentos há CELLS_PER_SEGMENT=20 células (para simular o movimento).
  - Carros andam célula a célula; velocidade = 1 célula a cada N ticks.
  - Dois carros na mesma célula é proibido (lock por célula).
  - Dois carros em faixas diferentes do mesmo segmento convivem OK.

Topologia (5×4 = 20 cruzamentos):
  Linhas pares  (r=0,2): (esquerda para direita).
  Linhas ímpares(r=1,3): (direita para esquerda).
  Colunas pares (c=0,2,4): (cima para baixo).
  Colunas ímpares(c=1,3):  (baixo para cima).
  -> Forma um padrão de circulação tipo "serpentina", sem becos sem saída.
"""

from enum import Enum

# -- Janela ----------------------------------------------------------------
WIN_W   = 1440
WIN_H   = 900
PANEL_W = 240
MAP_W   = WIN_W - PANEL_W   # 1200

# --- Malha de cruzamentos ------------------------------------------------------
COLS = 5  
ROWS = 4   
# Total: 5×4 = 20 cruzamentos

# --- Células e espaçamento ------------------------------------------------------
CELLS_PER_SEGMENT = 20   # Células entre dois cruzamentos consecutivos.
LANES             = 2    # Faixas por via (mão única, lado a lado).
LANE_W            = 14   # Pixels por faixa.
ROAD_W            = LANE_W * LANES  # 28 px: largura total da via.
SEG_PX            = CELLS_PER_SEGMENT * LANE_W  # 280 px a distância entre cruzamentos.

# Margens (centralizadas na tela)
MARGIN_X = (MAP_W - (COLS - 1) * SEG_PX) // 2   # (1200 - 4*280)/2 = 40
MARGIN_Y = (WIN_H - (ROWS - 1) * SEG_PX) // 2   # (900  - 3*280)/2 = 30

# --- Tempo ----------------------------------------------------------------
TICK_S    = 0.08   # Segundos por tick do relógio global.
GREEN_DUR = 90     # Ticks que o semáforo fica verde.

# Ticks para mover UMA célula.
CELL_TICKS = {
    "FAST"      : 1,
    "MEDIUM"    : 2,
    "SLOW"      : 4,
    "AMBULANCE" : 1,
}

# -- Visual do carro -----------------------------------------------------------
CAR_W = LANE_W - 4   # 10 px 
CAR_H = LANE_W + 2   # 16 px

# --- Cores ----------------------------------------------------------------------
C_BG        = (13,  15,  20)
C_ASPHALT   = (28,  30,  40)
C_ROAD      = (48,  52,  64)
C_LANE_DIV  = (60,  65,  80)   # divisória entre faixas (linha tracejada)
C_LANE_EDGE = (20,  22,  30)   # borda exterior da via
C_SIDEWALK  = (38,  40,  50)
C_ARROW     = (160, 150, 100)  # setas de sentido na via
C_GREEN     = ( 40, 210,  80)
C_RED       = (220,  45,  55)
C_YELLOW    = (240, 200,  20)
C_AMB       = (255,  55,  55)
C_SLOW      = ( 60, 120, 215)
C_MED       = ( 55, 185, 105)
C_FAST      = (235, 150,  25)
C_PANEL_BG  = (18,  20,  28)
C_TEXT      = (190, 200, 220)
C_ACCENT    = ( 80, 150, 255)
C_WHITE     = (255, 255, 255)
C_DIM       = (80,  85, 100)

# --- Enums úteis ------------------------------------------------------------------------
class Dir(Enum):
    UP    = ( 0, -1)
    DOWN  = ( 0,  1)
    LEFT  = (-1,  0)
    RIGHT = ( 1,  0)

class CarType(Enum):
    SLOW      = "Lento"
    MEDIUM    = "Médio"
    FAST      = "Rápido"
    AMBULANCE = "Ambulância"

# --- Pixel central do cruzamento ---------------------------------------------------
def intersection_pixel(col: int, row: int) -> tuple[int, int]:
    return (MARGIN_X + col * SEG_PX,
            MARGIN_Y + row * SEG_PX)

# --- Pixel central de uma célula no segmento entre n1 e n2 ------------------------------------------------
def cell_pixel(n1: tuple, n2: tuple, step: int, lane: int) -> tuple[float, float]:
    """
    Retorna o pixel (cx, cy) do centro da célula `step`,
    na faixa `lane` (0 ou 1), do segmento dirigido n1 até n2.

    Convenção de faixa (vista de quem vai de n1 à n2):
      lane 0 vai para faixa da ESQUERDA  (mais próxima do eixo da via).
      lane 1 vai para faixa da DIREITA   (mais afastada).

    Espaçamento lateral em relação ao eixo do segmento:
      -(LANE_W/2)  para lane 0   (esquerda relativa)
      +(LANE_W/2)  para lane 1   (direita relativa)
    """
    p1x, p1y = intersection_pixel(*n1)
    p2x, p2y = intersection_pixel(*n2)
    t  = step / CELLS_PER_SEGMENT
    ax = p1x + (p2x - p1x) * t   # Ponto no eixo do segmento
    ay = p1y + (p2y - p1y) * t

    # Direção do segmento.
    dx, dy = n2[0] - n1[0], n2[1] - n1[1]
    # vetor perpendicular para a direita do movimento.
    # rotação +90°: (dx,dy) -> (dy, -dx)
    px_dir, py_dir = float(dy), float(-dx)

    # lane 0: meio-LANE_W para a esquerda (−), lane 1: para a direita (+).
    sign  = -1.0 if lane == 0 else 1.0
    off   = sign * LANE_W / 2.0

    return (ax + px_dir * off, ay + py_dir * off)

# ── Construção do grafo dirigido ────────────────────────────────────────────
def build_grid():
    """
    Retorna (nós, arestas dirigidas).

    arestas dirigidas: lista de (n1, n2, Dir)
      — Cada entrada é uma aresta UNI-DIRECIONAL de n1 para n2.
      — NÃO existe aresta de volta (sem mão dupla).

    Padrão de direções (elimina becos sem saída):
      Segmentos horizontais:
        linha par  (r%2==0): sempre ->  (c, r) -> (c+1, r).
        linha ímpar (r%2==1): sempre <-  (c+1,r) → (c, r).
      Segmentos verticais:
        coluna par  (c%2==0): sempre baixo  (c,r) → (c,r+1)
        coluna ímpar(c%2==1): sempre cima  (c,r+1) → (c,r)

    Este padrão garante que todo nó tem pelo menos 1 saída e 1 entrada,
    formando circuitos fechados.
    """
    nodes = [(c, r) for r in range(ROWS) for c in range(COLS)]

    edges = []

    # Horizontais.
    for r in range(ROWS):
        for c in range(COLS - 1):
            if r % 2 == 0:
                edges.append(((c,r), (c+1,r), Dir.RIGHT))
            else:
                edges.append(((c+1,r), (c,r), Dir.LEFT))

    # Verticais.
    # Regra: colunas ímpares (1,3) direita-cima (UP); colunas pares (2,4) direita-baixo (DOWN)
    # Coluna 0 direita-cima (UP) para evitar beco sem saída no canto (0,3).
    # Mapa de sentido por coluna:
    #   c=0: UP, c=1: UP, c=2: DOWN, c=3: UP, c=4: DOWN.
    col_dir = {0: 'up', 1: 'up', 2: 'down', 3: 'up', 4: 'down'}
    for c in range(COLS):
        for r in range(ROWS - 1):
            if col_dir[c] == 'down':
                edges.append(((c, r),   (c, r+1), Dir.DOWN))
            else:
                edges.append(((c, r+1), (c, r),   Dir.UP))

    return nodes, edges


def build_adjacency(edges):
    """
    Retorna dict: nó -> [(prox_nó, Dir)]
    Baseado nas arestas dirigidas, ou seja, não tem volta.
    """
    adj = {}
    for (n1, n2, d) in edges:
        adj.setdefault(n1, []).append((n2, d))
    return adj
