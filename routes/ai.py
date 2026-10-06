from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from anthropic import Anthropic

from models import db, Meal, User

from datetime import date

import os
import json
import base64


# ============================================================
# BLUEPRINT
# ============================================================

ai_bp = Blueprint(
    "ai",
    __name__
)


# ============================================================
# CLIENT ANTHROPIC
# ============================================================

def get_client():

    api_key = os.getenv(
        "ANTHROPIC_API_KEY"
    )

    if not api_key:
        return None

    return Anthropic(
        api_key=api_key
    )


# ============================================================
# JSON PARSER
# ============================================================

def parse_json(text):

    text = text.strip()

    if text.startswith("```"):

        parts = text.split("```")

        if len(parts) >= 2:

            text = parts[1]

            if text.startswith("json"):
                text = text[4:]

    return json.loads(
        text.strip()
    )


# ============================================================
# ANALYSE TEXTE
# ============================================================

@ai_bp.route(
    "/analyze-text",
    methods=["POST"]
)
@jwt_required()
def analyze_text():

    user_id = int(
        get_jwt_identity()
    )

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    description = str(
        data.get(
            "description",
            ""
        )
    ).strip()

    if not description:

        return jsonify({
            "error":
                "Décris ton repas."
        }), 400


    client = get_client()

    if not client:

        return jsonify({
            "error":
                "La clé API IA n'est pas configurée."
        }), 503


    prompt = f"""
Tu es NutriAI, expert en estimation nutritionnelle.

L'utilisateur décrit ce repas :

"{description}"

Tu dois estimer :

- la quantité probable ;
- les calories ;
- les protéines ;
- les glucides ;
- les lipides.

Utilise des valeurs nutritionnelles typiques cohérentes
avec des tables reconnues comme ANSES Ciqual ou USDA.

Si l'utilisateur donne une quantité précise,
utilise cette quantité.

Si aucune quantité n'est donnée,
estime une portion réaliste.

Pour un plat composé :
1. identifie les ingrédients principaux ;
2. estime leur poids ;
3. estime leurs nutriments ;
4. additionne.

Retourne UNIQUEMENT un JSON valide :

{{
    "description": "description normalisée du repas",
    "estimated_portion": "portion estimée",
    "calories": 0,
    "protein": 0,
    "carbs": 0,
    "fat": 0,
    "confidence": "faible|moyenne|bonne",
    "details": "explication courte"
}}

Aucun markdown.
"""


    try:

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        nutrition = parse_json(
            response.content[0].text
        )

    except Exception as error:

        print(
            "Erreur analyse texte IA :",
            repr(error)
        )

        return jsonify({
            "error":
                f"L'analyse IA du repas a échoué : {str(error)}"
        }), 503


    try:

        calories = max(
            float(
                nutrition.get(
                    "calories",
                    0
                )
            ),
            0
        )

        protein = max(
            float(
                nutrition.get(
                    "protein",
                    0
                )
            ),
            0
        )

        carbs = max(
            float(
                nutrition.get(
                    "carbs",
                    0
                )
            ),
            0
        )

        fat = max(
            float(
                nutrition.get(
                    "fat",
                    0
                )
            ),
            0
        )

    except (TypeError, ValueError):

        return jsonify({
            "error":
                "Valeurs nutritionnelles invalides."
        }), 503


    meal = Meal(
        user_id=user_id,

        description=nutrition.get(
            "description",
            description
        ),

        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat
    )


    db.session.add(
        meal
    )

    db.session.commit()


    return jsonify({
        "id":
            meal.id,

        "description":
            meal.description,

        "estimated_portion":
            nutrition.get(
                "estimated_portion",
                ""
            ),

        "calories":
            meal.calories,

        "protein":
            meal.protein,

        "carbs":
            meal.carbs,

        "fat":
            meal.fat,

        "confidence":
            nutrition.get(
                "confidence",
                "moyenne"
            ),

        "details":
            nutrition.get(
                "details",
                ""
            )
    }), 201


# ============================================================
# ANALYSE PHOTO
# ============================================================

