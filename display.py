"""
display.py - (Modulei o display) É a parte de Renderização do mapa, vias, semáforos e carros usando Pygame.

Todas as vias são mão única com 2 faixas. O desenho mostra:
  - Via: retângulo com largura ROAD_W (2 faixas);
  - Linha divisória tracejada entre as 2 faixas;
  - Setas de sentido repetidas ao longo do segmento;
  - Semáforo com dois LEDs (H verde/vermelho e V verde/vermelho), optamos por não colocar o amarelo para simplificar a lógica de controle;
  - Barra de progresso de fase;
  - Carros na posição exata da sua célula/faixa.
"""

import pygame, time

from config import (
    WIN_W, WIN_H, MAP_W, PANEL_W,
    CELLS_PER_SEGMENT, LANES, LANE_W, ROAD_W, SEG_PX,
    CAR_W, CAR_H,
    Dir, CarType,
    C_BG, C_ASPHALT, C_ROAD, C_LANE_DIV, C_LANE_EDGE,
    C_SIDEWALK, C_ARROW,
    C_GREEN, C_RED, C_YELLOW,
    C_AMB, C_SLOW, C_MED, C_FAST,
    C_PANEL_BG, C_TEXT, C_ACCENT, C_WHITE, C_DIM,
    intersection_pixel,
)

CROSS_R = ROAD_W // 2 + 2   # Meia-largura da caixa de cruzamento.


