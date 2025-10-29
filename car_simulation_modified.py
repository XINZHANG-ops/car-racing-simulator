"""
这个版本，计算漂移，减速，甩尾
"""

import math
import random
import sys
import os

import neat
import pygame

# Constants
# WIDTH = 1600
# HEIGHT = 880

MAP = 'k1.png'

MAX_SIM_SECONDS = 23
FPS = 60
dt = 1.0 / FPS

# 自行车模型参数（像素为单位）
WHEELBASE_PX   = 50.0      # 轴距（按你的车图大小和地图比例调）
MAX_STEER_DEG  = 30.0      # 最大前轮转角（物理转向角，不是航向变化）
MAX_STEER_RAD  = math.radians(MAX_STEER_DEG)

# 地面抓地与阈值
MU             = 0.5       # 轮胎-路面摩擦系数，0.1~1.2 间调
# 若没有真实比例尺，直接用“像素/帧²”的 g_eff 当阈值常量（经验值）
G_EFF          = 0.4       # 你可以从 0.3~1.5 之间试，越大越不容易滑

# 打滑产生的额外偏航与掉速
K_OVERSTEER    = 0.3       # 过极限后的“额外偏航”强度
K_DRIFT_SLOW   = 1.0      # 滑时速度衰减比例
ALPHA_STEER    = 0.5       # 转向平滑（低通滤波）系数

TEXT_COLOR = (255,255,255)
STEER_PER_STEP_DEG = 270 / FPS   # 每帧最大转角步进（度） 如果我们用一秒来考虑，由于我们一秒有 FPS 帧，我们规定一秒最多比如 90 度，则这里设置 90 / FPS

V_MIN, V_MAX       = 2.0, 4.2
ACCEL_PER_STEP     = V_MAX / (1.5 * FPS)    # 每帧速度变化量（像素/帧）如果我们想让车起码 1.5 秒才能加速到最高，则 V_MAX / FPS


WIDTH = 1920
HEIGHT = 1080

CAR_SIZE_X = 60    
CAR_SIZE_Y = 60

BORDER_COLOR = (255, 255, 255, 255) # Color To Crash on Hit

current_generation = 0 # Generation counter

