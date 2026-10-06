from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Meal
from datetime import date, datetime, timedelta

meals_bp = Blueprint("meals", __name__)


def serialize_meal(m):
    return {
        "id": m.id,
        "description": m.description,
        "calories": round(m.calories or 0, 1),
        "protein": round(m.protein or 0, 1),
        "carbs": round(m.carbs or 0, 1),
        "fat": round(m.fat or 0, 1),
        "logged_at": m.logged_at.isoformat() if m.logged_at else None,
    }


def number(value, field):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} invalide")
    if result < 0 or result > 20000:
        raise ValueError(f"{field} hors limites")
    return result


@meals_bp.route("/meal", methods=["POST"])
@jwt_required()
def add_meal():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    description = str(data.get("description", "")).strip()
    if not description:
        return jsonify({"error": "description requise"}), 400
    try:
        meal = Meal(
            user_id=user_id,
            description=description[:255],
            calories=number(data.get("calories", 0), "calories"),
            protein=number(data.get("protein", 0), "protein"),
            carbs=number(data.get("carbs", 0), "carbs"),
            fat=number(data.get("fat", 0), "fat"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    db.session.add(meal)
    db.session.commit()
    return jsonify(serialize_meal(meal)), 201


@meals_bp.route("/meal/<int:meal_id>", methods=["PUT"])
@jwt_required()
def update_meal(meal_id):
    user_id = get_jwt_identity()
    meal = Meal.query.filter_by(id=meal_id, user_id=user_id).first()
    if not meal:
        return jsonify({"error": "repas introuvable"}), 404
    data = request.get_json(silent=True) or {}
    try:
        if "description" in data:
            description = str(data["description"]).strip()
            if not description:
                return jsonify({"error": "description requise"}), 400
            meal.description = description[:255]
        for field in ("calories", "protein", "carbs", "fat"):
            if field in data:
                setattr(meal, field, number(data[field], field))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    db.session.commit()
    return jsonify(serialize_meal(meal)), 200


@meals_bp.route("/meal/<int:meal_id>", methods=["DELETE"])
@jwt_required()
def delete_meal(meal_id):
    user_id = get_jwt_identity()
    meal = Meal.query.filter_by(id=meal_id, user_id=user_id).first()
    if not meal:
        return jsonify({"error": "repas introuvable"}), 404
    db.session.delete(meal)
    db.session.commit()
    return jsonify({"success": True}), 200


@meals_bp.route("/day", methods=["GET"])
@jwt_required()
def day_summary():
    user_id = get_jwt_identity()
    raw = request.args.get("date")
    try:
        selected = datetime.strptime(raw, "%Y-%m-%d").date() if raw else date.today()
    except ValueError:
        return jsonify({"error": "date invalide, format YYYY-MM-DD"}), 400
    meals = Meal.query.filter(Meal.user_id == user_id, db.func.date(Meal.logged_at) == selected).order_by(Meal.logged_at.desc()).all()
    return jsonify(summary_payload(selected, meals)), 200


def summary_payload(selected, meals):
    return {
        "date": str(selected),
        "totals": {
            "calories": round(sum(m.calories or 0 for m in meals), 1),
            "protein": round(sum(m.protein or 0 for m in meals), 1),
            "carbs": round(sum(m.carbs or 0 for m in meals), 1),
            "fat": round(sum(m.fat or 0 for m in meals), 1),
        },
        "meals": [serialize_meal(m) for m in meals],
    }


@meals_bp.route("/today", methods=["GET"])
@jwt_required()
def today_summary():
    user_id = get_jwt_identity()
    selected = date.today()
    meals = Meal.query.filter(Meal.user_id == user_id, db.func.date(Meal.logged_at) == selected).order_by(Meal.logged_at.desc()).all()
    return jsonify(summary_payload(selected, meals)), 200


@meals_bp.route("/week", methods=["GET"])
@jwt_required()
def week_summary():
    user_id = get_jwt_identity()
    today = date.today()
    days_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    week_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        meals = Meal.query.filter(Meal.user_id == user_id, db.func.date(Meal.logged_at) == day).all()
        week_data.append({"day": days_fr[day.weekday()], "date": str(day), "calories": round(sum(m.calories or 0 for m in meals)), "protein": round(sum(m.protein or 0 for m in meals), 1), "has_meals": bool(meals)})
    return jsonify({"week": week_data}), 200


@meals_bp.route("/analytics", methods=["GET"])
@jwt_required()
def analytics():
    user_id = get_jwt_identity()
    days = min(max(request.args.get("days", default=30, type=int), 7), 90)
    today = date.today()
    series = []
    active_days = 0
    all_calories, all_protein = [], []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        meals = Meal.query.filter(Meal.user_id == user_id, db.func.date(Meal.logged_at) == d).all()
        calories = round(sum(m.calories or 0 for m in meals), 1)
        protein = round(sum(m.protein or 0 for m in meals), 1)
        if meals:
            active_days += 1
            all_calories.append(calories)
            all_protein.append(protein)
        series.append({"date": str(d), "calories": calories, "protein": protein, "logged": bool(meals)})
    return jsonify({
        "days": days,
        "series": series,
        "active_days": active_days,
        "adherence": round(active_days / days * 100),
        "average_calories": round(sum(all_calories) / len(all_calories)) if all_calories else None,
        "average_protein": round(sum(all_protein) / len(all_protein), 1) if all_protein else None,
    }), 200


@meals_bp.route("/streak", methods=["GET"])
@jwt_required()
def get_streak():
    user_id = get_jwt_identity()
    today = date.today()
    streak = 0
    current_day = today
    while streak <= 365:
        exists = Meal.query.filter(Meal.user_id == user_id, db.func.date(Meal.logged_at) == current_day).first()
        if not exists:
            break
        streak += 1
        current_day -= timedelta(days=1)
    week_days = []
    days_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        exists = Meal.query.filter(Meal.user_id == user_id, db.func.date(Meal.logged_at) == day).first()
        week_days.append({"day": days_fr[day.weekday()], "done": bool(exists), "today": day == today})
    return jsonify({"streak": streak, "week": week_days}), 200
