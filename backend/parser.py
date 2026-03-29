import cv2
import numpy as np


def parse_floor_plan(image_path):
    """
    Parse a floor plan image using OpenCV.
    Returns walls as [x1, y1, x2, y2] line segments.
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

        # Dilate edges slightly to connect nearby lines
        kernel = np.ones((2, 2), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

        # HoughLinesP to detect wall line segments
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

        walls = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            if length > 15:  # Filter very short segments
                walls.append([int(x1), int(y1), int(x2), int(y2)])

        # Remove near-duplicate lines
        walls = _deduplicate_lines(walls)

        return {
            "walls": walls,
            "image_size": [new_w, new_h],
            "source": "opencv",
        }

    except Exception as e:
        print(f"[Parser] OpenCV failed ({e}), using fallback geometry.")
        return _fallback_geometry()


def _deduplicate_lines(walls, threshold=8):
    """Remove near-duplicate lines."""
    unique = []
    for w in walls:
        x1, y1, x2, y2 = w
        duplicate = False
        for u in unique:
            ux1, uy1, ux2, uy2 = u
            if (
                abs(x1 - ux1) < threshold
                and abs(y1 - uy1) < threshold
                and abs(x2 - ux2) < threshold
                and abs(y2 - uy2) < threshold
            ):
                duplicate = True
                break
        if not duplicate:
            unique.append(w)
    return unique


def _fallback_geometry():
    """
    Hardcoded sample geometry: a 4-bedroom floor plan.
    Coordinates are in pixels (800x600 canvas scale).
    """
    walls = [
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
        # Door openings (short gaps represented by shorter lines)
        [130, 380, 130, 550],
        [310, 380, 310, 550],
        [490, 380, 490, 550],
    ]
    return {
        "walls": walls,
        "image_size": [800, 600],
        "source": "fallback",
    }
