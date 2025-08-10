import os
import json
import random
from random import randint

# ---------- Configuration ----------
MAP_FILES = {1: "level1.txt", 2: "level2.txt"}
SAVE_FILE = "savegame.json"
SCORES_FILE = "scores.json"

TURNS_PER_DAY = 20
WIN_GP = 800  # increased because of second level
INITIAL_CAPACITY = 10

mineral_names = {"C": "copper", "S": "silver", "G": "gold"}
mineral_piece_ranges = {"copper": (1, 5), "silver": (1, 3), "gold": (1, 2)}
mineral_price_ranges = {"copper": (1, 3), "silver": (5, 8), "gold": (10, 18)}

PICKAXE_UPGRADE_PRICES = {2: 50, 3: 150}
TORCH_PRICE = 50  # magic torch price


# ---------- Utilities ----------
def in_bounds(x, y, grid):
    return 0 <= y < len(grid) and 0 <= x < len(grid[0])


# ---------- Map loading ----------
def load_map_file(filename):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Map file {filename} not found")
    with open(filename, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]
    width = max(len(line) for line in lines)
    grid = [list(line.ljust(width)) for line in lines]
    return grid


def create_fog(map_grid):
    return [["?" for _ in row] for row in map_grid]


def clear_fog_around(fog, map_grid, px, py, radius=1):
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx, ny = px + dx, py + dy
            if in_bounds(nx, ny, map_grid):
                fog[ny][nx] = map_grid[ny][nx]