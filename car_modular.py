import math
import sys

import neat
import pygame

from env_settings import (
    MAP,
    CAR_IMAGE,
    FPS,
    MAX_SIM_SECONDS,
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
    WIDTH, 
    HEIGHT,
    CAR_SIZE_X, 
    CAR_SIZE_Y,
    BORDER_COLOR,
    RADAR_MAX_LEN,
    INPUT_NORMALIZATION_DENOMINATOR
)


def color_from_index(idx: int, sat=92, val=92):
    """
    - 用黄金角打散色相，颜色分布均匀
    - 高饱和高亮度 => 鲜明
    - 防止出现接近黑色
    """
    hue = (idx * 137.5) % 360
    c = pygame.Color(0, 0, 0, 255)
    c.hsva = (hue, sat, val, 100)
    rgb = (c.r, c.g, c.b)
    # 防黑色兜底：如果太暗，就抬高亮度
    if (rgb[0] + rgb[1] + rgb[2]) < 80:
        c.hsva = (hue, sat, 95, 100)
        rgb = (c.r, c.g, c.b)
    return rgb



def tint_surface_flat(src: pygame.Surface, rgb: tuple[int,int,int]) -> pygame.Surface:
    """把非透明像素的RGB直接替换为指定颜色，保留每个像素的alpha。"""
    tinted = src.copy()
    w, h = tinted.get_width(), tinted.get_height()
    # 逐像素很快，因为只有 60x60 一次性做，成本可忽略
    px = pygame.PixelArray(tinted)
    for y in range(h):
        for x in range(w):
            r,g,b,a = tinted.unmap_rgb(px[x, y]).r, tinted.unmap_rgb(px[x, y]).g, tinted.unmap_rgb(px[x, y]).b, (px.surface.get_at((x,y)).a)
            if a != 0:
                px[x, y] = (rgb[0], rgb[1], rgb[2], a)
    del px
    return tinted

class Car:

    def __init__(
            self,
            index: int,
            car_img: str,
            car_size_x: int,
            car_size_y: int,
            wheelbase_px: float,
            max_steer_deg: float,
            start_position: list[int, int],
            radar_max_len: int,
            v_min: float,
            v_max: float,
            start_facing_angle: int = 180
            ):
        # 载入车贴图

        base = pygame.image.load(car_img).convert_alpha()
        base = pygame.transform.scale(base, (car_size_x, car_size_y))
        # self.sprite = pygame.image.load(car_img).convert()
        # self.sprite = pygame.transform.scale(self.sprite, (car_size_x, car_size_y))

        # 基于 index 生成稳定的“随机颜色”，只给非透明部分上色
        car_rgb = color_from_index(index)                        # 用上面的取色函数
        self.sprite = tint_surface_flat(base, car_rgb) # 你现有的“保留 alpha 的上色”函数
        self.rotated_sprite = self.sprite

        self.index = index

        self.car_size_x = car_size_x
        self.car_size_y = car_size_y

        # === 字体与编号贴图 ===
        # 字号按车高比例来，粗体更清晰
        # font_size = max(14, int(self.car_size_y * 0.55))
        font_size = 15
        self._idx_font = pygame.font.SysFont("Arial", font_size, bold=True)
        # 黑色文字
        self._idx_surf = self._idx_font.render(str(self.index), True, (0, 0, 0))

        self.radar_max_len = radar_max_len
        self.wheelbase_px = wheelbase_px # 轴距
        self.max_steer_deg = max_steer_deg # 最大前轮转角（物理转向角，不是航向变化）
        self.max_steer_rad =  math.radians(max_steer_deg)

        # 初始位姿
        self.position = start_position.copy()
        self.angle = start_facing_angle  # 航向角（度）
        self.speed = 0.0

        # 缓存
        self.v_min = v_min
        self.v_max = v_max
        self._steer_smoothed = 0.0
        self._vlimit_smooth  = v_max  # 平滑后的转向限速

        self.center = [self.position[0] + car_size_x / 2, self.position[1] + car_size_y / 2]

        self.radars = []          # 雷达点
        self.drawing_radars = []  # 可视化雷达
        self.alive = True

        self.distance = 0.0  # 行驶距离（像素）
        self.time = 0        # 生存帧数

        self.radar_angles = list(range(-90, 120, 45))

    def get_data(self, normalization_denominator: int=30):
        radars = self.radars
        ret = [0] * len(self.radar_angles)
        for i, radar in enumerate(radars):
            ret[i] = int(radar[1] / normalization_denominator)
        return ret
    
    def is_alive(self):
        return self.alive


