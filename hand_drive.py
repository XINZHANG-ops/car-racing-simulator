import math
import pygame


from src.my_env import (
    Car,
    Track
)


# ==== 复用你的 env_settings（保持和训练一致）====
from env_settings import (
    MAP,
    CAR_IMAGE,
    FPS,
    MAX_SIM_SECONDS,   # 仅用于 HUD 显示；不强制结束
    WHEELBASE_PX,
    MAX_STEER_DEG,
    V_MIN,
    V_MAX,
    ACCEL_PER_STEP,
    V_TURN_FLOOR,
    TURN_EXP,
    BRAKE_PER_STEP,
    LIMIT_SMOOTH_ALPHA,
    ALPHA_STEER,
    TEXT_COLOR,
    START_POSITION,
    STARTING_ANGLE,
    WIDTH, HEIGHT,
    CAR_SIZE_X, CAR_SIZE_Y,
    BORDER_COLOR,
    RADAR_MAX_LEN,
    PLOT_RADAR,           # 画不画雷达
)

# ============ 主程序：键盘驾驶 ============
def main():
    pygame.init()

    screen = pygame.display.set_mode((WIDTH, HEIGHT))  # 窗口模式；如需全屏换成 pygame.FULLSCREEN
    clock = pygame.time.Clock()
    font_big = pygame.font.SysFont("Arial", 28)
    font_small = pygame.font.SysFont("Arial", 18)

    track = Track(MAP, WIDTH, HEIGHT, V_TURN_FLOOR, LIMIT_SMOOTH_ALPHA, TURN_EXP, BORDER_COLOR)
    car = Car(
        index=1,  # 固定一个颜色编号即可
        car_img=CAR_IMAGE,
        car_size_x=CAR_SIZE_X,
        car_size_y=CAR_SIZE_Y,
        wheelbase_px=WHEELBASE_PX,
        max_steer_deg=MAX_STEER_DEG,
        start_position=START_POSITION,
        radar_max_len=RADAR_MAX_LEN,
        v_min=V_MIN,
        v_max=V_MAX,
        start_facing_angle=STARTING_ANGLE,
    )

    trail_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    # 键控参数
    STEER_RATE = 1.5      # 每秒可把 steer_cmd 变化多少（幅度单位）
    BRAKE_HARD = 5.0      # 空格紧急刹车的“倍数”
    steer_cmd = 0.0       # [-1, 1]
    accel_cmd = 0.0       # [-1, 1]

    running = True
    while running:
        dt = 1.0 / FPS

        # 事件与退出
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            running = False

        # ---- 键盘转向：持续按住线性变化，松开自动回正 ----
        steer_target = 0.0
        if keys[pygame.K_LEFT]:
            steer_target += 1.0
        if keys[pygame.K_RIGHT]:
            steer_target -= 1.0
        # 用 STEER_RATE 平滑逼近 steer_target
        if steer_cmd < steer_target:
            steer_cmd = min(steer_cmd + STEER_RATE * dt, steer_target)
        elif steer_cmd > steer_target:
            steer_cmd = max(steer_cmd - STEER_RATE * dt, steer_target)

        # ---- 油门/刹车 ----
        accel_target = 0.0
        if keys[pygame.K_UP]:
            accel_target += 1.0
        if keys[pygame.K_DOWN]:
            accel_target -= 1.0

        # 空格：紧急刹车（叠加到向下的目标）
        if keys[pygame.K_SPACE]:
            accel_target = -BRAKE_HARD

        # 直接跟随（也可以再做个低通）
        accel_cmd = accel_target

        # R 重置
        if keys[pygame.K_r]:
            car.reset(START_POSITION, STARTING_ANGLE)
            trail_surf.fill((0, 0, 0, 0))  # 清轨迹

        # ==== 更新动力学 ====
        track.update_car_kinematics(car, steer_cmd, accel_cmd)

        # ==== 画面 ====
        screen.blit(track.map_surface, (0, 0))

        # 追加轨迹（用车身颜色；刹车时用红色）
        car.trail.append((int(car.center[0]), int(car.center[1])))
        if len(car.trail) > 1:
            col = (255, 0, 0, 220) if accel_cmd < 0 else (*car.color, 220)
            pygame.draw.line(trail_surf, col, car.trail[-2], car.trail[-1], 2)
        screen.blit(trail_surf, (0, 0))

        # 画车与雷达
        track.draw_car(screen, car, plot_radar=PLOT_RADAR)

        # HUD
        hud_lines = [
            f"Speed: {car.speed:.2f} px/frame",
            f"SteerCmd: {steer_cmd:.2f}",
            f"AccelCmd: {accel_cmd:.2f}",
            f"Turn Vmax: {car._vlimit_smooth:.2f}",
            "ESC: Quit  |  R: Reset  |  SPACE: Brake",
        ]
        y0 = 20
        for line in hud_lines:
            t = font_small.render(line, True, TEXT_COLOR)
            screen.blit(t, (20, y0))
            y0 += 22

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
