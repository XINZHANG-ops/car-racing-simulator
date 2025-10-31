import math
import pickle

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
    PLOT_RADAR
)

from src.my_env import (
    Car,
    Track
)


# ===================== 单车演示 =====================
def demo_winner(winner_id, best_net, config):
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
    clock = pygame.time.Clock()
    generation_font = pygame.font.SysFont("Arial", 30)
    info_font = pygame.font.SysFont("Arial", 20)

    trail_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)  # 创建轨迹层（带透明通道）

    car = Car(
        index=winner_id,
        car_img=CAR_IMAGE,
        car_size_x=CAR_SIZE_X,
        car_size_y=CAR_SIZE_Y,
        wheelbase_px=WHEELBASE_PX,
        max_steer_deg=MAX_STEER_DEG,
        start_position=START_POSITION,
        radar_max_len=RADAR_MAX_LEN,
        v_min=V_MIN,
        v_max=V_MAX,
        start_facing_angle=STARTING_ANGLE
    )

    track = Track(
        map=MAP,
        map_width=WIDTH,
        map_height=HEIGHT,
        v_turn_floor=V_TURN_FLOOR,
        turn_exp=TURN_EXP,
        limit_smooth_alpha=LIMIT_SMOOTH_ALPHA,
        border_color=BORDER_COLOR
    )
    counter = 0

    running = True
    while running:
        # 事件
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        # 按 ESC 退出
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            running = False

        # 网络输出
        steer_cmd, accel_cmd = best_net.activate(car.get_data(INPUT_NORMALIZATION_DENOMINATOR, SPEED_NORM))
        steer_cmd = max(-1.0, min(1.0, steer_cmd))
        accel_cmd = max(-1.0, min(1.0, accel_cmd))

        # 物理 & 碰撞
        track.update_car_kinematics(
                car,
                steer_cmd,
                accel_cmd
            )
        if not car.is_alive():
            running = False

        counter += 1
        if counter >= FPS * MAX_SIM_SECONDS:
            running = False

        # 绘制
        if not hasattr(car, "trail"):
            car.trail = []
        car.trail.append((int(car.center[0]), int(car.center[1])))
        if len(car.trail) > 1:
            if accel_cmd >= 0.0:
                pygame.draw.line(trail_surf, (255, 255, 255, 255), car.trail[-2], car.trail[-1], 2)
            else:
                pygame.draw.line(trail_surf, (255, 0, 0, 255), car.trail[-2], car.trail[-1], 2)

        screen.blit(track.map_surface, (0, 0))
        screen.blit(trail_surf, (0, 0))

        track.draw_car(screen, car=car, plot_radar=PLOT_RADAR)

        # HUD
        # text = generation_font.render("Winner Demo", True, TEXT_COLOR)
        # r = text.get_rect(); r.center = (900, 420)
        # screen.blit(text, r)

        elapsed_seconds = counter / FPS
        hud_lines = [
            f"Time: {elapsed_seconds:.1f} s",
            f"Speed: {car.speed:.2f} px/frame",
            f"V_limit: {car._vlimit_smooth:.2f}",
            f"Steer cmd: {steer_cmd:.2f}",
        ]
        y = 420
        for line in hud_lines:
            t = info_font.render(line, True, TEXT_COLOR)
            rect = t.get_rect(); rect.center = (900, y)
            screen.blit(t, rect)
            y += 30

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

# ===================== 入口：加载 winner 并演示 =====================
if __name__ == "__main__":
    # 加载 NEAT 配置（必须与训练一致）
    config_path = "./config_modified.txt"
    config = neat.config.Config(neat.DefaultGenome,
                                neat.DefaultReproduction,
                                neat.DefaultSpeciesSet,
                                neat.DefaultStagnation,
                                config_path)

    # 加载保存的最佳基因组
    with open("winner.pkl", "rb") as f:
        winner = pickle.load(f)

    # 构建可执行网络（推理）
    best_net = neat.nn.FeedForwardNetwork.create(winner, config)

    # 跑可视化演示
    demo_winner(winner.key, best_net, config)