@ai_bp.route(
    "/analyze-photo",
    methods=["POST"]
)
@jwt_required()
def analyze_photo():

    user_id = int(
        get_jwt_identity()
    )

    photo = request.files.get(
        "photo"
    )

    if not photo:

        return jsonify({
            "error":
                "Aucune photo reçue."
        }), 400


    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp"
    }


    if photo.content_type not in allowed_types:

        return jsonify({
            "error":
                "Format d'image non accepté."
        }), 400


    image_bytes = photo.read()


    if len(image_bytes) > 8 * 1024 * 1024:

        return jsonify({
            "error":
                "L'image est trop volumineuse."
        }), 400


    client = get_client()

    if not client:

        return jsonify({
            "error":
                "La clé API IA n'est pas configurée."
        }), 503


    encoded = (
        base64
        .standard_b64encode(
            image_bytes
        )
        .decode(
            "utf-8"
        )
    )


    prompt = """
Tu es NutriAI.

Analyse le repas visible sur la photo.

Identifie les aliments.
Estime leurs quantités.

Utilise des valeurs nutritionnelles typiques
compatibles avec ANSES Ciqual ou USDA.

Retourne UNIQUEMENT :

{
    "description": "description du repas",
    "estimated_portion": "description des portions",
    "calories": 0,
    "protein": 0,
    "carbs": 0,
    "fat": 0,
    "confidence": "faible|moyenne|bonne",
    "details": "courte explication"
}

Aucun markdown.
"""


    try:

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[
                {
                    "role":
                        "user",

                    "content": [
                        {
                            "type":
                                "image",

                            "source": {
                                "type":
                                    "base64",

                                "media_type":
                                    photo.content_type,

                                "data":
                                    encoded
                            }
                        },

                        {
                            "type":
                                "text",

                            "text":
                                prompt
                        }
                    ]
                }
            ]
        )

        nutrition = parse_json(
            response.content[0].text
        )

    except Exception as error:

        print(
            "Erreur analyse photo IA :",
            repr(error)
        )

        return jsonify({
            "error":
                f"Impossible d'analyser cette photo : {str(error)}"
        }), 503


    try:

        calories = max(
            float(
                nutrition.get(
                    "calories",
                    0
                )
            ),
            0
        )

        protein = max(
            float(
                nutrition.get(
                    "protein",
                    0
                )
            ),
            0
        )

        carbs = max(
            float(
                nutrition.get(
                    "carbs",
                    0
                )
            ),
            0
        )

        fat = max(
            float(
                nutrition.get(
                    "fat",
                    0
                )
            ),
            0
        )

    except (TypeError, ValueError):

        return jsonify({
            "error":
                "Valeurs nutritionnelles invalides."
        }), 503


    meal = Meal(
        user_id=user_id,

        description=nutrition.get(
            "description",
            "Repas analysé"
        ),

        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat
    )


    db.session.add(
        meal
    )

    db.session.commit()


    return jsonify({
        "id":
            meal.id,

        "description":
            meal.description,

        "estimated_portion":
            nutrition.get(
                "estimated_portion",
                ""
            ),

        "calories":
            meal.calories,

        "protein":
            meal.protein,

        "carbs":
            meal.carbs,

        "fat":
            meal.fat,

        "confidence":
            nutrition.get(
                "confidence",
                "moyenne"
            ),

        "details":
            nutrition.get(
                "details",
                ""
            )
    }), 201


# ============================================================
# COACH IA
# ============================================================

