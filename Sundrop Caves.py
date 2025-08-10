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


# ---------- Scores ----------
def load_scores():
    if not os.path.exists(SCORES_FILE):
        return []
    with open(SCORES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_scores(scores):
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f)


def update_top_scores(player):
    scores = load_scores()
    scores.append(
        {
            "name": player["name"],
            "days": player["day"] - 1,
            "steps": player["steps"],
            "GP": player["GP"],
        }
    )
    scores.sort(key=lambda e: (e["days"], e["steps"], -e["GP"]))
    save_scores(scores[:5])


# ---------- Game mechanics ----------
def sell_ore(player, source, amounts=None):
    # source: "backpack" or "warehouse"
    # amounts: dict specifying amounts to sell per mineral (optional). If None sell all from source.
    if source == "backpack":
        totals = {"copper": player["copper"], "silver": player["silver"], "gold": player["gold"]}
    else:
        totals = player["warehouse"].copy()

    if amounts:
        # validate amounts
        for k, v in amounts.items():
            if v < 0 or v > totals.get(k, 0):
                print(f"Invalid amount for {k}.")
                return
        sell_map = amounts
    else:
        sell_map = {k: totals.get(k, 0) for k in totals}

    gained = 0
    for m, qty in sell_map.items():
        if qty <= 0:
            continue
        price = randint(*mineral_price_ranges[m])
        value = price * qty
        print(f"You sell {qty} {m} ore for {value} GP.")
        gained += value
        if source == "backpack":
            player[m] -= qty
        else:
            player["warehouse"][m] -= qty
    player["GP"] += gained
    if gained == 0:
        print("Nothing sold.")


def place_portal(player):
    lvl = player["level"]
    player["portal_positions"][lvl] = (player["x"], player["y"])
    print("\nYou place your portal stone here and zap back to town.\n")
    # Selling automatic when you zap back from the mine: sell all backpack items
    sell_ore(player, "backpack")
    print(f"You now have {player['GP']} GP!\n")
    player["day"] += 1
    player["turns"] = TURNS_PER_DAY
    # return to town coordinates
    player["x"], player["y"] = 0, 0
    player["level"] = 1  # when in town, level resets to 1 for next enter


def can_mine(symbol, pickaxe):
    return (
        symbol == "C"
        or (symbol == "S" and pickaxe >= 2)
        or (symbol == "G" and pickaxe >= 3)
    )


def mine_tile(map_grid, fog, player):
    sym = map_grid[player["y"]][player["x"]]
    if sym not in mineral_names:
        return False
    m = mineral_names[sym]
    pieces = randint(*mineral_piece_ranges[m])
    load = player["copper"] + player["silver"] + player["gold"]
    space = player["capacity"] - load
    if space <= 0:
        print("You can't carry any more, so you can't go that way.")
        return False
    take = min(pieces, space)
    print(f"\nYou mined {take} piece(s) of {m}.")
    if take < pieces:
        print(f"...but you can only carry {take} more piece(s)!")
    player[m] += take
    map_grid[player["y"]][player["x"]] = " "
    fog[player["y"]][player["x"]] = " "
    return True


def replenish_day(map_maps):
    # map_maps: dict level->map_grid
    for lvl in map_maps:
        grid = map_maps[lvl]
        for y in range(len(grid)):
            for x in range(len(grid[0])):
                if grid[y][x] == " " and random.random() < 0.2:
                    r = random.random()
                    grid[y][x] = "C" if r < 0.7 else ("S" if r < 0.95 else "G")

# ---------- Menus & UI ----------
def intro():
    print("---------------- Welcome to Sundrop Caves! ----------------")
    print("You spent all your money to get the deed to a mine, a small")
    print("  backpack, a simple pickaxe and a magical portal stone.\n")
    print(f"How quickly can you get the {WIN_GP} GP you need to retire")
    print("  and live happily ever after?")
    print("-----------------------------------------------------------")


def main_menu():
    print("\n--- Main Menu ----")
    print("(N)ew game")
    print("(L)oad saved game")
    print("(H)igh scores")
    print("(Q)uit")
    print("------------------")


def town_menu(player):
    print(f"\nDAY {player['day']}")
    print("----- Sundrop Town -----")
    print("(B)uy stuff")
    print("See Player (I)nformation")
    print("See Mine (M)ap")
    print("(E)nter mine")
    print("(S)ell ore")
    print("(W)arehouse")
    print("Sa(V)e game")
    print("(Q)uit to main menu")
    print("------------------------")


def shop(player):
    while True:
        print("\n----------------------- Shop Menu -------------------------")
        if player["pickaxe"] < 3:
            lvl = player["pickaxe"] + 1
            metal = "silver" if lvl == 2 else "gold"
            print(
                f"(P)ickaxe upgrade to Level {lvl} to mine {metal} ore for {PICKAXE_UPGRADE_PRICES[lvl]} GP"
            )
        bp_cost = player["capacity"] * 2
        print(
            f"(B)ackpack upgrade to carry {player['capacity']+2} items for {bp_cost} GP"
        )
        if not player["torch"]:
            print(f"(T)orch (magic) purchase for {TORCH_PRICE} GP (increases viewport to 5x5)")
        print("(L)eave shop")
        print("-----------------------------------------------------------")
        print(f"GP: {player['GP']}")
        print("-----------------------------------------------------------")
        c = input("Your choice? ").strip().lower()
        if c == "p" and player["pickaxe"] < 3:
            lvl = player["pickaxe"] + 1
            cost = PICKAXE_UPGRADE_PRICES[lvl]
            if player["GP"] >= cost:
                player["GP"] -= cost
                player["pickaxe"] = lvl
                print("Congratulations!")
            else:
                print("You do not have enough GP for that upgrade.")
        elif c == "b":
            if player["GP"] >= bp_cost:
                player["GP"] -= bp_cost
                player["capacity"] += 2
                print("Congratulations!")
            else:
                print("You do not have enough GP for that upgrade.")
        elif c == "t" and not player["torch"]:
            if player["GP"] >= TORCH_PRICE:
                player["GP"] -= TORCH_PRICE
                player["torch"] = True
                print("You purchased the Magic Torch! Your viewport is now 5x5.")
            else:
                print("You do not have enough GP for that upgrade.")
        elif c == "l":
            break
        else:
            print("Invalid choice.")

