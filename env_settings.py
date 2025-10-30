import math


# ===================== 基本设置 =====================
MAP = 'K1_Real.png'
CAR_IMAGE = 'car.png'

MAX_SIM_SECONDS = 250
FPS = 60
dt = 1.0 / FPS


V_MIN = 2
V_MAX = 4.5
SPEED_NORM = 0.2
ACCEL_PER_STEP     = V_MAX / (1.6 * FPS)    # 1.6 秒 0->V_MAX, 加速度（每帧速度增长量）。这里设定为“1.65秒内从 0 加到 V_MAX”。

"""
含义：打满方向（最大转向角）时允许的最低最高速度。
也就是“弯中限速的底线”。

影响：

值越大 → 弯中最高速度越高，车更容易飘出弯（高速转向）。

值越小 → 弯中会自动降速更多，更稳但慢。

✅ 想让弯中速度更高 → 增大它，比如 1.5 或 2.0。
"""
V_TURN_FLOOR       = 1.0     # 打满方向时的最高速下限


"""
含义：弯速曲线指数（弯中限速随转向角变化的形状）。

当 TURN_EXP 较小（≈1）时 → 限速变化平缓，大部分转角都能高速。

当 TURN_EXP 较大（>2）时 → 一转方向就大幅降速，弯内更慢。

✅ 想弯中速度更高 → 减小它，比如 1.2 或 1.3。
"""
TURN_EXP           = 1.6     # 曲线形状：越大弯内越慢；1.6~2.5 之间调


"""
含义：当当前速度超过允许限速时，每帧自动减速的幅度。

影响：

越大 → 超速后马上被“刹”下来（响应快）。

越小 → 会滑行更久再慢慢降下来（更自然）。

✅ 如果你希望弯中速度保持更高，可以略减小这个，比如 1.0 * ACCEL_PER_STEP。
"""
BRAKE_PER_STEP     = 2.0 * ACCEL_PER_STEP   # 超限时每帧自动减速量（平滑降速的力度）


"""
含义：限速的平滑系数。
控制限速值（v_limit）的更新速度。

影响：

大（如0.8） → 反应快，车刚打方向就立刻降速。

小（如0.2） → 慢慢降速，更“惯性”更自然。

✅ 想要弯中速度更高、降速更平缓 → 减小它，如 0.2。
"""
LIMIT_SMOOTH_ALPHA = 0.4     # 限速的低通平滑（0~1，越大响应越快）


"""
含义：转向输入平滑程度。

影响：

小（如 0.2） → 转向平滑、不灵敏。

大（如 0.8） → 转向响应快，容易抖。

和限速无直接关系，主要影响“驾驶感觉”。
"""
ALPHA_STEER        = 0.5     # 转向平滑（低通滤波）系数

# 画面/碰撞
if MAP == "K1_Real.png":
    WIDTH, HEIGHT = 1920, 1080
    TEXT_COLOR   = (255, 255, 255)
    START_POSITION   = [950, 630]
    STARTING_ANGLE   = 180
    # 车模型参数（像素为单位）
    CAR_SIZE_X, CAR_SIZE_Y = 60, 60
    WHEELBASE_PX   = 50.0      # 轴距（按你的车图大小和地图比例调）
    MAX_STEER_DEG  = 30.0      # 最大前轮转角（物理转向角，不是航向变化）
    MAX_STEER_RAD  = math.radians(MAX_STEER_DEG)
    RADAR_MAX_LEN = 600
    INPUT_NORMALIZATION_DENOMINATOR = 60 #  RADAR_MAX_LEN/INPUT_NORMALIZATION_DENOMINATOR 我发现不一定输入一定要在 0,1之间，如果限制在0,1之间，车的速度涨的很慢
else:
    WIDTH, HEIGHT = 1920, 1080
    TEXT_COLOR   = (0, 0, 0) # other map
    START_POSITION   = [830, 920]
    STARTING_ANGLE   = 0
    CAR_SIZE_X, CAR_SIZE_Y = 60, 60
    WHEELBASE_PX   = 50.0      # 轴距（按你的车图大小和地图比例调）
    MAX_STEER_DEG  = 30.0      # 最大前轮转角（物理转向角，不是航向变化）
    MAX_STEER_RAD  = math.radians(MAX_STEER_DEG)
    RADAR_MAX_LEN = 800
    INPUT_NORMALIZATION_DENOMINATOR = 80 #  RADAR_MAX_LEN/INPUT_NORMALIZATION_DENOMINATOR 我发现不一定输入一定要在 0,1之间，如果限制在0,1之间，车的速度涨的很慢


PLOT_RADAR = False
BORDER_COLOR = (255, 255, 255, 255)  # 碰撞的颜色（白色）

TOP_N_GENO = 100