class Track:
    def __init__(
            self,
            map: str,
            map_width: int,
            map_height: int,
            v_turn_floor: float,
            limit_smooth_alpha: float,
            turn_exp: float,
            border_color: tuple[int, int, int, int]=(255, 255, 255, 255),

            ):
        self.map = map
        self.width = map_width
        self.height = map_height
        
        self.v_turn_floor = v_turn_floor
        self.limit_smooth_alpha = limit_smooth_alpha
        self.turn_exp = turn_exp

        self.border_color = border_color
        

    def draw(self, screen, car: Car):
        # screen.blit(car.rotated_sprite, car.position)
        screen.blit(car.rotated_sprite, car.position)
        label_rect = car._idx_surf.get_rect(center=(int(car.center[0]), int(car.center[1])))
        screen.blit(car._idx_surf, label_rect)

        self.draw_radar(screen, car)

    def draw_radar(self, screen, car: Car):
        for radar in car.radars:
            pos = radar[0]
            pygame.draw.line(screen, (0, 255, 0), car.center, pos, 1)
            pygame.draw.circle(screen, (0, 255, 0), pos, 5)

    def check_collision(self, game_map, car: Car):
        car.alive = True
        for point in car.corners:
            if game_map.get_at((int(point[0]), int(point[1]))) == self.border_color:
                car.alive = False
                break

    def check_radar(self, game_map, degree: int, car: Car):
        length = 0
        x = int(car.center[0] + math.cos(math.radians(360 - (car.angle + degree))) * length)
        y = int(car.center[1] + math.sin(math.radians(360 - (car.angle + degree))) * length)

        while not game_map.get_at((x, y)) == self.border_color and length < car.radar_max_len:
            length += 1
            x = int(car.center[0] + math.cos(math.radians(360 - (car.angle + degree))) * length)
            y = int(car.center[1] + math.sin(math.radians(360 - (car.angle + degree))) * length)

        dist = int(math.sqrt((x - car.center[0]) ** 2 + (y - car.center[1]) ** 2))
        car.radars.append([(x, y), dist])

    def update(self, game_map, car: Car):
        # 旋转贴图 & 位置更新
        car.rotated_sprite = self.rotate_center(car.sprite, car.angle)
        car.position[0] += math.cos(math.radians(360 - car.angle)) * car.speed
        car.position[0] = max(car.position[0], 20)
        car.position[0] = min(car.position[0], self.width - 120)

        car.distance += car.speed
        car.time += 1

        car.position[1] += math.sin(math.radians(360 - car.angle)) * car.speed
        car.position[1] = max(car.position[1], 20)
        car.position[1] = min(car.position[1], self.height - 120)

        # 更新中心与四角
        car.center = [int(car.position[0]) + car.car_size_x / 2, int(car.position[1]) + car.car_size_y / 2]

        length = 0.5 * car.car_size_x
        left_top = [car.center[0] + math.cos(math.radians(360 - (car.angle + 30))) * length,
                    car.center[1] + math.sin(math.radians(360 - (car.angle + 30))) * length]
        right_top = [car.center[0] + math.cos(math.radians(360 - (car.angle + 150))) * length,
                     car.center[1] + math.sin(math.radians(360 - (car.angle + 150))) * length]
        left_bottom = [car.center[0] + math.cos(math.radians(360 - (car.angle + 210))) * length,
                       car.center[1] + math.sin(math.radians(360 - (car.angle + 210))) * length]
        right_bottom = [car.center[0] + math.cos(math.radians(360 - (car.angle + 330))) * length,
                        car.center[1] + math.sin(math.radians(360 - (car.angle + 330))) * length]
        car.corners = [left_top, right_top, left_bottom, right_bottom]

        # 碰撞 & 雷达
        self.check_collision(game_map, car)  # 检查四角是否碰到白色
        car.radars.clear()             # 清空上一帧的雷达数据 
        for d in car.radar_angles:   # 重新发射 5 束雷达
            self.check_radar(game_map, d, car)

    def get_reward(self, car: Car):
        return car.distance / (car.car_size_x / 2)

    def rotate_center(self, image, angle):
        rectangle = image.get_rect()
        rotated_image = pygame.transform.rotate(image, angle)
        rotated_rectangle = rectangle.copy()
        rotated_rectangle.center = rotated_image.get_rect().center
        rotated_image = rotated_image.subsurface(rotated_rectangle).copy()
        return rotated_image
    
    def turn_speed_limit(self, car: Car):
        # 物理前轮转角 δ
        delta_rad = car._steer_smoothed * car.max_steer_rad
        # 归一化转角：x ∈ [0,1]
        x = min(1.0, abs(delta_rad) / car.max_steer_rad)
        # 平滑下降：x=0 -> V_MAX；x=1 -> V_TURN_FLOOR
        return self.v_turn_floor + (car.v_max - self.v_turn_floor) * (1.0 - (x ** self.turn_exp))



# ===================== 仿真主循环（NEAT 回调） =====================
current_generation = 0

