import os
from flask import Flask, request, jsonify, after_this_request
from werkzeug.utils import secure_filename

from parser import parse_floor_plan, _fallback_geometry
from geometry import reconstruct_geometry
from material import recommend_materials

app = Flask(__name__)

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


def _build_response(parse_result):
    walls_raw = parse_result["walls"]
    image_size = parse_result["image_size"]
    source = parse_result["source"]

    geo_result = reconstruct_geometry(walls_raw, image_size)
    rooms = geo_result["rooms"]
    classified_walls = geo_result["classified_walls"]
    mat_result = recommend_materials(classified_walls)

    scale = 0.05
    wall_height = 3.0
    wall_thickness = 0.2

    walls_3d = []
    for w in classified_walls:
        x1, y1, x2, y2 = w["coords"]
        walls_3d.append({
            "x1": round(x1 * scale, 3), "y1": round(y1 * scale, 3),
            "x2": round(x2 * scale, 3), "y2": round(y2 * scale, 3),
            "height": wall_height, "thickness": wall_thickness,
            "type": w["type"], "length_m": w["length"],
        })

    rooms_3d = []
    for room in rooms:
        rooms_3d.append([[round(c[0]*scale,3), round(c[1]*scale,3)] for c in room])

    w_px, h_px = image_size
    return {
        "meta": {"source": source, "image_size": image_size,
                 "wall_count": len(classified_walls), "room_count": len(rooms), "scale": scale},
        "walls_2d": [w["coords"] for w in classified_walls],
        "classified_walls": classified_walls,
        "rooms": rooms, "walls_3d": walls_3d, "rooms_3d": rooms_3d,
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

    parse_result = parse_floor_plan(image_path) if image_path else _fallback_geometry()
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
