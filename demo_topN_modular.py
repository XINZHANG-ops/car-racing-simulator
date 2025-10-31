import math
import sys
import pickle
from typing import List

import neat
import pygame

# ===================== 与训练保持一致的参数 =====================
from env_settings import (
    MAP,
    CAR_IMAGE,
    FPS,
    MAX_SIM_SECONDS,
    WHEELBASE_PX,
    MAX_STEER_DEG,
    V_MIN, 
    V_MAX,
    SPEED_NORM,
    ACCEL_PER_STEP,
    V_TURN_FLOOR,
    TURN_EXP,
    BRAKE_PER_STEP,
    LIMIT_SMOOTH_ALPHA,
    ALPHA_STEER,
    TEXT_COLOR,
    START_POSITION,
    STARTING_ANGLE,
    WIDTH, 
    HEIGHT,
    CAR_SIZE_X, 
    CAR_SIZE_Y,
    BORDER_COLOR,
    RADAR_MAX_LEN,
    INPUT_NORMALIZATION_DENOMINATOR,
    PLOT_RADAR,
)

from src.my_env import (
    Car,
    Track
)


# ============ 工具：从文件加载基因组 ============
def load_topN_genomes(topn_path: str, winner_path: str) -> List[neat.genome.DefaultGenome]:
    try:
        with open(topn_path, "rb") as f:
            topN = pickle.load(f)
        if not isinstance(topN, list):
            topN = [topN]
        print(f"Loaded {len(topN)} genomes from {topn_path}")
        return topN
    except Exception as e:
        print(f"[Info] Failed to load {topn_path}: {e}\nTrying {winner_path}...")
        with open(winner_path, "rb") as f:
            g = pickle.load(f)
        print("Loaded 1 genome from winner.pkl")
        return [g]


# ============ 主函数：同时演示前 N 个 ============
def demo_topN(genomes: List[neat.genome.DefaultGenome], config):
    pygame.init()

    # 👉 想窗口模式就用这行；想全屏就换成 FULLSCREEN
    screen = pygame.display.set_mode((WIDTH, HEIGHT))  # or pygame.FULLSCREEN
    clock = pygame.time.Clock()
    hud_font  = pygame.font.SysFont("Arial", 20)
    title_font = pygame.font.SysFont("Arial", 28)

    # 赛道与底图
    track = Track(
        map=MAP,
        map_width=WIDTH,
        map_height=HEIGHT,
        v_turn_floor=V_TURN_FLOOR,
        turn_exp=TURN_EXP,
        limit_smooth_alpha=LIMIT_SMOOTH_ALPHA,
        border_color=BORDER_COLOR
    )

    # 每辆车的网络、实例与轨迹层
    nets  = []
    cars  = []
    trails = []  # 每辆车一个独立的 trail surface，避免颜色混杂
    trail_colors = []  # 每辆车轨迹颜色（用车身色+不透明黑边效果也可，这里直接黑）

    for g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)

        # 用 genome.key 作为稳定 index => 颜色 & 车身编号都稳定
        car = Car(
            index=g.key,
            car_img=CAR_IMAGE,
            car_size_x=CAR_SIZE_X,
            car_size_y=CAR_SIZE_Y,
            wheelbase_px=WHEELBASE_PX,
            max_steer_deg=MAX_STEER_DEG,
            start_position=START_POSITION,     # 注意：大家同点起步；如需错位，可在此处添加偏移
            radar_max_len=RADAR_MAX_LEN,
            v_min=V_MIN,
            v_max=V_MAX,
            start_facing_angle=STARTING_ANGLE
        )
        cars.append(car)

        # 为每辆车建一层轨迹画布（透明）
        t = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        trails.append(t)
        trail_colors.append((*car.sprite.get_at((car.car_size_x//2, car.car_size_y//2))[:3], 255))

    running = True
    counter = 0

    while running:
        # 事件处理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            running = False

        # == 所有车一步物理 ==
        still_alive = 0
        for i, car in enumerate(cars):
            if not car.is_alive():
                continue

            steer_cmd, accel_cmd = nets[i].activate(car.get_data(INPUT_NORMALIZATION_DENOMINATOR, SPEED_NORM))
            steer_cmd = max(-1.0, min(1.0, steer_cmd))
            accel_cmd = max(-1.0, min(1.0, accel_cmd))

            track.update_car_kinematics(
                car,
                steer_cmd,
                accel_cmd
            )
            if car.is_alive():
                still_alive += 1

                # 记录轨迹并画到自己的轨迹层
                if not hasattr(car, "trail"):
                    car.trail = []
                car.trail.append((int(car.center[0]), int(car.center[1])))
                if len(car.trail) > 1:
                    pygame.draw.line(trails[i], trail_colors[i], car.trail[-2], car.trail[-1], 2)

        counter += 1
        if still_alive == 0 or counter >= FPS * MAX_SIM_SECONDS:
            running = False

        # == 渲染 ==
        screen.blit(track.map_surface, (0, 0))
        # 先把所有轨迹层贴上来
        for t in trails:
            screen.blit(t, (0, 0))

        # 再画车（车会盖在轨迹上）
        for car in cars:
            if car.is_alive():
                track.draw_car(screen, car=car, plot_radar=PLOT_RADAR)

        # HUD
        elapsed_seconds = counter / FPS
        title = title_font.render(f"Top-{len(genomes)} Demo", True, TEXT_COLOR)
        screen.blit(title, title.get_rect(topright=(WIDTH-20, 20)))

        hud_lines = [
            f"Time: {elapsed_seconds:.1f}s",
            f"Alive: {still_alive}/{len(genomes)}",
            "ESC to exit",
        ]
        y = 60
        for line in hud_lines:
            t = hud_font.render(line, True, TEXT_COLOR)
            screen.blit(t, (WIDTH-20 - t.get_width(), y))
            y += 24

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


# ===================== 入口 =====================
if __name__ == "__main__":
    # 载入 NEAT 配置（必须与训练一致）
    config_path = "./config_modified.txt"
    config = neat.config.Config(neat.DefaultGenome,
                                neat.DefaultReproduction,
                                neat.DefaultSpeciesSet,
                                neat.DefaultStagnation,
                                config_path)

    # 先尝试加载 topN；失败则退回 winner
    genomes = load_topN_genomes("topN_genomes.pkl", "winner.pkl")[:10]

    # 如果 topN.pkl 里是（每代topN那种）二维结构，可在这里拍平：
    # if genomes and isinstance(genomes[0], list):
    #     genomes = [g for sub in genomes for g in sub]

    demo_topN(genomes, config)