def run_simulation(genomes, config):
    track = Track(
        map=MAP,
        map_width=WIDTH,
        map_height=HEIGHT,
        v_turn_floor=V_TURN_FLOOR,
        turn_exp=TURN_EXP,
        limit_smooth_alpha=LIMIT_SMOOTH_ALPHA,
        border_color=BORDER_COLOR
    )
    nets = []
    cars = []

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)

    for idx, (gid, g) in enumerate(genomes):
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        g.fitness = 0.0

        car = Car(
            index=idx,
            car_img=CAR_IMAGE,
            car_size_x=CAR_SIZE_X,
            car_size_y=CAR_SIZE_Y,
            wheelbase_px=WHEELBASE_PX,
            max_steer_deg=MAX_STEER_DEG,
            start_position=START_POSITION,
            radar_max_len=RADAR_MAX_LEN,
            v_min=V_MIN,
            v_max=V_MAX,
            start_facing_angle=180
        )
        cars.append(car)

    clock = pygame.time.Clock()
    generation_font = pygame.font.SysFont("Arial", 30)
    alive_font = pygame.font.SysFont("Arial", 20)
    game_map = pygame.image.load(MAP).convert()

    global current_generation
    current_generation += 1

    counter = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)

        # —— 行为与动力学 —— #
        for i, car in enumerate(cars):
            steer_cmd, accel_cmd = nets[i].activate(car.get_data(INPUT_NORMALIZATION_DENOMINATOR))  # 输出2维：转向, 加速度
            steer_cmd = max(-1.0, min(1.0, steer_cmd))
            accel_cmd = max(-1.0, min(1.0, accel_cmd))

            # 转向平滑
            car._steer_smoothed = car._steer_smoothed * (1 - ALPHA_STEER) + steer_cmd * ALPHA_STEER
            # 物理前轮转角 δ
            delta = car._steer_smoothed * car.max_steer_rad
            

            # 航向角变化（Kinematic Bicycle）
            psi_dot = (car.speed / car.wheelbase_px) * math.tan(delta)  # 弧度/帧
            dpsi_rad = psi_dot

            # 应用航向
            car.angle += math.degrees(dpsi_rad)
            car.angle %= 360.0

            # —— 动态限速（随转向） + 平滑下降 —— #
            v_limit_inst = track.turn_speed_limit(car=car)
            # 对 v_limit 做低通平滑，避免突然跳变
            car._vlimit_smooth = (1 - track.limit_smooth_alpha) * getattr(car, "_vlimit_smooth", car.v_max) \
                                 + track.limit_smooth_alpha * v_limit_inst
            v_limit = car._vlimit_smooth

            # 先按加速度更新
            if accel_cmd >= 0.0:
                car.speed += ACCEL_PER_STEP * accel_cmd
                # 正油门不超过全局 V_MAX
                car.speed = min(car.speed, car.v_max)
            else:
                # 允许主动刹车到 V_MIN
                car.speed += ACCEL_PER_STEP * accel_cmd
                car.speed = max(car.v_min, car.speed)

            # 若超出限速，按固定刹车率渐进下降（不会瞬间砍到限速）
            if car.speed > v_limit:
                car.speed = max(v_limit, car.speed - BRAKE_PER_STEP)

            # 最后做全局夹
            car.speed = max(car.v_min, min(car.v_max, car.speed))

        # —— 存活、更新、奖励 —— #
        still_alive = 0
        for i, car in enumerate(cars):
            if car.is_alive():
                still_alive += 1
                track.update(game_map, car=car)
                genomes[i][1].fitness += track.get_reward(car)

        if still_alive == 0:
            break

        counter += 1
        if counter >= FPS * MAX_SIM_SECONDS:
            break

        # —— 渲染 —— #
        screen.blit(game_map, (0, 0))
        for car in cars:
            if car.is_alive():
                track.draw(screen, car=car)

        text = generation_font.render(f"Generation: {current_generation}", True, TEXT_COLOR)
        text_rect = text.get_rect()
        text_rect.center = (900, 420)
        screen.blit(text, text_rect)

        text = alive_font.render(f"Still Alive: {still_alive}", True, TEXT_COLOR)
        text_rect = text.get_rect()
        text_rect.center = (900, 470)
        screen.blit(text, text_rect)

        elapsed_seconds = counter / FPS
        text = alive_font.render(f"Time: {elapsed_seconds:.1f} s", True, TEXT_COLOR)
        text_rect = text.get_rect()
        text_rect.center = (900, 500)
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

    winner = population.run(run_simulation, 1000)   # 返回当代里 fitness 最高的基因组

    import pickle
    with open("winner.pkl", "wb") as f:
        pickle.dump(winner, f)

    # # 需要时加载
    # with open("winner.pkl", "rb") as f:
    #     winner = pickle.load(f)

    # # 用它构建可执行网络（推理）
    # best_net = neat.nn.FeedForwardNetwork.create(winner, config)

    # # 之后你可以在一个“评估/演示”循环里只跑这一个网络：
    # # obs = car.get_data(); action = best_net.activate(obs); …（不再进化）
