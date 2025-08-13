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
# Creates a “fog-of-war” layer with ? covering all squares.


def clear_fog_around(fog, map_grid, px, py, radius=1):
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx, ny = px + dx, py + dy
            if in_bounds(nx, ny, map_grid):
                fog[ny][nx] = map_grid[ny][nx]
# Reveals tiles around the player’s position within radius.


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
# Draws the full map with borders.
# Uses fog layer so unrevealed tiles show ?.
# Can highlight the portal (P) and player (M).

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
# Draws small viewport (3×3 or 5×5 if torch owned).
# Shows M in the middle, unrevealed tiles as blank spaces, out-of-bounds as #.

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
# Creates a dictionary with all player stats.


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
# Saves maps, fog states, and player dictionary to JSON.


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
# Loads saved data back into game variables.


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

# 3 of these Reads/writes from scores.json, Stores top 5 scores, sorted by days → steps → GP.


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
# Sells ore from backpack or warehouse.
# Random price within range per mineral type.
# Adds GP to player’s total.c


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
# Sets portal position for current level.
# Sells all backpack ore automatically.
# Returns player to town, resets turns, moves to day+1.

def can_mine(symbol, pickaxe):
    return (
        symbol == "C"
        or (symbol == "S" and pickaxe >= 2)
        or (symbol == "G" and pickaxe >= 3)
    )
# Checks if player’s pickaxe can mine a mineral type.


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
# Mines ore at player’s position.
# Random pieces taken (limited by backpack space).
# Removes mineral from map and fog.


def replenish_day(map_maps):
    # map_maps: dict level->map_grid
    for lvl in map_maps:
        grid = map_maps[lvl]
        for y in range(len(grid)):
            for x in range(len(grid[0])):
                if grid[y][x] == " " and random.random() < 0.2:
                    r = random.random()
                    grid[y][x] = "C" if r < 0.7 else ("S" if r < 0.95 else "G")
# Bonus feature: 20% chance that empty tiles regenerate minerals.

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


# ---------- Town actions ----------
def player_info(player):
    print("\n----- Player Information -----")
    print(f"Name: {player['name']}")
    ppos = player["portal_positions"].get(player["level"], (0, 0))
    print(f"Portal position (current level {player['level']}): ({ppos[0]}, {ppos[1]})")
    print(f"Pickaxe level: {player['pickaxe']}")
    print(f"Gold: {player['gold']}")
    print(f"Silver: {player['silver']}")
    print(f"Copper: {player['copper']}")
    load = player["copper"] + player["silver"] + player["gold"]
    print("------------------------------")
    print(f"Load: {load} / {player['capacity']}")
    print("------------------------------")
    print(f"GP: {player['GP']}")
    print("------------------------------")
    print(f"Warehouse - Gold: {player['warehouse']['gold']}, Silver: {player['warehouse']['silver']}, Copper: {player['warehouse']['copper']}")
    print("------------------------------")
    print(f"Steps taken: {player['steps']}")
    print("------------------------------")
    print(f"Torch owned: {'Yes' if player['torch'] else 'No'}")
    print("------------------------------")


def warehouse_menu(player):
    while True:
        print("\n----- Warehouse Menu -----")
        print("(S)tore all backpack ore in warehouse")
        print("(R)etrieve ore from warehouse to backpack")
        print("(V)iew warehouse contents")
        print("(L)eave warehouse")
        print("--------------------------")
        c = input("Your choice? ").strip().lower()
        if c == "s":
            # move as much as capacity allows from backpack to warehouse
            carried = player["copper"] + player["silver"] + player["gold"]
            to_store = {"copper": player["copper"], "silver": player["silver"], "gold": player["gold"]}
            if carried == 0:
                print("You have nothing to store.")
                continue
            for k, v in to_store.items():
                player["warehouse"][k] += v
                player[k] -= v
            print("All carried ore moved to warehouse.")
        elif c == "r":
            # retrieve as much as backpack capacity allows (LIFO: gold, silver, copper)
            space = player["capacity"] - (player["copper"] + player["silver"] + player["gold"])
            if space <= 0:
                print("You have no space in your backpack.")
                continue
            for k in ("gold", "silver", "copper"):
                take = min(player["warehouse"][k], space)
                if take > 0:
                    player["warehouse"][k] -= take
                    player[k] += take
                    space -= take
            print("Retrieved ore from warehouse into backpack where possible.")
        elif c == "v":
            w = player["warehouse"]
            print(f"Warehouse contents - Gold: {w['gold']}, Silver: {w['silver']}, Copper: {w['copper']}")
        elif c == "l":
            return
        else:
            print("Invalid choice.")


