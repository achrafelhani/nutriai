from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User
import math

auth_bp = Blueprint("auth", __name__)

def calculate_macros(age, weight, height, goal):
    """Repères énergétiques estimatifs à partir des données de profil.

    Le calcul conserve la logique historique du projet (Harris-Benedict, activité
    modérée) mais évite les projections de poids/muscle non observées.
    """
    bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
    tdee = bmr * 1.55
    if goal == "perte":
        calories, protein, fat = tdee - 500, weight * 2.0, weight * 0.8
    elif goal == "muscle":
        calories, protein, fat = tdee + 300, weight * 2.2, weight * 1.0
    elif goal == "maintien":
        calories, protein, fat = tdee, weight * 1.6, weight * 0.9
    else:
        calories, protein, fat = tdee - 200, weight * 1.6, weight * 0.8
    carbs = (calories - protein * 4 - fat * 9) / 4
    return {
        "calories": round(calories),
        "protein": round(protein),
        "carbs": round(max(carbs, 50)),
        "fat": round(fat),
        "conseil": "Repères estimatifs calculés à partir de ton profil et de l'hypothèse d'une activité modérée."
    }


def validate_profile(data, legacy=False):
    try:
        age = int(data.get("age"))
        weight = float(data.get("poids" if legacy else "weight"))
        height = float(data.get("taille" if legacy else "height"))
    except (TypeError, ValueError):
        raise ValueError("âge, poids et taille doivent être numériques")
    goal = data.get("objectif" if legacy else "goal")
    if not 14 <= age <= 100:
        raise ValueError("âge hors limites")
    if not 30 <= weight <= 350:
        raise ValueError("poids hors limites")
    if not 120 <= height <= 230:
        raise ValueError("taille hors limites")
    if goal not in {"perte", "muscle", "maintien", "sante"}:
        raise ValueError("objectif invalide")
    return age, weight, height, goal

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({"error": "username et password requis"}), 400
    if len(username) < 3 or len(username) > 80:
        return jsonify({"error": "username entre 3 et 80 caractères"}), 400
    if len(password) < 8:
        return jsonify({"error": "mot de passe de 8 caractères minimum"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "ce username existe deja"}), 409

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "username": user.username}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "identifiants invalides"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "username": user.username}), 200


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "utilisateur introuvable"}), 404

    macros = None
    if user.age and user.weight and user.height and user.goal:
        macros = calculate_macros(user.age, user.weight, user.height, user.goal)

    return jsonify({
        "id": user.id,
        "username": user.username,
        "age": user.age,
        "weight": user.weight,
        "height": user.height,
        "goal": user.goal,
        "macros": macros
    }), 200


@auth_bp.route("/profile", methods=["POST"])
@jwt_required()
def save_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "utilisateur introuvable"}), 404

    data = request.get_json(silent=True) or {}
    try:
        user.age, user.weight, user.height, user.goal = validate_profile(data, legacy=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    db.session.commit()

    macros = calculate_macros(user.age, user.weight, user.height, user.goal)
    return jsonify({"success": True, "macros": macros}), 200


@auth_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "utilisateur introuvable"}), 404

    data = request.get_json(silent=True) or {}
    merged = {
        "age": data.get("age", user.age),
        "weight": data.get("weight", user.weight),
        "height": data.get("height", user.height),
        "goal": data.get("goal", user.goal),
    }
    try:
        user.age, user.weight, user.height, user.goal = validate_profile(merged)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    db.session.commit()

    return jsonify({
        "id": user.id,
        "username": user.username,
        "age": user.age,
        "weight": user.weight,
        "height": user.height,
        "goal": user.goal
    }), 200