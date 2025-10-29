import math
import pickle
import sys

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
    MAX_STEER_RAD,
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
    WIDTH, 
    HEIGHT,
    CAR_SIZE_X, 
    CAR_SIZE_Y,
    BORDER_COLOR,
    RADAR_MAX_LEN,
    INPUT_NORMALIZATION_DENOMINATOR
)



# ===================== 车辆类（与训练一致） =====================
class Car:
    def __init__(self):
        self.sprite = pygame.image.load(CAR_IMAGE).convert()
        self.sprite = pygame.transform.scale(self.sprite, (CAR_SIZE_X, CAR_SIZE_Y))
        self.rotated_sprite = self.sprite

        self.position = START_POSITION.copy()
        self.angle = 180
        self.speed = 0.0

        self._steer_smoothed = 0.0
        self._vlimit_smooth  = V_MAX

        self.center = [self.position[0] + CAR_SIZE_X / 2, self.position[1] + CAR_SIZE_Y / 2]
        self.radars = []
        self.alive = True

        self.distance = 0.0
        self.time = 0

    def draw(self, screen):
        screen.blit(self.rotated_sprite, self.position)
        for radar in self.radars:
            pos = radar[0]
            pygame.draw.line(screen, (0, 255, 0), self.center, pos, 1)
            pygame.draw.circle(screen, (0, 255, 0), pos, 5)

    def check_collision(self, game_map):
        self.alive = True
        for point in self.corners:
            if game_map.get_at((int(point[0]), int(point[1]))) == BORDER_COLOR:
                self.alive = False
                break

    def check_radar(self, degree, game_map):
        length = 0
        x = int(self.center[0] + math.cos(math.radians(360 - (self.angle + degree))) * length)
        y = int(self.center[1] + math.sin(math.radians(360 - (self.angle + degree))) * length)

        while not game_map.get_at((x, y)) == BORDER_COLOR and length < RADAR_MAX_LEN:
            length += 1
            x = int(self.center[0] + math.cos(math.radians(360 - (self.angle + degree))) * length)
            y = int(self.center[1] + math.sin(math.radians(360 - (self.angle + degree))) * length)

        dist = int(math.sqrt((x - self.center[0]) ** 2 + (y - self.center[1]) ** 2))
        self.radars.append([(x, y), dist])

    def update(self, game_map):
        self.rotated_sprite = self.rotate_center(self.sprite, self.angle)
        self.position[0] += math.cos(math.radians(360 - self.angle)) * self.speed
        self.position[0] = max(self.position[0], 20)
        self.position[0] = min(self.position[0], WIDTH - 120)

        self.distance += self.speed
        self.time += 1

        self.position[1] += math.sin(math.radians(360 - self.angle)) * self.speed
        self.position[1] = max(self.position[1], 20)
        self.position[1] = min(self.position[1], HEIGHT - 120)

        self.center = [int(self.position[0]) + CAR_SIZE_X / 2, int(self.position[1]) + CAR_SIZE_Y / 2]

        length = 0.5 * CAR_SIZE_X
        left_top = [self.center[0] + math.cos(math.radians(360 - (self.angle + 30))) * length,
                    self.center[1] + math.sin(math.radians(360 - (self.angle + 30))) * length]
        right_top = [self.center[0] + math.cos(math.radians(360 - (self.angle + 150))) * length,
                     self.center[1] + math.sin(math.radians(360 - (self.angle + 150))) * length]
        left_bottom = [self.center[0] + math.cos(math.radians(360 - (self.angle + 210))) * length,
                       self.center[1] + math.sin(math.radians(360 - (self.angle + 210))) * length]
        right_bottom = [self.center[0] + math.cos(math.radians(360 - (self.angle + 330))) * length,
                        self.center[1] + math.sin(math.radians(360 - (self.angle + 330))) * length]
        self.corners = [left_top, right_top, left_bottom, right_bottom]

        self.check_collision(game_map)
        self.radars.clear()
        for d in range(-90, 120, 45):
            self.check_radar(d, game_map)

    def get_data(self):
        ret = [0, 0, 0, 0, 0]
        for i, radar in enumerate(self.radars):
            ret[i] = radar[1] / INPUT_NORMALIZATION_DENOMINATOR
        return ret

    def is_alive(self):
        return self.alive

    def rotate_center(self, image, angle):
        rectangle = image.get_rect()
        rotated_image = pygame.transform.rotate(image, angle)
        rotated_rectangle = rectangle.copy()
        rotated_rectangle.center = rotated_image.get_rect().center
        rotated_image = rotated_image.subsurface(rotated_rectangle).copy()
        return rotated_image

# —— 与训练一致的“转向限速”函数 ——
def turn_speed_limit(delta_rad):
    x = min(1.0, abs(delta_rad) / MAX_STEER_RAD)  # 归一化转角强度
    return V_TURN_FLOOR + (V_MAX - V_TURN_FLOOR) * (1.0 - (x ** TURN_EXP))

# ===================== 单车演示 =====================
def demo_winner(best_net, config):
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
    clock = pygame.time.Clock()
    generation_font = pygame.font.SysFont("Arial", 30)
    info_font = pygame.font.SysFont("Arial", 20)

    game_map = pygame.image.load(MAP).convert()

    car = Car()
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
        steer_cmd, accel_cmd = best_net.activate(car.get_data())
        steer_cmd = max(-1.0, min(1.0, steer_cmd))
        accel_cmd = max(-1.0, min(1.0, accel_cmd))

        # 转向平滑 + 前轮转角
        car._steer_smoothed = car._steer_smoothed * (1 - ALPHA_STEER) + steer_cmd * ALPHA_STEER
        delta = car._steer_smoothed * MAX_STEER_RAD

        # 航向更新（Kinematic Bicycle）
        psi_dot = (car.speed / WHEELBASE_PX) * math.tan(delta)  # rad/frame
        car.angle = (car.angle + math.degrees(psi_dot)) % 360.0

        # 动态限速 + 平滑
        v_limit_inst = turn_speed_limit(delta)
        car._vlimit_smooth = (1 - LIMIT_SMOOTH_ALPHA) * getattr(car, "_vlimit_smooth", V_MAX) \
                             + LIMIT_SMOOTH_ALPHA * v_limit_inst
        v_limit = car._vlimit_smooth

        # 速度更新
        if accel_cmd >= 0.0:
            car.speed += ACCEL_PER_STEP * accel_cmd
            car.speed = min(car.speed, V_MAX)
        else:
            car.speed += ACCEL_PER_STEP * accel_cmd
            car.speed = max(V_MIN, car.speed)

        if car.speed > v_limit:
            car.speed = max(v_limit, car.speed - BRAKE_PER_STEP)

        car.speed = max(V_MIN, min(V_MAX, car.speed))

        # 物理 & 碰撞
        car.update(game_map)
        if not car.is_alive():
            running = False

        counter += 1
        if counter >= FPS * MAX_SIM_SECONDS:
            running = False

        # 绘制
        screen.blit(game_map, (0, 0))
        car.draw(screen)

        # HUD
        text = generation_font.render("Winner Demo", True, TEXT_COLOR)
        r = text.get_rect(); r.center = (900, 420)
        screen.blit(text, r)

        elapsed_seconds = counter / FPS
        hud_lines = [
            f"Time: {elapsed_seconds:.1f} s",
            f"Speed: {car.speed:.2f} px/frame",
            f"V_limit: {v_limit:.2f}",
            f"Steer cmd: {steer_cmd:.2f}",
        ]
        y = 460
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
    demo_winner(best_net, config)
