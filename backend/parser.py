import cv2
import numpy as np


def parse_floor_plan(image_path):
    """
    Parse a floor plan image using OpenCV.
    Returns walls with attached windows.
    Falls back to sample geometry if CV fails.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Could not load image")

        h, w = img.shape[:2]

        # Normalize image to a 800x600 canvas for consistent output
        scale = min(800 / w, 600 / h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h))

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Canny edge detection
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

        # Remove text and small components using connected components
        edges = _filter_components(edges, min_area=150, min_dim=20)

        # Dilate edges slightly to connect nearby lines
        kernel = np.ones((2, 2), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

        # HoughLinesP to detect line segments
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=40,
            minLineLength=20,
            maxLineGap=10,
        )

        if lines is None or len(lines) == 0:
            raise ValueError("No lines detected")

        wall_candidates = []
        window_candidates = []

        # Keep only approximately horizontal/vertical lines; remove diagonals
        for line in lines:
            x1, y1, x2, y2 = map(int, line[0])
            orientation = _line_orientation(x1, y1, x2, y2)
            if orientation is None:
                continue
            length = np.hypot(x2 - x1, y2 - y1)

            # Window detection: small segment close to a longer main wall
            if length < 40:
                window_candidates.append([x1, y1, x2, y2])
            else:
                wall_candidates.append([x1, y1, x2, y2])

        # Deduplicate walls and windows
        wall_candidates = _deduplicate_lines(wall_candidates, threshold=12)
        window_candidates = _deduplicate_lines(window_candidates, threshold=8)

        # Attach windows to nearby walls
        walls_with_windows = []
        for wall in wall_candidates:
            walls_with_windows.append({
                "coords": wall,
                "type": "partition",  # type will be updated in app by geometry classification
                "windows": []
            })

        for window in window_candidates:
            target = _find_closest_wall(window, wall_candidates, max_dist=18)
            if target is not None:
                for wall in walls_with_windows:
                    if wall["coords"] == target:
                        wall["windows"].append(window)
                        break

        return {
            "walls": walls_with_windows,
            "image_size": [new_w, new_h],
            "source": "opencv",
        }

    except Exception as e:
        print(f"[Parser] OpenCV failed ({e}), using fallback geometry.")
        return _fallback_geometry()


def _deduplicate_lines(walls, threshold=8):
    """Remove near-duplicate lines using midpoint and endpoint closeness."""
    unique = []
    for w in walls:
        x1, y1, x2, y2 = w
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        found = False
        for u in unique:
            ux1, uy1, ux2, uy2 = u
            umid_x, umid_y = (ux1 + ux2) / 2, (uy1 + uy2) / 2
            if abs(mid_x - umid_x) < threshold and abs(mid_y - umid_y) < threshold:
                found = True
                break
            if (
                abs(x1 - ux1) < threshold
                and abs(y1 - uy1) < threshold
                and abs(x2 - ux2) < threshold
                and abs(y2 - uy2) < threshold
            ):
                found = True
                break
        if not found:
            unique.append(w)
    return unique


def _filter_components(edge_img, min_area=150, min_dim=20):
    """Remove text/noise by keeping only large connected components."""
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(edge_img, connectivity=8)
    cleaned = np.zeros_like(edge_img)
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        width = stats[i, cv2.CC_STAT_WIDTH]
        height = stats[i, cv2.CC_STAT_HEIGHT]
        if area >= min_area and (width >= min_dim or height >= min_dim):
            cleaned[labels == i] = 255
    return cleaned


def _line_orientation(x1, y1, x2, y2, angle_tol=10):
    """Return 'horizontal' or 'vertical' if in tolerance, otherwise None."""
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 1 and abs(dy) > 5:
        return 'vertical'
    if abs(dy) < 1 and abs(dx) > 5:
        return 'horizontal'
    angle = abs(np.degrees(np.arctan2(dy, dx))) % 180
    if angle <= angle_tol or angle >= 180 - angle_tol:
        return 'horizontal'
    if abs(angle - 90) <= angle_tol:
        return 'vertical'
    return None


def _point_segment_distance(px, py, x1, y1, x2, y2):
    """Distance from point to line segment."""
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    c = vx*wx + vy*wy
    if c <= 0:
        return np.hypot(px - x1, py - y1)
    d2 = vx*vx + vy*vy
    if c >= d2:
        return np.hypot(px - x2, py - y2)
    b = c / d2
    bx, by = x1 + b*vx, y1 + b*vy
    return np.hypot(px - bx, py - by)


def _find_closest_wall(window, walls, max_dist=18):
    wx1, wy1, wx2, wy2 = window
    midx, midy = (wx1 + wx2) / 2.0, (wy1 + wy2) / 2.0
    best_wall = None
    best_dist = float('inf')
    for wall in walls:
        x1, y1, x2, y2 = wall
        dist = _point_segment_distance(midx, midy, x1, y1, x2, y2)
        if dist < best_dist:
            best_dist = dist
            best_wall = wall
    if best_dist <= max_dist:
        return best_wall
    return None


def _fallback_geometry():
    """
    Hardcoded sample geometry: a 4-bedroom floor plan.
    Coordinates are in pixels (800x600 canvas scale).
    """
    raw_walls = [
        # Outer boundary
        [50, 50, 750, 50],
        [750, 50, 750, 550],
        [750, 550, 50, 550],
        [50, 550, 50, 50],
        # Horizontal dividers
        [50, 200, 400, 200],
        [400, 200, 750, 200],
        [50, 380, 400, 380],
        [400, 380, 750, 380],
        # Vertical dividers
        [400, 50, 400, 550],
        [220, 200, 220, 380],
        [580, 50, 580, 380],
    ]
    walls = []
    for coords in raw_walls:
        x1, y1, x2, y2 = coords
        kind = "load_bearing" if (x1 in (50, 750) or x2 in (50, 750) or y1 in (50, 550) or y2 in (50, 550)) else "partition"
        walls.append({"coords": coords, "type": kind, "windows": []})

    return {
        "walls": walls,
        "image_size": [800, 600],
        "source": "fallback",
    }
