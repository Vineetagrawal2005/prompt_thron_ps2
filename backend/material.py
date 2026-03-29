import math

# Starter material database (from problem statement)
MATERIALS = {
    "AAC Blocks": {
        "cost": 1,        # 1=Low, 2=Med, 3=High
        "strength": 2,    # 1=Low, 2=Med, 3=High, 4=VeryHigh
        "durability": 3,
        "best_use": "Partition walls",
        "cost_label": "Low",
        "strength_label": "Medium",
    },
    "Red Brick": {
        "cost": 2,
        "strength": 3,
        "durability": 2,
        "best_use": "Load-bearing walls",
        "cost_label": "Medium",
        "strength_label": "High",
    },
    "RCC": {
        "cost": 3,
        "strength": 4,
        "durability": 4,
        "best_use": "Columns, slabs",
        "cost_label": "High",
        "strength_label": "Very High",
    },
    "Steel Frame": {
        "cost": 3,
        "strength": 4,
        "durability": 4,
        "best_use": "Long spans (>5m)",
        "cost_label": "High",
        "strength_label": "Very High",
    },
    "Hollow Concrete Block": {
        "cost": 1.5,
        "strength": 2,
        "durability": 2,
        "best_use": "Non-structural walls",
        "cost_label": "Low–Med",
        "strength_label": "Medium",
    },
    "Fly Ash Brick": {
        "cost": 1,
        "strength": 2.5,
        "durability": 3,
        "best_use": "General walling",
        "cost_label": "Low",
        "strength_label": "Medium–High",
    },
    "Precast Concrete Panel": {
        "cost": 2.5,
        "strength": 3,
        "durability": 4,
        "best_use": "Structural walls, slabs",
        "cost_label": "Med–High",
        "strength_label": "High",
    },
}

# Pixel-to-meter scale (assuming 800px wide = ~15m typical house)
PIXELS_PER_METER = 800 / 15.0


def recommend_materials(classified_walls):
    """
    For each wall, recommend top 2 materials with tradeoff scores.
    Returns per-wall recommendations and overall stats.
    """
    recommendations = []

    for wall in classified_walls:
        wall_type = wall["type"]
        length_px = wall["length"]
        length_m = round(length_px / PIXELS_PER_METER, 2)

        scored = _score_materials(wall_type, length_m)
        top2 = scored[:2]

        recommendations.append(
            {
                "wall_coords": wall["coords"],
                "wall_type": wall_type,
                "length_m": length_m,
                "recommendations": top2,
                "explanation": _explain(wall_type, length_m, top2),
            }
        )

    # Aggregate summary
    lb_count = sum(1 for w in classified_walls if w["type"] == "load_bearing")
    pt_count = sum(1 for w in classified_walls if w["type"] == "partition")

    return {
        "wall_recommendations": recommendations,
        "summary": {
            "total_walls": len(classified_walls),
            "load_bearing_count": lb_count,
            "partition_count": pt_count,
            "primary_structural_material": "Red Brick" if lb_count > 0 else "AAC Blocks",
            "primary_partition_material": "AAC Blocks",
        },
    }


def _score_materials(wall_type, length_m):
    """
    Score all materials for a given wall type.
    
    For load-bearing walls: weight strength more (0.6 strength, 0.4 cost-efficiency)
    For partition walls: weight cost more (0.7 cost-efficiency, 0.3 strength)
    
    cost-efficiency = (4 - cost) / 3   [inverted: lower cost = higher score]
    strength_norm = strength / 4
    """
    results = []

    for name, props in MATERIALS.items():
        cost_eff = (4 - props["cost"]) / 3.0
        strength_norm = props["strength"] / 4.0

        # Long span bonus for steel/RCC
        span_bonus = 0
        if length_m > 5 and name in ("Steel Frame", "RCC"):
            span_bonus = 0.15

        if wall_type == "load_bearing":
            score = 0.6 * strength_norm + 0.4 * cost_eff + span_bonus
        else:
            score = 0.3 * strength_norm + 0.7 * cost_eff + span_bonus

        results.append(
            {
                "material": name,
                "score": round(score, 3),
                "cost": props["cost_label"],
                "strength": props["strength_label"],
                "best_use": props["best_use"],
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def _explain(wall_type, length_m, top2):
    """Generate plain-English explanation for material recommendation."""
    top = top2[0]["material"]
    runner = top2[1]["material"] if len(top2) > 1 else "N/A"

    span_note = ""
    if length_m > 5:
        span_note = f" This is a long span ({length_m}m > 5m), so high-strength materials are critical."
    elif length_m > 3:
        span_note = f" Span is {length_m}m — moderate structural demand."
    else:
        span_note = f" Short span ({length_m}m) — standard construction applies."

    if wall_type == "load_bearing":
        return (
            f"This is a LOAD-BEARING wall and carries structural loads to the foundation."
            f"{span_note} "
            f"**{top}** is recommended as primary material (high strength, proven for structural walls). "
            f"**{runner}** is a cost-effective alternative if budget is constrained."
        )
    else:
        return (
            f"This is a PARTITION wall — non-structural, used only for space division."
            f"{span_note} "
            f"**{top}** is recommended for its low cost and ease of construction. "
            f"**{runner}** offers slightly better durability at a marginal cost increase."
        )
