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

# ---------- Drawing ----------
def draw_map(map_grid, fog, show_portal=None, show_miner=None):
    width = len(map_grid[0])
    print("+" + "-" * width + "+")
    for y in range(len(map_grid)):
        row = "|"
        for x in range(width):
            if show_miner and (x, y) == show_miner:
                row += "M"
            elif show_portal and (x, y) == show_portal:
                row += "P"
            else:
                row += fog[y][x]
        row += "|"
        print(row)
    print("+" + "-" * width + "+")


def draw_view(map_grid, fog, px, py, torch=False):
    # torch True -> 5x5 (radius 2), else 3x3 (radius 1)
    radius = 2 if torch else 1
    size = radius * 2 + 1
    border = "+" + "-" * size + "+"
    print(border)
    for dy in range(-radius, radius + 1):
        row = "|"
        for dx in range(-radius, radius + 1):
            nx, ny = px + dx, py + dy
            if not in_bounds(nx, ny, map_grid):
                row += "#"
            elif dx == 0 and dy == 0:
                row += "M"
            else:
                ch = fog[ny][nx]
                # When revealed show the underlying map character (minerals as letters),
                # when not revealed show space in small view (matching PDF style)
                row += " " if ch == "?" else ch
        row += "|"
        print(row)
    print(border)

# ---------- Player / State ----------
def initialize_player():
    return {
        "name": "",
        "level": 1,  # current mine level (1 or 2)
        "x": 0,
        "y": 0,
        # portal positions per level stored as dict {level: (x,y)}
        "portal_positions": {1: (0, 0), 2: (0, 0)},
        "capacity": INITIAL_CAPACITY,
        "copper": 0,
        "silver": 0,
        "gold": 0,
        "warehouse": {"copper": 0, "silver": 0, "gold": 0},
        "GP": 0,
        "day": 1,
        "steps": 0,
        "turns": TURNS_PER_DAY,
        "pickaxe": 1,
        "torch": False,
    }


# ---------- Save / Load ----------
def save_game(map_grids, fogs, player):
    # map_grids: dict level->map_grid ; fogs: dict level->fog
    data = {
        "maps": {lvl: ["".join(row) for row in map_grids[lvl]] for lvl in map_grids},
        "fogs": {lvl: ["".join(row) for row in fogs[lvl]] for lvl in fogs},
        "player": player,
    }
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print("\nGame saved.")


def load_game():
    if not os.path.exists(SAVE_FILE):
        print("No saved game found.")
        return None
    with open(SAVE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    maps = {int(k): [list(row) for row in data["maps"][k]] for k in data["maps"]}
    fogs = {int(k): [list(row) for row in data["fogs"][k]] for k in data["fogs"]}
    player = data["player"]
    return maps, fogs, player

