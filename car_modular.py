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
    SPEED_NORM,
    V_TURN_FLOOR,
    TURN_EXP,
    LIMIT_SMOOTH_ALPHA,
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
    TOP_N_GENO
)

from src.my_env import (
    Car,
    Track
)


# ===================== 仿真主循环（NEAT 回调） =====================
current_generation = 0

def run_simulation(genomes, config):
    nets = []
    cars = []

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT)) # , pygame.FULLSCREEN)

    track = Track(
        map=MAP,
        map_width=WIDTH,
        map_height=HEIGHT,
        v_turn_floor=V_TURN_FLOOR,
        turn_exp=TURN_EXP,
        limit_smooth_alpha=LIMIT_SMOOTH_ALPHA,
        border_color=BORDER_COLOR
    )

    for idx, (gid, g) in enumerate(genomes):
        net = neat.nn.FeedForwardNetwork.create(g, config)
        nets.append(net)
        g.fitness = 0.0

        car = Car(
            index=gid, # gid 是完全对应某一辆车 跨代不变的标识
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
        cars.append(car)

    clock = pygame.time.Clock()
    generation_font = pygame.font.SysFont("Arial", 30)
    alive_font = pygame.font.SysFont("Arial", 20)

    global current_generation
    current_generation += 1

    counter = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit(0)

        still_alive = 0
        # —— 行为与动力学 —— #
        for i, car in enumerate(cars):
            steer_cmd, accel_cmd = nets[i].activate(car.get_data(INPUT_NORMALIZATION_DENOMINATOR, SPEED_NORM))  # 输出2维：转向, 加速度
            steer_cmd = max(-1.0, min(1.0, steer_cmd))
            accel_cmd = max(-1.0, min(1.0, accel_cmd))

            # —— 存活、更新、奖励 —— #
            if car.is_alive():
                still_alive += 1
                track.update_car_kinematics(car, steer_cmd, accel_cmd)
                genomes[i][1].fitness += track.get_reward(car)

        if still_alive == 0:
            break

        counter += 1
        if counter >= FPS * MAX_SIM_SECONDS:
            break

        # —— 渲染 —— #
        screen.blit(track.map_surface, (0, 0))
        for car in cars:
            if car.is_alive():
                track.draw_car(screen, car=car, plot_radar=PLOT_RADAR)

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

    import pickle, copy
    # —— 保存全局最优 winner —— 
    with open("winner.pkl", "wb") as f:
        pickle.dump(winner, f)

    # —— 从 stats 拿每代最优，然后：深拷贝、去重（同 key 取最高 fitness）、再取前 N —— 
    raw_best = [g for g in stats.most_fit_genomes if g is not None]

    # 去重：同一 key 只保留 fitness 最高的那个
    best_by_key = {}
    for g in raw_best:
        if (g.key not in best_by_key) or (g.fitness > best_by_key[g.key].fitness):
            best_by_key[g.key] = g
    # 深拷贝，避免后续引用问题
    dedup_copies = [copy.deepcopy(g) for g in best_by_key.values()]

    # 1️⃣ 按 fitness 排序，取前 N
    # 排序取前 N
    topN = sorted(dedup_copies, key=lambda g: g.fitness, reverse=True)[:TOP_N_GENO]

    # 2️⃣ 保存前 N 个个体
    with open("topN_genomes.pkl", "wb") as f:
        pickle.dump(topN, f)
