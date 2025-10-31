import math

import pygame

from env_settings import (
    ACCEL_PER_STEP,
    BRAKE_PER_STEP,
    ALPHA_STEER
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

        # 基于 index 生成稳定的“随机颜色”，只给非透明部分上色
        car_rgb = color_from_index(index)                        # 用上面的取色函数
        self.color = car_rgb
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
        self.trail = []

        self.radar_angles = list(range(-90, 120, 45))

    def get_data(self, normalization_denominator: int=30, speed_norm: float=4.5):
        radars = self.radars
        input_size = len(self.radar_angles) # + 1
        ret = [0] * input_size
        for i, radar in enumerate(radars):
            ret[i] = int(radar[1] / normalization_denominator)
        # ret[-1] = self.speed / speed_norm
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
        self.map_surface = pygame.image.load(self.map).convert()

    def draw_car(self, screen, car: Car, plot_radar=False):
        rotated = self.rotate_center(car.sprite, car.angle)
        screen.blit(rotated, car.position)
        # 贴编号（正中央）
        label_rect = car._idx_surf.get_rect(center=(int(car.center[0]), int(car.center[1])))
        screen.blit(car._idx_surf, label_rect)

        if plot_radar:
            self.draw_radar(screen, car)

    def draw_radar(self, screen, car: Car):
        for radar in car.radars:
            pos = radar[0]
            pygame.draw.line(screen, (0, 255, 0), car.center, pos, 1)
            pygame.draw.circle(screen, (0, 255, 0), pos, 5)

    def check_collision(self, car: Car):
        car.alive = True
        for point in car.corners:
            if self.map_surface.get_at((int(point[0]), int(point[1]))) == self.border_color:
                car.alive = False
                break

    def check_radar(self, degree: int, car: Car):
        length = 0
        x = int(car.center[0] + math.cos(math.radians(360 - (car.angle + degree))) * length)
        y = int(car.center[1] + math.sin(math.radians(360 - (car.angle + degree))) * length)

        while not self.map_surface.get_at((x, y)) == self.border_color and length < car.radar_max_len:
            length += 1
            x = int(car.center[0] + math.cos(math.radians(360 - (car.angle + degree))) * length)
            y = int(car.center[1] + math.sin(math.radians(360 - (car.angle + degree))) * length)

        dist = int(math.sqrt((x - car.center[0]) ** 2 + (y - car.center[1]) ** 2))
        car.radars.append([(x, y), dist])


    def update_car_kinematics(self, car: Car, steer_cmd: float, accel_cmd: float):
        # 转向平滑
        car._steer_smoothed = (1 - ALPHA_STEER) * car._steer_smoothed + ALPHA_STEER * steer_cmd

        # 物理前轮转角 δ
        delta = car._steer_smoothed * car.max_steer_rad
        # 航向角变化（Kinematic Bicycle）
        psi_dot = (car.speed / car.wheelbase_px) * math.tan(delta)
        car.angle = (car.angle + math.degrees(psi_dot)) % 360.0

        # 动态限速（随转向）+ 平滑下降 
        v_limit_inst = self.turn_speed_limit(car)
        # v_limit 做低通平滑，避免突然跳变
        car._vlimit_smooth = (1 - self.limit_smooth_alpha) * getattr(car, "_vlimit_smooth", car.v_max) \
                             + self.limit_smooth_alpha * v_limit_inst
        v_limit = car._vlimit_smooth

        # 速度更新
        if accel_cmd >= 0.0:
            car.speed += ACCEL_PER_STEP * accel_cmd
            car.speed = min(car.speed, car.v_max)
        else:
            car.speed += ACCEL_PER_STEP * accel_cmd
            car.speed = max(car.v_min, car.speed)

        # 若超出限速，按固定刹车率渐进下降（不会瞬间砍到限速）
        if car.speed > v_limit:
            car.speed = max(v_limit, car.speed - BRAKE_PER_STEP)

        # 全局夹
        car.speed = max(car.v_min, min(car.v_max, car.speed))

        # 位移
        car.position[0] += math.cos(math.radians(360 - car.angle)) * car.speed
        car.position[1] += math.sin(math.radians(360 - car.angle)) * car.speed
        car.position[0] = max(20, min(self.width - 120, car.position[0]))
        car.position[1] = max(20, min(self.height - 120, car.position[1]))

        # 中心 & 四角
        car.center = [int(car.position[0]) + car.car_size_x / 2, int(car.position[1]) + car.car_size_y / 2]
        length = 0.5 * car.car_size_x
        lt = [car.center[0] + math.cos(math.radians(360 - (car.angle + 30))) * length,
              car.center[1] + math.sin(math.radians(360 - (car.angle + 30))) * length]
        rt = [car.center[0] + math.cos(math.radians(360 - (car.angle + 150))) * length,
              car.center[1] + math.sin(math.radians(360 - (car.angle + 150))) * length]
        lb = [car.center[0] + math.cos(math.radians(360 - (car.angle + 210))) * length,
              car.center[1] + math.sin(math.radians(360 - (car.angle + 210))) * length]
        rb = [car.center[0] + math.cos(math.radians(360 - (car.angle + 330))) * length,
              car.center[1] + math.sin(math.radians(360 - (car.angle + 330))) * length]
        car.corners = [lt, rt, lb, rb]

        # 碰撞
        self.check_collision(car)

        # 雷达
        car.radars.clear()  # 清空上一帧的雷达数据 
        for d in car.radar_angles:  # 重新发射 5 束雷达
            self.check_radar(d, car)

        # 数据累计
        car.distance += car.speed
        car.time += 1

    def get_reward(self, car: Car):
        return (car.distance / (car.car_size_x / 2)) / car.time

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

