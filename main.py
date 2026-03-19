"""
main.py (precisa dos outros módulos) - Ponto de entrada do Simulador de Tráfego.

Para rodar:
    - Instale o pygame: pip install pygame.
    - Execute: python main.py.
"""

import pygame
from config    import WIN_W, WIN_H, CarType, build_grid, build_adjacency
from clock     import GlobalClock
from semaphore import build_lights, build_cell_locks
from vehicle   import Car
from display   import Renderer

SPAWN = [
    (CarType.AMBULANCE, 2),
    (CarType.FAST,      4),
    (CarType.MEDIUM,    4),
    (CarType.SLOW,      4),
]
 
def main():
    # Malha dirigida.
    nodes, edges = build_grid()
    adj          = build_adjacency(edges)

    # Semáforos e locks de célula.
    lights     = build_lights(nodes)
    cell_locks = build_cell_locks(nodes, edges)

    # Relógio global.
    clock = GlobalClock()
    clock.set_lights(lights)
    clock.start()

    # Instanciando os veículos.
    cars = []
    for car_type, n in SPAWN:
        for _ in range(n):
            cars.append(Car(car_type, nodes, adj, lights, cell_locks, clock))
    for car in cars:
        car.start()

    # Iniciando o Pygame.
    pygame.init()
    screen   = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Simulador de Tráfego — CC0021 UFCA")
    pg_clock = pygame.time.Clock()
    renderer = Renderer(screen, edges, nodes, lights)

    # Laço principal de renderização e eventos.
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False

        screen.fill((13, 15, 20))
        renderer.draw_background()
        renderer.draw_roads()
        renderer.draw_intersections()
        renderer.draw_cars(cars)
        renderer.draw_panel(cars, clock.total_ticks, pg_clock.get_fps())

        pygame.display.flip()
        pg_clock.tick(60)

    # Encerramento.
    clock.stop()
    for car in cars: car.stop()
    pygame.quit()

if __name__ == "__main__":
    main()