class Car:

    def __init__(self):
        # Load Car Sprite and Rotate
        self.sprite = pygame.image.load('car.png').convert() # Convert Speeds Up A Lot
        self.sprite = pygame.transform.scale(self.sprite, (CAR_SIZE_X, CAR_SIZE_Y))
        self.rotated_sprite = self.sprite 

        # self.position = [690, 740] # Starting Position
        # self.position = [830, 920] # Starting Position
        self.position = [950, 680] # Starting Position
        self.angle = 180
        self.speed = 0

        self.speed_set = False # Flag For Default Speed Later on

        self.center = [self.position[0] + CAR_SIZE_X / 2, self.position[1] + CAR_SIZE_Y / 2] # Calculate Center

        self.radars = [] # List For Sensors / Radars
        self.drawing_radars = [] # Radars To Be Drawn

        self.alive = True # Boolean To Check If Car is Crashed

        self.distance = 0 # Distance Driven
        self.time = 0 # Time Passed

    def draw(self, screen):
        screen.blit(self.rotated_sprite, self.position)
        if getattr(self, "drifting", False):
            # 漂移时车尾画一个小点
            pygame.draw.circle(screen, (255, 0, 0), (int(self.center[0]), int(self.center[1])), 20, 20)
        self.draw_radar(screen)  # 如果你想可视化雷达，保留

    def draw_radar(self, screen):
        # Optionally Draw All Sensors / Radars
        for radar in self.radars:
            position = radar[0]
            pygame.draw.line(screen, (0, 255, 0), self.center, position, 1)
            pygame.draw.circle(screen, (0, 255, 0), position, 5)

    def check_collision(self, game_map):
        self.alive = True
        for point in self.corners:
            # If Any Corner Touches Border Color -> Crash
            # Assumes Rectangle
            if game_map.get_at((int(point[0]), int(point[1]))) == BORDER_COLOR:
                self.alive = False
                break

    def check_radar(self, degree, game_map):
        length = 0
        x = int(self.center[0] + math.cos(math.radians(360 - (self.angle + degree))) * length)
        y = int(self.center[1] + math.sin(math.radians(360 - (self.angle + degree))) * length)

        # While We Don't Hit BORDER_COLOR AND length < 300 (just a max) -> go further and further
        while not game_map.get_at((x, y)) == BORDER_COLOR and length < 300:
            length = length + 1
            x = int(self.center[0] + math.cos(math.radians(360 - (self.angle + degree))) * length)
            y = int(self.center[1] + math.sin(math.radians(360 - (self.angle + degree))) * length)

        # Calculate Distance To Border And Append To Radars List
        dist = int(math.sqrt(math.pow(x - self.center[0], 2) + math.pow(y - self.center[1], 2)))
        self.radars.append([(x, y), dist])
    
    def update(self, game_map):
        # Get Rotated Sprite And Move Into The Right X-Direction
        # Don't Let The Car Go Closer Than 20px To The Edge
        self.rotated_sprite = self.rotate_center(self.sprite, self.angle)
        self.position[0] += math.cos(math.radians(360 - self.angle)) * self.speed
        self.position[0] = max(self.position[0], 20)
        self.position[0] = min(self.position[0], WIDTH - 120)

        # Increase Distance and Time
        self.distance += self.speed
        self.time += 1
        
        # Same For Y-Position
        self.position[1] += math.sin(math.radians(360 - self.angle)) * self.speed
        self.position[1] = max(self.position[1], 20)
        self.position[1] = min(self.position[1], HEIGHT - 120)

        # Calculate New Center
        self.center = [int(self.position[0]) + CAR_SIZE_X / 2, int(self.position[1]) + CAR_SIZE_Y / 2]

        # Calculate Four Corners
        # Length Is Half The Side
        length = 0.5 * CAR_SIZE_X
        left_top = [self.center[0] + math.cos(math.radians(360 - (self.angle + 30))) * length, self.center[1] + math.sin(math.radians(360 - (self.angle + 30))) * length]
        right_top = [self.center[0] + math.cos(math.radians(360 - (self.angle + 150))) * length, self.center[1] + math.sin(math.radians(360 - (self.angle + 150))) * length]
        left_bottom = [self.center[0] + math.cos(math.radians(360 - (self.angle + 210))) * length, self.center[1] + math.sin(math.radians(360 - (self.angle + 210))) * length]
        right_bottom = [self.center[0] + math.cos(math.radians(360 - (self.angle + 330))) * length, self.center[1] + math.sin(math.radians(360 - (self.angle + 330))) * length]
        self.corners = [left_top, right_top, left_bottom, right_bottom]

        # Check Collisions And Clear Radars
        self.check_collision(game_map)
        self.radars.clear()

        # From -90 To 120 With Step-Size 45 Check Radar
        for d in range(-90, 120, 45):
            self.check_radar(d, game_map)

    def get_data(self):
        # Get Distances To Border
        radars = self.radars
        return_values = [0, 0, 0, 0, 0]
        for i, radar in enumerate(radars):
            return_values[i] = int(radar[1] / 30)

        return return_values

    def is_alive(self):
        # Basic Alive Function
        return self.alive

    def get_reward(self):
        # Calculate Reward (Maybe Change?)
        # return self.distance / 50.0
        return self.distance / (CAR_SIZE_X / 2)

    def rotate_center(self, image, angle):
        # Rotate The Rectangle
        rectangle = image.get_rect()
        rotated_image = pygame.transform.rotate(image, angle)
        rotated_rectangle = rectangle.copy()
        rotated_rectangle.center = rotated_image.get_rect().center
        rotated_image = rotated_image.subsurface(rotated_rectangle).copy()
        return rotated_image


