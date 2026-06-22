"""
Flask app to serve the LOL-Tool API and frontend.

Usage:
    python app.py

Then visit http://localhost:5000
"""

import json
import os

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

from retrieval import retrieve_chunks
from generate import generate_recommendations

load_dotenv()

app = Flask(__name__)


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/api/champions", methods=["GET"])
def get_champions():
    """Return list of available champions (hardcoded for now)."""
    champions = [
        "Yasuo", "Zed", "Ahri", "Lux", "Jinx", "Lee Sin", "Darius",
        "Garen", "Thresh", "Vayne", "Yone", "Akali", "Katarina",
        "Malphite", "Leona", "Jhin", "Ezreal", "Riven", "Ashe", "Morgana",
    ]
    return jsonify(champions)


@app.route("/api/recommend", methods=["POST"])
def recommend():
    """
    POST endpoint to generate recommendations.
    
    Expected JSON:
    {
        "champion": "Yasuo",
        "role": "top",
        "enemy_comp": ["Zed", "Ahri", "Leona"],
        "team_comp": ["Yasuo", "Lee Sin", "Ahri", "Jinx", "Leona"]  (optional)
    }
    """
    try:
        data = request.json
        
        champion = data.get("champion", "").strip()
        role = data.get("role", "").strip()
        enemy_comp = data.get("enemy_comp", [])
        team_comp = data.get("team_comp", None)
        
        # Validate inputs
        if not champion or not role or not enemy_comp:
            return jsonify({"error": "Missing required fields: champion, role, enemy_comp"}), 400
        
        # Retrieve wiki chunks
        query = f"{champion} {role} vs {' '.join(enemy_comp)}"
        chunks = retrieve_chunks(
            query=query,
            champion_filter=champion,
            top_k=15
        )
        
        if not chunks:
            return jsonify({"error": f"No wiki data found for {champion}"}), 404
        
        # Generate recommendations
        recommendation = generate_recommendations(
            champion=champion,
            role=role,
            enemy_comp=enemy_comp,
            team_comp=team_comp,
            retrieved_chunks=chunks
        )
        
        return jsonify({
            "success": True,
            "recommendation": recommendation,
            "chunks_retrieved": len(chunks)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
