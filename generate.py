"""
Generation layer: use Claude to synthesize retrieved chunks into recommendations.

Takes retrieved wiki chunks and generates:
1. Rune page recommendation
2. Summoner spell recommendation with reasoning
3. Early game gameplan
4. Item path with reasoning
5. Teamfight role description

Usage:
    from generate import generate_recommendations
    
    result = generate_recommendations(
        champion="Yasuo",
        role="top",
        enemy_comp=["Zed", "Ahri", "Leona"],
        team_comp=["Yasuo", "Lee Sin", "Ahri", "Jinx", "Leona"],  # optional
        retrieved_chunks=[...]  # from retrieval.py
    )
"""

import json
import os
from typing import Any

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY must be set in .env")

client = Anthropic()


def format_chunks_for_context(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into a readable context string for Claude."""
    if not chunks:
        return "No relevant wiki data found."
    
    context_parts = []
    for chunk in chunks:
        context_parts.append(
            f"[{chunk['champion']} - {chunk['section']}]\n{chunk['content']}"
        )
    return "\n\n---\n\n".join(context_parts)


def generate_recommendations(
    champion: str,
    role: str,
    enemy_comp: list[str],
    team_comp: list[str] | None = None,
    retrieved_chunks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Generate build/strategy recommendations using Claude and retrieved wiki data.
    
    Args:
        champion: Champion to build for (e.g. "Yasuo")
        role: Role to play (e.g. "top")
        enemy_comp: List of enemy champion names (e.g. ["Zed", "Ahri", "Leona"])
        team_comp: Optional list of your team's champions
        retrieved_chunks: List of chunks from retrieval.retrieve_chunks()
    
    Returns:
        Dict with keys: rune_page, summoner_spells, early_game, item_path, teamfight_role
    """
    
    # Format enemy comp
    enemy_str = ", ".join(enemy_comp)
    team_str = ", ".join(team_comp) if team_comp else "Unknown"
    
    # Format context
    context = format_chunks_for_context(retrieved_chunks or [])
    
    # Build the prompt
    prompt = f"""You are an expert League of Legends coach. Based on the wiki data below, provide a concise build recommendation for:

Champion: {champion}
Role: {role}
Enemy Comp: {enemy_str}
Your Team Comp: {team_str}

---

WIKI DATA:
{context}

---

Provide your recommendation in the following JSON format ONLY (no markdown, no extra text):

{{
    "rune_page": {{
        "primary_tree": "Precision|Domination|Sorcery|Resolve|Inspiration",
        "primary_keystone": "Keystone rune name",
        "secondaries": ["rune 1", "rune 2"],
        "secondary_tree": "Tree name",
        "shards": {{"offense": "shard", "flex": "shard", "defense": "shard"}}
    }},
    "summoner_spells": {{
        "spell_1": "Flash|Teleport|Ignite|Smite|...",
        "spell_2": "...",
        "reasoning": "Brief explanation of why these spells into this comp"
    }},
    "early_game_plan": "1-2 sentences on laning phase strategy, win conditions, and what to avoid against this comp",
    "item_path": {{
        "early_game": "First 1-2 items",
        "mid_game": "Items 3-4",
        "late_game": "Items 5-6",
        "reasoning": "Why this path counters the enemy comp"
    }},
    "teamfight_role": "1-2 sentences describing your positioning, threats to watch, and your primary job in 5v5 teamfights"
}}

Generate the recommendation now:"""

    # Call Claude
    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    response_text = message.content[0].text
    
    # Parse JSON response
    try:
        recommendation = json.loads(response_text)
    except json.JSONDecodeError:
        # If Claude's response isn't valid JSON, return a fallback
        recommendation = {
            "rune_page": {"error": "Failed to parse Claude's response"},
            "summoner_spells": {"spell_1": "Flash", "spell_2": "Teleport"},
            "early_game_plan": "Unable to generate plan",
            "item_path": {"error": "Unable to generate path"},
            "teamfight_role": "Unable to determine role",
            "raw_response": response_text
        }
    
    return recommendation


if __name__ == "__main__":
    # Test with mock chunks
    from retrieval import retrieve_chunks
    
    champion = "Yasuo"
    role = "top"
    enemy_comp = ["Zed", "Ahri", "Leona"]
    
    print(f"Retrieving wiki data for {champion} {role}...")
    chunks = retrieve_chunks(
        query=f"{champion} {role} vs {' '.join(enemy_comp)}",
        champion_filter=champion,
        top_k=15
    )
    
    print(f"Generating recommendations based on {len(chunks)} chunks...\n")
    result = generate_recommendations(
        champion=champion,
        role=role,
        enemy_comp=enemy_comp,
        retrieved_chunks=chunks
    )
    
    print(json.dumps(result, indent=2))