def sell_menu(player):
    while True:
        print("\n----- Sell Menu -----")
        print("(B)ackpack - sell all ore in backpack")
        print("(W)arehouse - sell from warehouse")
        print("(L)eave sell menu")
        print("---------------------")
        c = input("Your choice? ").strip().lower()
        if c == "b":
            sell_ore(player, "backpack")
        elif c == "w":
            sell_ore(player, "warehouse")
        elif c == "l":
            return
        else:
            print("Invalid choice.")


# ---------- Mine loop ----------
def enter_mine(map_maps, fogs, player):
    lvl = player["level"]
    # when entering from town, if at town coords (0,0) appear at stored portal pos for that level
    if player["x"] == 0 and player["y"] == 0:
        px, py = player["portal_positions"].get(lvl, (0, 0))
        player["x"], player["y"] = px, py
    current_map = map_maps[lvl]
    current_fog = fogs[lvl]

    # reveal around player
    clear_fog_around(current_fog, current_map, player["x"], player["y"], radius=2 if player["torch"] else 1)

    while True:
        print("\n---------------------------------------------------")
        print(f"                       DAY {player['day']}")
        print("---------------------------------------------------\n")
        draw_view(current_map, current_fog, player["x"], player["y"], torch=player["torch"])
        load_amt = player["copper"] + player["silver"] + player["gold"]
        print(
            f"Turns left: {player['turns']}    Load: {load_amt} / {player['capacity']}    Steps: {player['steps']}"
        )
        print("\n(WASD) to move\n")
        print("(M)ap, (I)nformation, (P)ortal, (Q)uit to main menu")
        act = input("\nAction? ").strip().lower()
        if act in ("w", "a", "s", "d"):
            player["turns"] -= 1
            dx, dy = (0, -1) if act == "w" else (0, 1) if act == "s" else (-1, 0) if act == "a" else (1, 0)
            nx, ny = player["x"] + dx, player["y"] + dy
            if not in_bounds(nx, ny, current_map):
                print("You cannot move past the edge of the map.")
            else:
                tile = current_map[ny][nx]
                # If stepping on portal town tile 'T' -> place portal, sell, return to town
                if tile == "T":
                    player["x"], player["y"] = nx, ny
                    place_portal(player)
                    # replenish all maps
                    replenish_day(map_maps)
                    return
                # If door 'D' leads to Level 2 (only if there is a level2 map file loaded)
                if tile == "D":
                    # move the player into that tile and switch to level 2 (or back to 1)
                    player["x"], player["y"] = nx, ny
                    # store portal for current level before switching
                    player["portal_positions"][lvl] = (player["x"], player["y"])
                    # toggle level: if at 1 go to 2; if at 2 and D leads back to 1, go to 1
                    new_level = 2 if lvl == 1 else 1
                    if new_level not in map_maps:
                        print("That door is locked.")
                    else:
                        player["level"] = new_level
                        # place player at corresponding entrance in the new map:
                        # we'll put them at (0,0) or stored portal for that level
                        px, py = player["portal_positions"].get(new_level, (0, 0))
                        player["x"], player["y"] = px, py
                        print(f"You pass through a door and enter mine level {new_level}.")
                        # refresh references
                        lvl = player["level"]
                        current_map = map_maps[lvl]
                        current_fog = fogs[lvl]
                        clear_fog_around(current_fog, current_map, player["x"], player["y"], radius=2 if player["torch"] else 1)
                elif tile in mineral_names:
                    if not can_mine(tile, player["pickaxe"]):
                        print("You can't go there — you can't mine that mineral yet.")
                    else:
                        player["x"], player["y"] = nx, ny
                        if mine_tile(current_map, current_fog, player):
                            player["steps"] += 1
                            clear_fog_around(current_fog, current_map, player["x"], player["y"], radius=2 if player["torch"] else 1)
                else:
                    # empty or other tile: move normally
                    player["x"], player["y"] = nx, ny
                    player["steps"] += 1
                    clear_fog_around(current_fog, current_map, player["x"], player["y"], radius=2 if player["torch"] else 1)
            if player["turns"] <= 0:
                print("\nYou are exhausted.")
                place_portal(player)
                replenish_day(map_maps)
                return
        elif act == "m":
            draw_map(current_map, current_fog, show_portal=player["portal_positions"].get(lvl), show_miner=(player["x"], player["y"]))
        elif act == "i":
            player_info(player)
        elif act == "p":
            player["turns"] -= 1
            # store current pos as portal for this level
            player["portal_positions"][lvl] = (player["x"], player["y"])
            place_portal(player)
            replenish_day(map_maps)
            return
        elif act == "q":
            if input("Quit to main menu? (Y/N) ").strip().lower() == "y":
                # do not sell; simply go back to town (position 0,0)
                # store portal
                player["portal_positions"][lvl] = (player["x"], player["y"])
                player["x"], player["y"] = 0, 0
                player["level"] = 1
                return
        else:
            print("Invalid action.")
