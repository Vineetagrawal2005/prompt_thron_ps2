import numpy as np


def reconstruct_geometry(walls, image_size):
    width, height = image_size
    classified_walls = []
    for w in walls:
        x1, y1, x2, y2 = w
        wtype = _classify_wall(x1, y1, x2, y2, width, height)
        length = round(np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2), 1)
        classified_walls.append({"coords": [x1, y1, x2, y2], "type": wtype, "length": length})
    rooms = _extract_rooms(walls, image_size)
    return {"rooms": rooms, "classified_walls": classified_walls}


def _classify_wall(x1, y1, x2, y2, width, height, margin=30):
    on_left   = x1 < margin and x2 < margin
    on_right  = x1 > width - margin and x2 > width - margin
    on_top    = y1 < margin and y2 < margin
    on_bottom = y1 > height - margin and y2 > height - margin
    if on_left or on_right or on_top or on_bottom:
        return "load_bearing"
    length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    if length > min(width, height) * 0.45:
        return "load_bearing"
    return "partition"


def _extract_rooms(walls, image_size):
    width, height = image_size
    scale = 4
    gw, gh = width // scale, height // scale
    grid = np.zeros((gh, gw), dtype=np.uint8)
    for w in walls:
        x1, y1, x2, y2 = [c // scale for c in w]
        x1, y1 = max(0, min(gw-1, x1)), max(0, min(gh-1, y1))
        x2, y2 = max(0, min(gw-1, x2)), max(0, min(gh-1, y2))
        _draw_line(grid, x1, y1, x2, y2)
    visited = np.zeros_like(grid)
    rooms = []
    for sy in range(1, gh - 1):
        for sx in range(1, gw - 1):
            if grid[sy, sx] == 0 and visited[sy, sx] == 0:
                region, size = _flood_fill(grid, visited, sx, sy, gw, gh)
                if size > 200:
                    poly = _region_to_polygon(region, scale)
                    if poly:
                        rooms.append(poly)
    return rooms


def _draw_line(grid, x1, y1, x2, y2):
    gh, gw = grid.shape
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx - dy
    for _ in range(max(dx, dy) + 200):
        for ty in range(-1, 2):
            for tx in range(-1, 2):
                nx, ny = x1 + tx, y1 + ty
                if 0 <= nx < gw and 0 <= ny < gh:
                    grid[ny, nx] = 1
        if x1 == x2 and y1 == y2:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x1 += sx
        if e2 < dx:
            err += dx
            y1 += sy


def _flood_fill(grid, visited, sx, sy, gw, gh):
    stack = [(sx, sy)]
    region = []
    visited[sy, sx] = 1
    while stack:
        x, y = stack.pop()
        region.append((x, y))
        if len(region) > 50000:
            break
        for nx, ny in [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
            if 0 <= nx < gw and 0 <= ny < gh and grid[ny, nx] == 0 and visited[ny, nx] == 0:
                visited[ny, nx] = 1
                stack.append((nx, ny))
    return region, len(region)


def _region_to_polygon(region, scale):
    if not region:
        return None
    xs = [p[0] for p in region]
    ys = [p[1] for p in region]
    x_min, x_max = min(xs) * scale, max(xs) * scale
    y_min, y_max = min(ys) * scale, max(ys) * scale
    return [[float(x_min),float(y_min)],[float(x_max),float(y_min)],
            [float(x_max),float(y_max)],[float(x_min),float(y_max)],[float(x_min),float(y_min)]]