class Renderer:
    def __init__(self, surface, edges, nodes, lights):
        self.surf    = surface
        self.edges   = edges    # [(n1, n2, Dir), ...]
        self.nodes   = nodes
        self.lights  = lights
        self.start_t = time.time()

        self.font_s  = pygame.font.SysFont("monospace", 10, bold=True)
        self.font_m  = pygame.font.SysFont("monospace", 12, bold=True)
        self.font_l  = pygame.font.SysFont("monospace", 15, bold=True)
        self.font_xl = pygame.font.SysFont("monospace", 19, bold=True)

    # -- Fundo ------------------------------------------------------
    def draw_background(self):
        pygame.draw.rect(self.surf, C_ASPHALT, (0, 0, MAP_W, WIN_H))

    # -- Vias -----------------------------------------------------------
    def draw_roads(self):
        for (n1, n2, direction) in self.edges:
            p1 = intersection_pixel(*n1)
            p2 = intersection_pixel(*n2)
            is_h = (n1[1] == n2[1])
            self._draw_segment(p1, p2, is_h, direction)

    def _draw_segment(self, p1, p2, is_h, direction):
        rw = ROAD_W   # 28 px

        if is_h:
            x1, x2 = min(p1[0], p2[0]), max(p1[0], p2[0])
            y  = p1[1]
            # Asfalto [janela, cor RGB, os pontos]
            pygame.draw.rect(self.surf, C_ROAD, (x1, y - rw//2, x2-x1, rw))
            # Bordas externas. [janela, cor, ponto inicial, ponto final, espessura].
            pygame.draw.line(self.surf, C_LANE_EDGE, (x1, y-rw//2), (x2, y-rw//2), 2)
            pygame.draw.line(self.surf, C_LANE_EDGE, (x1, y+rw//2), (x2, y+rw//2), 2)
            # Divisória de faixas, que é o tracejado central.
            self._dash_h(x1+4, x2-4, y, C_LANE_DIV)
            # Setas de sentido (3 ao longo do segmento), para ficar claro as direções possíveis de mão única.
            for frac in [0.25, 0.50, 0.75]:
                mx = int(x1 + (x2-x1)*frac)
                self._arrow_h(mx, y, direction)
        else:
            x  = p1[0]
            y1, y2 = min(p1[1], p2[1]), max(p1[1], p2[1])
            pygame.draw.rect(self.surf, C_ROAD, (x - rw//2, y1, rw, y2-y1))
            pygame.draw.line(self.surf, C_LANE_EDGE, (x-rw//2, y1), (x-rw//2, y2), 2)
            pygame.draw.line(self.surf, C_LANE_EDGE, (x+rw//2, y1), (x+rw//2, y2), 2)
            self._dash_v(y1+4, y2-4, x, C_LANE_DIV)
            for frac in [0.25, 0.50, 0.75]:
                my = int(y1 + (y2-y1)*frac)
                self._arrow_v(x, my, direction)

    # -- Cruzamentos / semáforos ------------------------------------------------------
    def draw_intersections(self):
        cr = CROSS_R
        for node, lt in self.lights.items():
            px, py = intersection_pixel(*node)

            #-- Caixa de asfalto --------------------------------------------------------
            pygame.draw.rect(self.surf, C_ROAD,
                             (px-cr, py-cr, 2*cr, 2*cr))
            pygame.draw.rect(self.surf, C_LANE_EDGE,
                             (px-cr, py-cr, 2*cr, 2*cr), 1)

            # -- Semáforo -----------------------------------------------------------
            sx, sy = px - cr - 20, py - cr + 2
            # Carcaça.
            pygame.draw.rect(self.surf, (20, 20, 26),
                             (sx, sy, 14, 32), border_radius=4)
            # LED horizontal (topo).
            pygame.draw.circle(self.surf, lt.color_h, (sx+7, sy+8),  5)
            # LED vertical (baixo).
            pygame.draw.circle(self.surf, lt.color_v, (sx+7, sy+24), 5)
            # Brilho
            for (cy_off, c) in [(sy+8, lt.color_h), (sy+24, lt.color_v)]:
                bc = tuple(min(v+70, 255) for v in c)
                pygame.draw.circle(self.surf, bc, (sx+5, cy_off-2), 2)

            # Barra de fase.
            bw = int(14 * lt.phase_fraction)
            pygame.draw.rect(self.surf, (35,35,45), (sx, sy+34, 14, 3))
            pygame.draw.rect(self.surf, C_YELLOW,   (sx, sy+34, bw,  3))

            # Label coordenada.
            lbl = self.font_s.render(f"{node[0]},{node[1]}", True, (75, 80, 98))
            self.surf.blit(lbl, (px + cr + 3, py - 6))

    # -- Carros --------------------------------------------------------------- (Por Enquanto são simples retângulos)
    def draw_cars(self, cars):
        for car in cars:
            cx = int(round(car.px))
            cy = int(round(car.py))
            col = car.color

            # Sombra.
            pygame.draw.rect(self.surf, (5, 5, 8),
                             (cx-CAR_W//2+2, cy-CAR_H//2+2, CAR_W, CAR_H),
                             border_radius=3)
            # Corpo.
            pygame.draw.rect(self.surf, col,
                             (cx-CAR_W//2, cy-CAR_H//2, CAR_W, CAR_H),
                             border_radius=3)

            # Borda amarela pulsante = Trocando de faixa agora. Simular a seta de mudança de faixa que o motorista liga, 
            # para indicar a intenção de mudar de faixa. A borda aparece apenas durante o processo de troca de faixa, ou seja,
            # quando o carro já iniciou a manobra mas ainda não chegou na nova célula/faixa.
            if getattr(car, 'changing_lane', False):
                pulse = int(time.time() * 10) % 2 == 0
                bc    = C_YELLOW if pulse else (200, 160, 0)
                pygame.draw.rect(self.surf, bc,
                                 (cx-CAR_W//2-1, cy-CAR_H//2-1,
                                  CAR_W+2, CAR_H+2), 2, border_radius=3)

            wc = tuple(min(v+55, 255) for v in col)
            pygame.draw.rect(self.surf, wc,
                             (cx-CAR_W//2+1, cy-CAR_H//2+2, CAR_W-2, 4),
                             border_radius=1)

            # Giroflex para diferenciar ambulância (dois LEDs piscantes alternados).
            if car.car_type == CarType.AMBULANCE:
                b  = int(time.time() * 6) % 2 == 0
                c1 = C_WHITE     if b else C_YELLOW
                c2 = (50,80,255) if b else C_WHITE
                pygame.draw.circle(self.surf, c1, (cx-2, cy-CAR_H//2-2), 3)
                pygame.draw.circle(self.surf, c2, (cx+2, cy-CAR_H//2-2), 3)

            # Ponto vermelho no carro = aguardando semáforo.
            if car.waiting:
                pygame.draw.circle(self.surf, C_RED,
                                   (cx+CAR_W//2+3, cy-CAR_H//2), 3)

            # Label para identificar o carro (opcional, pode ser o número do carro ou outro identificador). Centralizado no carro.
            lbl = self.font_s.render(car.label, True, C_WHITE)
            self.surf.blit(lbl, (cx - lbl.get_width()//2,
                                  cy - lbl.get_height()//2 + 1))

    # -- Painel Lateral com Informações -------------------------------------------------------------
    def draw_panel(self, cars, total_ticks, fps):
        x0 = MAP_W
        pygame.draw.rect(self.surf, C_PANEL_BG, (x0, 0, PANEL_W, WIN_H))
        pygame.draw.line(self.surf, C_ACCENT, (x0,0),(x0,WIN_H), 2)
        y = 14

        self._ct("SIMULADOR DE TRÁFEGO", self.font_xl, C_ACCENT, x0, y); y+=26
        self._hl(x0, y); y+=10

        elapsed = int(time.time() - self.start_t)
        for label, val in [
            ("Tempo",  f"{elapsed//60:02d}:{elapsed%60:02d}"),
            ("Ticks",  str(total_ticks)),
            ("Cruzes", str(len(self.nodes))),
            ("FPS",    f"{fps:.0f}"),
        ]:
            self._row(label, val, x0, y); y+=19
        self._hl(x0, y); y+=10

        self._ct("VIAS", self.font_m, C_ACCENT, x0, y); y+=15
        info = [
            "Todas mão única (-> setas)",
            "2 faixas lado a lado",
        ]
        for s in info:
            t = self.font_s.render(s, True, C_DIM)
            self.surf.blit(t, (x0+10, y)); y+=14
        self._hl(x0, y); y+=10

        self._ct("VEÍCULOS", self.font_m, C_ACCENT, x0, y); y+=15
        for col, name in [
            (C_AMB,  "Ambulância  V=2"),
            (C_FAST, "Rápido      V=2"),
            (C_MED,  "Médio       V=1"),
            (C_SLOW, "Lento      V=0.5"),
        ]:
            pygame.draw.rect(self.surf, col, (x0+10, y+1, 12, 12), border_radius=2)
            t = self.font_s.render(name, True, C_TEXT)
            self.surf.blit(t, (x0+26, y)); y+=15
        self._hl(x0, y); y+=10

        self._ct("STATUS", self.font_m, C_ACCENT, x0, y); y+=15
        for car in sorted(cars, key=lambda c: c.car_id):
            if y > WIN_H - 44: break
            st = "Pausado" if car.waiting else "Continuar"
            nd = car.current_node
            ln = f"{st} #{car.car_id:02d} ({nd[0]},{nd[1]}) d={car.distance}"
            pygame.draw.rect(self.surf, car.color, (x0+6,y+1,6,12), border_radius=1)
            t = self.font_s.render(ln, True, C_TEXT)
            self.surf.blit(t, (x0+16, y)); y+=14

        y = WIN_H - 46
        self._hl(x0, y); y+=1
        for note in ["vermelho = aguardando sinal",
                     "borda = trocando de faixa",
                     "barra = fase semáforo"]:
            t = self.font_s.render(note, True, (100,105,120))
            self.surf.blit(t, (x0+8, y)); y+=13

    # -- Aqui são funções auxiliares para desenhar elementos específicos, como linhas tracejadas, setas, etc. -----------

    # Desenhar linha horizontal tracejada (usada para divisória de faixas).
    def _dash_h(self, x1, x2, y, col, d=8, g=6):
        x, on = x1, True
        while x < x2:
            e = min(x + (d if on else g), x2)
            if on: pygame.draw.line(self.surf, col, (x,y),(e,y), 1)
            x=e; on=not on

    # Desenhar linha vertical tracejada (usada para divisória de faixas).
    def _dash_v(self, y1, y2, x, col, d=8, g=6):
        y, on = y1, True
        while y < y2:
            e = min(y + (d if on else g), y2)
            if on: pygame.draw.line(self.surf, col, (x,y),(x,e), 1)
            y=e; on=not on

    # Desenhar seta horizontal (usada para indicar direção de movimento).
    def _arrow_h(self, cx, cy, direction):
        pts = ([(cx-7,cy-4),(cx+7,cy),(cx-7,cy+4)]
               if direction == Dir.RIGHT else
               [(cx+7,cy-4),(cx-7,cy),(cx+7,cy+4)])
        pygame.draw.polygon(self.surf, C_ARROW, pts)

    # Desenhar seta vertical (usada para indicar direção de movimento).
    def _arrow_v(self, cx, cy, direction):
        pts = ([(cx-4,cy-7),(cx,cy+7),(cx+4,cy-7)]
               if direction == Dir.DOWN else
               [(cx-4,cy+7),(cx,cy-7),(cx+4,cy+7)])
        pygame.draw.polygon(self.surf, C_ARROW, pts)

    # Desenhar linha horizontal de destaque (usada para separar seções no painel lateral).
    def _hl(self, x0, y):
        pygame.draw.line(self.surf, C_ACCENT, (x0+6,y),(x0+PANEL_W-6,y), 1)

    # Desenhar texto centralizado horizontalmente no painel lateral.
    def _ct(self, text, font, color, x0, y):
        s = font.render(text, True, color)
        self.surf.blit(s, (x0 + (PANEL_W - s.get_width())//2, y))

    # Desenhar uma linha de informação no painel lateral, com label à esquerda e valor à direita.
    def _row(self, label, val, x0, y):
        l = self.font_m.render(f"{label}:", True, C_TEXT)
        v = self.font_m.render(val,         True, C_WHITE)
        self.surf.blit(l, (x0+10, y))
        self.surf.blit(v, (x0 + PANEL_W - v.get_width() - 10, y))