# Handles all gameplay in the mine


# ---------- Main Flow ----------
def main():
    # load maps for levels available
    maps = {}
    fogs = {}
    # always try to load level1; level2 optional
    try:
        maps[1] = load_map_file(MAP_FILES[1])
        fogs[1] = create_fog(maps[1])
    except FileNotFoundError as e:
        print(str(e))
        return
    if os.path.exists(MAP_FILES.get(2, "")):
        maps[2] = load_map_file(MAP_FILES[2])
        fogs[2] = create_fog(maps[2])

    player = initialize_player()

    intro()
    state = "main"

    while True:
        if state == "main":
            main_menu()
            c = input("Your choice? ").strip().lower()
            if c == "n":
                name = input("\nGreetings, miner! What is your name? ").strip()
                if not name:
                    name = "Anonymous"
                player = initialize_player()
                player["name"] = name
                # reset maps & fogs
                maps[1] = load_map_file(MAP_FILES[1])
                fogs[1] = create_fog(maps[1])
                if 2 in MAP_FILES and os.path.exists(MAP_FILES[2]):
                    maps[2] = load_map_file(MAP_FILES[2])
                    fogs[2] = create_fog(maps[2])
                # clear fog at town start pos for level 1 only
                clear_fog_around(fogs[1], maps[1], 0, 0)
                print(f"\nPleased to meet you, {player['name']}. Welcome to Sundrop Town!\n")
                state = "town"
            elif c == "l":
                loaded = load_game()
                if loaded:
                    maps, fogs, player = loaded
                    # ensure keys are ints
                    maps = {int(k): maps[k] for k in maps}
                    fogs = {int(k): fogs[k] for k in fogs}
                    print("\nGame loaded. Returning to town.")
                    state = "town"
                else:
                    # load failed message printed inside load_game
                    pass
            elif c == "h":
                scores = load_scores()
                if scores:
                    print("\n--- Top Scores ---")
                    for i, s in enumerate(scores, 1):
                        print(f"{i}. {s['name']} - Days: {s['days']}, Steps: {s['steps']}, GP: {s['GP']}")
                    print("------------------")
                else:
                    print("\nNo high scores yet.")
            elif c == "q":
                print("Goodbye!")
                break
            else:
                print("Invalid choice.")
        elif state == "town":
            town_menu(player)
            c = input("Your choice? ").strip().lower()
            if c == "b":
                shop(player)
            elif c == "i":
                player_info(player)
            elif c == "m":
                # show level1 map with portal for level1; show miner at town (0,0)
                draw_map(maps[1], fogs[1], show_portal=player["portal_positions"].get(1, (0, 0)), show_miner=(0, 0))
            elif c == "e":
                enter_mine(maps, fogs, player)
                if player["GP"] >= WIN_GP:
                    print("\n-------------------------------------------------------------")
                    print(f"Woo-hoo! Well done, {player['name']}, you have {player['GP']} GP!")
                    print("You now have enough to retire and play video games every day.")
                    print(f"And it only took you {player['day']} days and {player['steps']} steps! You win!")
                    print("-------------------------------------------------------------\n")
                    update_top_scores(player)
                    state = "main"
                else:
                    state = "town"
            elif c == "s":
                sell_menu(player)
            elif c == "w":
                warehouse_menu(player)
            elif c == "v":
                save_game(maps, fogs, player)
            elif c == "q":
                if input("Quit to main menu? (Y/N) ").strip().lower() == "y":
                    state = "main"
            else:
                print("Invalid choice.")


if __name__ == "__main__":
    main()