@ai_bp.route(
    "/coach",
    methods=["POST"]
)
@jwt_required()
def coach():

    user_id = int(
        get_jwt_identity()
    )


    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    question = str(
        data.get(
            "question",
            ""
        )
    ).strip()


    if not question:

        return jsonify({
            "error":
                "Pose une question au coach."
        }), 400


    # ========================================================
    # USER
    # ========================================================

    user = db.session.get(
        User,
        user_id
    )


    if not user:

        return jsonify({
            "error":
                "Utilisateur introuvable."
        }), 404


    # ========================================================
    # REPAS DU JOUR
    # ========================================================

    today = date.today()


    meals = Meal.query.filter(

        Meal.user_id == user_id,

        db.func.date(
            Meal.logged_at
        ) == today

    ).order_by(
        Meal.logged_at.asc()
    ).all()


    calories = sum(
        meal.calories or 0
        for meal in meals
    )

    protein = sum(
        meal.protein or 0
        for meal in meals
    )

    carbs = sum(
        meal.carbs or 0
        for meal in meals
    )

    fat = sum(
        meal.fat or 0
        for meal in meals
    )


    meal_descriptions = [
        meal.description
        for meal in meals
    ]


    # ========================================================
    # CLIENT
    # ========================================================

    client = get_client()


    if not client:

        return jsonify({
            "error":
                "La clé API Anthropic n'est pas configurée."
        }), 503


    # ========================================================
    # PROMPT
    # ========================================================

    prompt = f"""
Tu es NutriAI Coach.

Tu dois répondre à l'utilisateur ET détecter
s'il mentionne un aliment ou un repas
qu'il dit avoir mangé.

DONNÉES ENREGISTRÉES AUJOURD'HUI

Calories :
{round(calories)} kcal

Protéines :
{round(protein)} g

Glucides :
{round(carbs)} g

Lipides :
{round(fat)} g

Repas enregistrés :
{meal_descriptions if meal_descriptions else "aucun"}


PROFIL

Âge :
{user.age if user.age else "non renseigné"}

Poids :
{user.weight if user.weight else "non renseigné"}

Taille :
{user.height if user.height else "non renseignée"}

Objectif :
{user.goal if user.goal else "non renseigné"}


QUESTION UTILISATEUR

"{question}"


RÈGLES IMPORTANTES

Si l'utilisateur dit avoir mangé quelque chose :

exemples :
- j'ai mangé du pain
- j'ai mangé du couscous
- j'ai mangé 200 g de poulet
- j'ai mangé une pizza
- j'ai mangé un sandwich
- j'ai mangé une assiette de pâtes
- j'ai mangé un steak
- j'ai mangé du riz
- j'ai mangé des œufs
- j'ai mangé un burger
- j'ai mangé un tajine

tu dois estimer :

- calories
- protéines
- glucides
- lipides

Utilise des valeurs nutritionnelles typiques
comparables à ANSES Ciqual / USDA.

Si la quantité est inconnue,
estime une portion normale réaliste.

Pour un plat composé :
- identifie les ingrédients principaux ;
- estime leurs quantités ;
- estime les calories/macros ;
- additionne le total.

Si l'utilisateur donne une quantité précise,
utilise cette quantité.

Ne prétends jamais que le repas est déjà enregistré
s'il ne l'est pas.

L'estimation doit être séparée
des données officielles NutriAI.

Si l'utilisateur ne parle pas d'un repas à estimer,
réponds normalement.

Si le profil semble incohérent,
reste neutre et demande simplement
de vérifier les informations.

Réponds en français.

Réponse courte, naturelle et utile.


IMPORTANT :

Retourne UNIQUEMENT du JSON valide.

SI UN REPAS DOIT ÊTRE ESTIMÉ :

{{
    "answer": "réponse naturelle en français avec l'estimation",
    "estimate": {{
        "can_add": true,
        "description": "nom du repas",
        "calories": 0,
        "protein": 0,
        "carbs": 0,
        "fat": 0
    }}
}}

SI AUCUN REPAS N'EST À ESTIMER :

{{
    "answer": "réponse naturelle en français",
    "estimate": {{
        "can_add": false,
        "description": "",
        "calories": 0,
        "protein": 0,
        "carbs": 0,
        "fat": 0
    }}
}}

Aucun markdown autour du JSON.
Aucun texte avant le JSON.
Aucun texte après le JSON.
"""


    # ========================================================
    # CALL CLAUDE
    # ========================================================

    try:

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[
                {
                    "role":
                        "user",

                    "content":
                        prompt
                }
            ]
        )


        raw_text = (
            response
            .content[0]
            .text
            .strip()
        )




        result = parse_json(
            raw_text
        )


    except Exception as error:

        print(
            "Erreur Coach IA :",
            repr(error)
        )

        return jsonify({
            "error":
                "Le Coach IA est temporairement indisponible."
        }), 503


    # ========================================================
    # SAFE ESTIMATE
    # ========================================================

    estimate = result.get(
        "estimate",
        {}
    )


    try:

        estimate_calories = max(
            float(
                estimate.get(
                    "calories",
                    0
                )
            ),
            0
        )

    except (TypeError, ValueError):

        estimate_calories = 0


    try:

        estimate_protein = max(
            float(
                estimate.get(
                    "protein",
                    0
                )
            ),
            0
        )

    except (TypeError, ValueError):

        estimate_protein = 0


    try:

        estimate_carbs = max(
            float(
                estimate.get(
                    "carbs",
                    0
                )
            ),
            0
        )

    except (TypeError, ValueError):

        estimate_carbs = 0


    try:

        estimate_fat = max(
            float(
                estimate.get(
                    "fat",
                    0
                )
            ),
            0
        )

    except (TypeError, ValueError):

        estimate_fat = 0


    # ========================================================
    # RESPONSE
    # ========================================================

    return jsonify({
        "answer":
            result.get(
                "answer",
                ""
            ),

        "estimate": {

            "can_add":
                bool(
                    estimate.get(
                        "can_add",
                        False
                    )
                ),

            "description":
                str(
                    estimate.get(
                        "description",
                        ""
                    )
                ),

            "calories":
                estimate_calories,

            "protein":
                estimate_protein,

            "carbs":
                estimate_carbs,

            "fat":
                estimate_fat
        }
    })