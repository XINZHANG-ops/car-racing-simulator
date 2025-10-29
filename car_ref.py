"""
简化版：根据转向大小动态限速（转得越大，允许的最高速度越低）
- 无摩擦/横向加速度判定
- 限速平滑下降：不会瞬间把速度钳到低值，而是用每帧固定的刹车率渐进下降
"""

import math
import random
import sys
import os

import neat
import pygame

# ===================== 基本设置 =====================
MAP = 'k1.png'

MAX_SIM_SECONDS = 23
FPS = 60
dt = 1.0 / FPS

# 自行车模型参数（像素为单位）
WHEELBASE_PX   = 50.0      # 轴距（按你的车图大小和地图比例调）
MAX_STEER_DEG  = 30.0      # 最大前轮转角（物理转向角，不是航向变化）
MAX_STEER_RAD  = math.radians(MAX_STEER_DEG)

# 转向限速（角度越大 -> 限速越低）
V_MIN, V_MAX       = 2.0, 4.2
ACCEL_PER_STEP     = V_MAX / (1.5 * FPS)    # 1.5 秒 0->V_MAX
V_TURN_FLOOR       = 1.0     # 打满方向时的最高速下限
TURN_EXP           = 1.6     # 曲线形状：越大弯内越慢；1.6~2.5 之间调
BRAKE_PER_STEP     = 2.0 * ACCEL_PER_STEP   # 超限时每帧自动减速量（平滑降速的力度）
LIMIT_SMOOTH_ALPHA = 0.4     # 限速的低通平滑（0~1，越大响应越快）
ALPHA_STEER        = 0.5     # 转向平滑（低通滤波）系数

# 画面/碰撞
TEXT_COLOR   = (255, 255, 255)
WIDTH, HEIGHT = 1920, 1080
CAR_SIZE_X, CAR_SIZE_Y = 60, 60
BORDER_COLOR = (255, 255, 255, 255)  # 碰撞的颜色（白色）

current_generation = 0  # 世代计数

# ===================== 车辆类 =====================
class Car:

    def __init__(self):
        # 载入车贴图
        self.sprite = pygame.image.load('car.png').convert()
        self.sprite = pygame.transform.scale(self.sprite, (CAR_SIZE_X, CAR_SIZE_Y))
        self.rotated_sprite = self.sprite

        # 初始位姿
        self.position = [950, 680]  # 起点
        self.angle = 180            # 航向角（度）
        self.speed = 0.0

        # 缓存
        self._steer_smoothed = 0.0
        self._vlimit_smooth  = V_MAX  # 平滑后的转向限速

        self.center = [self.position[0] + CAR_SIZE_X / 2, self.position[1] + CAR_SIZE_Y / 2]

        self.radars = []          # 雷达点
        self.drawing_radars = []  # 可视化雷达
        self.alive = True

        self.distance = 0.0  # 行驶距离（像素）
        self.time = 0        # 生存帧数

    def draw(self, screen):
        screen.blit(self.rotated_sprite, self.position)
        # 可选：漂移点效果已移除（若需要可自定义某些条件时画点）
        self.draw_radar(screen)

    def draw_radar(self, screen):
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

        while not game_map.get_at((x, y)) == BORDER_COLOR and length < 300:
            length += 1
            x = int(self.center[0] + math.cos(math.radians(360 - (self.angle + degree))) * length)
            y = int(self.center[1] + math.sin(math.radians(360 - (self.angle + degree))) * length)

        dist = int(math.sqrt((x - self.center[0]) ** 2 + (y - self.center[1]) ** 2))
        self.radars.append([(x, y), dist])

    def update(self, game_map):
        # 旋转贴图 & 位置更新
        self.rotated_sprite = self.rotate_center(self.sprite, self.angle)
        self.position[0] += math.cos(math.radians(360 - self.angle)) * self.speed
        self.position[0] = max(self.position[0], 20)
        self.position[0] = min(self.position[0], WIDTH - 120)

        self.distance += self.speed
        self.time += 1

        self.position[1] += math.sin(math.radians(360 - self.angle)) * self.speed
        self.position[1] = max(self.position[1], 20)
        self.position[1] = min(self.position[1], HEIGHT - 120)

        # 更新中心与四角
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

        # 碰撞 & 雷达
        self.check_collision(game_map)
        self.radars.clear()
        for d in range(-90, 120, 45):
            self.check_radar(d, game_map)

    def get_data(self):
        # 5 路雷达距离（/30 归一）
        radars = self.radars
        ret = [0, 0, 0, 0, 0]
        for i, radar in enumerate(radars):
            ret[i] = int(radar[1] / 30)
        return ret

    def is_alive(self):
        return self.alive

    def get_reward(self):
        # 仍按原样（你可以换成 checkpoint 奖励等）
        return self.distance / (CAR_SIZE_X / 2)

    def rotate_center(self, image, angle):
        rectangle = image.get_rect()
        rotated_image = pygame.transform.rotate(image, angle)
        rotated_rectangle = rectangle.copy()
        rotated_rectangle.center = rotated_image.get_rect().center
        rotated_image = rotated_image.subsurface(rotated_rectangle).copy()
        return rotated_image

