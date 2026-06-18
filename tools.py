"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

import httpx
from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key, http_client=httpx.Client(verify=False))


# ── helpers ───────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Lowercase and split text into alphanumeric tokens (e.g. 'S/M' → ['s', 'm'])."""
    return re.findall(r'[a-z0-9]+', text.lower())


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    print(f"[tool] search_listings(description={description!r}, size={size!r}, max_price={max_price})")
    try:
        listings = load_listings()
    except Exception:
        return []

    # Price filter
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    # Size filter — substring match, case-insensitive
    if size is not None:
        size_lower = size.lower()
        listings = [l for l in listings if size_lower in l.get("size", "").lower()]

    # Tokenize the query
    query_tokens = set(_tokenize(description))
    if not query_tokens:
        return []

    # Score each listing by token overlap across all searchable fields
    scored = []
    for listing in listings:
        searchable = (
            [listing.get("title", ""), listing.get("description", ""), listing.get("brand") or ""]
            + listing.get("style_tags", [])
            + listing.get("colors", [])
        )
        listing_tokens = set()
        for field in searchable:
            listing_tokens.update(_tokenize(field))

        score = sum(1 for t in query_tokens if t in listing_tokens)
        if score > 0:
            scored.append((score, listing["price"], listing))

    # Sort by score descending, tie-break by lower price
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [entry[2] for entry in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    print(f"[tool] suggest_outfit(item={new_item.get('title')!r})")
    # Validate wardrobe and extract items
    items = []
    if isinstance(wardrobe, dict):
        items = wardrobe.get("items") or []

    # Fallback string derived from new_item metadata (used when wardrobe empty or LLM fails)
    colors_str = ", ".join(new_item.get("colors", [])) or "neutral"
    tags_str = ", ".join(new_item.get("style_tags", [])) or "vintage"
    category = new_item.get("category", "item")
    fallback = (
        f"• Pair this {category} (colors: {colors_str}) with simple basics to let it stand out.\n"
        f"• It suits a {tags_str} aesthetic — try layering for a more editorial look.\n"
        f"• Works well for casual outings, weekend hangs, or low-key streetwear fits.\n"
        f"• For shoes, chunky sneakers or boots complement this vibe best.\n"
        f"• Keep accessories minimal so the piece stays the focal point."
    )

    # Build prompt fields
    wardrobe_section: str
    task_instruction: str

    if not items:
        wardrobe_section = ""
        task_instruction = (
            "The user has no wardrobe on file. Give 3–5 general styling tips for this item: "
            "what bottoms/tops/shoes pair well with it, what vibe/mood it suits, and one occasion it works for."
        )
    else:
        lines = []
        for w in items[:6]:
            name = w.get("name", "item")
            cat = w.get("category", "")
            colors = ", ".join(w.get("colors", []))
            tags = ", ".join(w.get("style_tags", []))
            notes = w.get("notes") or ""
            line = f"- {name} ({cat}) | colors: {colors} | tags: {tags}"
            if notes:
                line += f" | notes: {notes}"
            lines.append(line)
        wardrobe_section = "USER'S WARDROBE:\n" + "\n".join(lines)
        task_instruction = (
            "Using only pieces from the wardrobe above, suggest 1–2 complete outfits "
            "that incorporate the new item. Name the specific wardrobe pieces in each outfit."
        )

    # Load and fill prompt template
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "suggest_outfit_prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
    except OSError:
        return fallback

    prompt = template.format(
        title=new_item.get("title", ""),
        category=category,
        colors=colors_str,
        style_tags=tags_str,
        description=new_item.get("description", ""),
        wardrobe_section=wardrobe_section,
        task_instruction=task_instruction,
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=400,
        )
        result = response.choices[0].message.content.strip()
        return result if result else fallback
    except Exception:
        return fallback


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    print(f"[tool] create_fit_card(item={new_item.get('title')!r})")
    if not outfit or not outfit.strip():
        return "Could not generate fit card: missing outfit details."

    title = new_item.get("title", "this item")
    price = new_item.get("price", "?")
    platform = new_item.get("platform", "secondhand")
    colors_str = ", ".join(new_item.get("colors", [])) or "neutral"
    tags_str = ", ".join(new_item.get("style_tags", [])) or "vintage"

    fallback = (
        f"Just scored the {title} for ${price} on {platform} and I'm obsessed. "
        f"This {colors_str} piece has major {tags_str} energy and it goes with everything."
    )

    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "create_fit_card_prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
    except OSError:
        return fallback

    prompt = template.format(
        title=title,
        price=price,
        platform=platform,
        colors=colors_str,
        style_tags=tags_str,
        outfit=outfit,
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=200,
        )
        result = response.choices[0].message.content.strip()
        return result if result else fallback
    except Exception:
        return fallback