def run_simulation(genomes, config):
    
    # Empty Collections For Nets and Cars
    nets = []
    cars = []

    # Initialize PyGame And The Display
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)

    # For All Genomes Passed Create A New Neural Network
    for i, g in genomes:
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        g.fitness = 0

        cars.append(Car())

    # Clock Settings
    # Font Settings & Loading Map
    clock = pygame.time.Clock()
    generation_font = pygame.font.SysFont("Arial", 30)
    alive_font = pygame.font.SysFont("Arial", 20)
    game_map = pygame.image.load(MAP).convert() # Convert Speeds Up A Lot

    global current_generation
    current_generation += 1

    # Simple Counter To Roughly Limit Time (Not Good Practice)
    counter = 0

    while True:
        # Exit On Quit Event
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)

        # For Each Car Get The Acton It Takes
        for i, car in enumerate(cars):
            # 网络输出：[-1,1]，映射到物理前轮转角 δ 和纵向加减速
            steer_cmd, accel_cmd = nets[i].activate(car.get_data())  # 我们最后一层的act是tanh => [-1,1] 附近
            steer_cmd = max(-1.0, min(1.0, steer_cmd)) # 我们把转向 clip 在 -1 到 1 之间
            accel_cmd = max(-1.0, min(1.0, accel_cmd)) # 我们把加速 clip 在 -1 到 1 之间

            # 1) 平滑命令，避免抖动,  这里做一个平滑的转向，alpha 越小，越平滑，取 1 则没有平滑
            car._steer_smoothed = getattr(car, "_steer_smoothed", 0.0) * (1 - ALPHA_STEER) + steer_cmd * ALPHA_STEER

            # 2) 把平滑后的命令映射到“物理转向角 δ”（前轮转角）
            delta = car._steer_smoothed * MAX_STEER_RAD   # δ ∈ [-MAX_STEER_RAD, +MAX_STEER_RAD]

            # 3) 自行车模型：计算本帧航向角变化（弧度/帧）
            #    注意：你的 v 是“像素/帧”，L 是“像素”，所以 v/L 的量纲是 1/帧；tan(δ) 无量纲。
            psi_dot = (car.speed / WHEELBASE_PX) * math.tan(delta)    # 弧度/帧
            dpsi_rad = psi_dot                                        # 每帧增量（已是/帧）

            # 4) 横向加速度（像素/帧²）用于打滑判定
            a_lat = (car.speed * car.speed / WHEELBASE_PX) * abs(math.tan(delta))

            # 5) 打滑判定：超出 μ*g_eff 时产生“过度转向”与掉速
            car.drifting = False
            limit = MU * G_EFF
            if a_lat > limit:
                car.drifting = True
                # 超额比例（越大，越滑）
                excess = (a_lat - limit) / (limit + 1e-6)
                # 甩尾：额外航向变化，方向同 δ 号
                dpsi_rad += K_OVERSTEER * excess * math.copysign(1.0, delta)
                # 掉速：随越界比例衰减
                car.speed -= K_DRIFT_SLOW * excess
                car.speed = max(V_MIN, min(V_MAX, car.speed))

            # 6) 应用航向角
            car.angle += math.degrees(dpsi_rad)
            car.angle %= 360.0

            # 7) 纵向速度（油门/刹车）
            car.speed += ACCEL_PER_STEP * accel_cmd
            car.speed  = max(V_MIN, min(V_MAX, car.speed))

        
        # Check If Car Is Still Alive
        # Increase Fitness If Yes And Break Loop If Not
        still_alive = 0
        for i, car in enumerate(cars):
            if car.is_alive():
                still_alive += 1
                car.update(game_map)
                genomes[i][1].fitness += car.get_reward()

        if still_alive == 0:
            break

        counter += 1
        if counter == FPS * MAX_SIM_SECONDS:
            break

        # Draw Map And All Cars That Are Alive
        screen.blit(game_map, (0, 0))
        for car in cars:
            if car.is_alive():
                car.draw(screen)
        
        # Display Info
        text = generation_font.render("Generation: " + str(current_generation), True, TEXT_COLOR)
        text_rect = text.get_rect()
        text_rect.center = (900, 450)
        screen.blit(text, text_rect)

        text = alive_font.render("Still Alive: " + str(still_alive), True, TEXT_COLOR)
        text_rect = text.get_rect()
        text_rect.center = (900, 490)
        screen.blit(text, text_rect)

        pygame.display.flip()
        clock.tick(FPS) # 60 FPS

if __name__ == "__main__":
    
    # Load Config
    config_path = "./config_modified.txt"
    config = neat.config.Config(neat.DefaultGenome,
                                neat.DefaultReproduction,
                                neat.DefaultSpeciesSet,
                                neat.DefaultStagnation,
                                config_path)

    # Create Population And Add Reporters
    population = neat.Population(config)
    population.add_reporter(neat.StdOutReporter(True))
    stats = neat.StatisticsReporter()
    population.add_reporter(stats)
    
    # Run Simulation For A Maximum of 1000 Generations
    population.run(run_simulation, 1000)


    # import pickle
    # # ……前略……
    # winner = population.run(run_simulation, 1000)   # 返回当代里 fitness 最高的基因组
    # with open("winner.pkl", "wb") as f:
    #     pickle.dump(winner, f)

    # # 需要时加载
    # with open("winner.pkl", "rb") as f:
    #     winner = pickle.load(f)

    # # 用它构建可执行网络（推理）
    # best_net = neat.nn.FeedForwardNetwork.create(winner, config)

    # # 之后你可以在一个“评估/演示”循环里只跑这一个网络：
    # # obs = car.get_data(); action = best_net.activate(obs); …（不再进化）