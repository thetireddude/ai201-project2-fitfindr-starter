"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import os
import re

from tools import _get_groq_client, search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)
    session["relaxed_search"] = False
    session["relaxed_params"] = None
    session["notes"] = []
    session["search_params"] = {}

    tool_calls = 0

    # Step 1: Parse query via LLM into structured fields
    print(f"[agent] parsing query: {query!r}")
    parsed = {"description": query, "size": None, "max_price": None}
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "parse_query_prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
        prompt = template.replace("{query}", query)
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if the model added them
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = raw.rstrip("`").strip()
        parsed = json.loads(raw)
    except Exception:
        pass  # fall back to raw query as description

    session["parsed"] = parsed
    description = parsed.get("description") or query
    size = parsed.get("size")
    max_price = parsed.get("max_price")
    # Coerce max_price to float in case the LLM returned a string like "$30"
    if isinstance(max_price, str):
        try:
            max_price = float(max_price.replace("$", "").strip())
        except ValueError:
            max_price = None
    session["search_params"] = {"description": description, "size": size, "max_price": max_price}
    print(f"[agent] parsed → description={description!r}, size={size!r}, max_price={max_price}")

    # Step 2: Search listings with automatic relaxation on no results
    results = search_listings(description, size, max_price)
    tool_calls += 1

    # Relax attempt 1: drop size filter
    if not results and size is not None and tool_calls < 6:
        print(f"[agent] no results — relaxing: dropping size filter '{size}'")
        results = search_listings(description, None, max_price)
        tool_calls += 1
        if results:
            session["relaxed_search"] = True
            session["relaxed_params"] = {"description": description, "size": None, "max_price": max_price}
            session["notes"].append(f"Relaxed: removed size filter '{size}'")

    # Relax attempt 2: also widen max_price by $20
    if not results and max_price is not None and tool_calls < 6:
        wider_price = max_price + 20.0
        print(f"[agent] no results — relaxing: raising max_price to ${wider_price:.2f}")
        results = search_listings(description, None, wider_price)
        tool_calls += 1
        if results:
            session["relaxed_search"] = True
            session["relaxed_params"] = {"description": description, "size": None, "max_price": wider_price}
            session["notes"].append(f"Relaxed: removed size filter and raised max_price to ${wider_price:.2f}")

    if not results:
        session["error"] = "No listings found — try broader keywords or remove size/price filters."
        return session

    session["search_results"] = results
    session["selected_item"] = results[0]

    # Step 3: Suggest outfit
    if tool_calls >= 6:
        session["error"] = "Reached tool call safety limit."
        return session

    outfit = suggest_outfit(session["selected_item"], wardrobe)
    tool_calls += 1

    if not outfit or not outfit.strip():
        session["error"] = "Could not generate outfit suggestion."
        return session

    session["outfit_suggestion"] = outfit

    # Step 4: Create fit card
    if tool_calls >= 6:
        session["error"] = "Reached tool call safety limit."
        return session

    fit_card = create_fit_card(outfit, session["selected_item"])
    tool_calls += 1

    if fit_card.startswith("Could not generate fit card"):
        session["error"] = fit_card
        return session

    session["fit_card"] = fit_card
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