# ===================== 仿真主循环（NEAT 回调） =====================
def run_simulation(genomes, config):
    nets = []
    cars = []

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)

    for i, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        g.fitness = 0.0
        cars.append(Car())

    clock = pygame.time.Clock()
    generation_font = pygame.font.SysFont("Arial", 30)
    alive_font = pygame.font.SysFont("Arial", 20)
    game_map = pygame.image.load(MAP).convert()

    global current_generation
    current_generation += 1

    counter = 0

    # —— 转向限速函数 —— #
    def turn_speed_limit(delta_rad):
        # 归一化转角：x ∈ [0,1]
        x = min(1.0, abs(delta_rad) / MAX_STEER_RAD)
        # 平滑下降：x=0 -> V_MAX；x=1 -> V_TURN_FLOOR
        return V_TURN_FLOOR + (V_MAX - V_TURN_FLOOR) * (1.0 - (x ** TURN_EXP))

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)

        # —— 行为与动力学 —— #
        for i, car in enumerate(cars):
            steer_cmd, accel_cmd = nets[i].activate(car.get_data())  # 输出2维：转向, 加速度
            steer_cmd = max(-1.0, min(1.0, steer_cmd))
            accel_cmd = max(-1.0, min(1.0, accel_cmd))

            # 转向平滑
            car._steer_smoothed = car._steer_smoothed * (1 - ALPHA_STEER) + steer_cmd * ALPHA_STEER
            # 物理前轮转角 δ
            delta = car._steer_smoothed * MAX_STEER_RAD

            # 航向角变化（Kinematic Bicycle）
            psi_dot = (car.speed / WHEELBASE_PX) * math.tan(delta)  # 弧度/帧
            dpsi_rad = psi_dot

            # 应用航向
            car.angle += math.degrees(dpsi_rad)
            car.angle %= 360.0

            # —— 动态限速（随转向） + 平滑下降 —— #
            v_limit_inst = turn_speed_limit(delta)  # 当前瞬时限速（函数）
            # 对 v_limit 做低通平滑，避免突然跳变
            car._vlimit_smooth = (1 - LIMIT_SMOOTH_ALPHA) * getattr(car, "_vlimit_smooth", V_MAX) \
                                 + LIMIT_SMOOTH_ALPHA * v_limit_inst
            v_limit = car._vlimit_smooth

            # 先按加速度更新
            if accel_cmd >= 0.0:
                car.speed += ACCEL_PER_STEP * accel_cmd
                # 正油门不超过全局 V_MAX
                car.speed = min(car.speed, V_MAX)
            else:
                # 允许主动刹车到 V_MIN
                car.speed += ACCEL_PER_STEP * accel_cmd
                car.speed = max(V_MIN, car.speed)

            # 若超出限速，按固定刹车率渐进下降（不会瞬间砍到限速）
            if car.speed > v_limit:
                car.speed = max(v_limit, car.speed - BRAKE_PER_STEP)

            # 最后做全局夹
            car.speed = max(V_MIN, min(V_MAX, car.speed))

        # —— 存活、更新、奖励 —— #
        still_alive = 0
        for i, car in enumerate(cars):
            if car.is_alive():
                still_alive += 1
                car.update(game_map)
                genomes[i][1].fitness += car.get_reward()

        if still_alive == 0:
            break

        counter += 1
        if counter >= FPS * MAX_SIM_SECONDS:
            break

        # —— 渲染 —— #
        screen.blit(game_map, (0, 0))
        for car in cars:
            if car.is_alive():
                car.draw(screen)

        text = generation_font.render(f"Generation: {current_generation}", True, TEXT_COLOR)
        text_rect = text.get_rect()
        text_rect.center = (900, 450)
        screen.blit(text, text_rect)

        text = alive_font.render(f"Still Alive: {still_alive}", True, TEXT_COLOR)
        text_rect = text.get_rect()
        text_rect.center = (900, 490)
        screen.blit(text, text_rect)

        pygame.display.flip()
        clock.tick(FPS)

# ===================== 入口 =====================
if __name__ == "__main__":
    # 载入 NEAT 配置（需把 num_outputs=2，对应 [steer, accel]）
    config_path = "./config_modified.txt"
    config = neat.config.Config(neat.DefaultGenome,
                                neat.DefaultReproduction,
                                neat.DefaultSpeciesSet,
                                neat.DefaultStagnation,
                                config_path)

    population = neat.Population(config)
    population.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    population.add_reporter(stats)

    population.run(run_simulation, 1000)
