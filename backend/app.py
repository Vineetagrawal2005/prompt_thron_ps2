import io
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify, after_this_request, send_file
from werkzeug.utils import secure_filename

from parser import parse_floor_plan, _fallback_geometry
from geometry import reconstruct_geometry
from material import recommend_materials

app = Flask(__name__)

# store latest wall data so /graph can render consistent visual
last_floor_plan_walls = None

UPLOAD_FOLDER = "/tmp/asis_uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.after_request
def after_request(response):
    return add_cors(response)


@app.route("/health", methods=["GET", "OPTIONS"])
def health():
    return jsonify({"status": "ok", "service": "ASIS"})


def _render_floor_plan_graph(walls):
    """Generate 2D floor plan visualization from wall data."""
    fig, ax = plt.subplots(figsize=(5, 5), dpi=100)

    # Extract and plot walls by type
    for w in walls:
        if isinstance(w, dict):
            x1, y1, x2, y2 = w["coords"]
            wall_type = w.get("type", "partition")
        else:
            x1, y1, x2, y2 = w

        # Color by wall type
        color = "#ff4455" if (isinstance(w, dict) and w.get("type") == "load_bearing") else "#00cc66"
        linewidth = 2.0 if (isinstance(w, dict) and w.get("type") == "load_bearing") else 1.0

        ax.plot([x1, x2], [y1, y2], color=color, linewidth=linewidth, alpha=0.8)

        # Plot endpoints as nodes
        ax.scatter([x1, x2], [y1, y2], color="#0077cc", s=16, zorder=5)

    ax.set_aspect("equal", adjustable="box")
    ax.invert_yaxis()
    ax.axis("off")
    ax.set_facecolor("#0f1318")
    fig.patch.set_facecolor("#0f1318")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.06, facecolor="#0f1318")
    plt.close(fig)
    buf.seek(0)
    return buf


def _save_floor_plan_graph(walls, filename="graph.png"):
    buf = _render_floor_plan_graph(walls)
    with open(filename, "wb") as f:
        f.write(buf.getbuffer())


@app.route("/graph", methods=["GET"])
def graph():
    if not os.path.exists("graph.png"):
        parse_result = _fallback_geometry()
        _save_floor_plan_graph(parse_result.get("walls", []), "graph.png")
    return send_file("graph.png", mimetype="image/png")


def _build_response(parse_result):
    walls_raw = parse_result["walls"]
    image_size = parse_result["image_size"]
    source = parse_result["source"]

    raw_coords = [w["coords"] for w in walls_raw]
    geo_result = reconstruct_geometry(raw_coords, image_size)
    rooms = geo_result["rooms"]
    classified_walls = geo_result["classified_walls"]

    walls_data = []
    for i, w in enumerate(walls_raw):
        base = classified_walls[i] if i < len(classified_walls) else None
        wtype = base["type"] if base else w.get("type", "partition")
        length = base["length"] if base else np.sqrt((w["coords"][2]-w["coords"][0])**2 + (w["coords"][3]-w["coords"][1])**2)
        walls_data.append({
            "coords": w["coords"],
            "type": wtype,
            "length": round(length, 1),
            "windows": w.get("windows", [])
        })

    mat_result = recommend_materials(walls_data)

    scale = 0.05
    wall_height = 3.0
    wall_thickness = 0.2

    walls_3d = []
    for w in walls_data:
        x1, y1, x2, y2 = w["coords"]
        windows_3d = []
        for win in w.get("windows", []):
            wx1, wy1, wx2, wy2 = win
            windows_3d.append({
                "x1": round(wx1 * scale, 3), "y1": round(wy1 * scale, 3),
                "x2": round(wx2 * scale, 3), "y2": round(wy2 * scale, 3)
            })

        walls_3d.append({
            "x1": round(x1 * scale, 3), "y1": round(y1 * scale, 3),
            "x2": round(x2 * scale, 3), "y2": round(y2 * scale, 3),
            "height": wall_height, "thickness": wall_thickness,
            "type": w["type"], "length_m": w["length"],
            "windows": windows_3d
        })

    rooms_3d = []
    for room in rooms:
        rooms_3d.append([[round(c[0]*scale,3), round(c[1]*scale,3)] for c in room])

    w_px, h_px = image_size
    windows_2d = [win for w in walls_data for win in w.get("windows", [])]
    return {
        "meta": {"source": source, "image_size": image_size,
                 "wall_count": len(walls_data), "room_count": len(rooms), "scale": scale},
        "walls": walls_data,
        "walls_2d": [w["coords"] for w in walls_data],
        "windows_2d": windows_2d,
        "classified_walls": walls_data,
        "rooms": rooms,
        "walls_3d": walls_3d,
        "rooms_3d": rooms_3d,
        "floor": {"width": round(w_px * scale, 2), "depth": round(h_px * scale, 2)},
        "materials": mat_result,
    }


@app.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    image_path = None
    if "image" in request.files:
        file = request.files["image"]
        if file.filename:
            filename = secure_filename(file.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(image_path)

    global last_floor_plan_walls
    parse_result = parse_floor_plan(image_path) if image_path else _fallback_geometry()
    last_floor_plan_walls = parse_result.get("walls", [])

    # Save snapshot graph for frontend to load from /graph
    _save_floor_plan_graph(last_floor_plan_walls, "graph.png")

    return jsonify(_build_response(parse_result))


@app.route("/sample", methods=["GET", "OPTIONS"])
def sample():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    parse_result = _fallback_geometry()
    parse_result["source"] = "sample"
    return jsonify(_build_response(parse_result))


if __name__ == "__main__":
    print("🏗️  ASIS Backend — http://localhost:5050")
    app.run(debug=True, port=5050, host="0.0.0.0")
