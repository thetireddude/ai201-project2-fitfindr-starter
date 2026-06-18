# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tool Inventory

Your README submission must document each tool's name, inputs, and return value. **These must exactly match your actual function signatures in `tools.py`.** Your documented interfaces will be checked against your actual function signatures in `tools.py` — if the parameter count or types contradict what's in the code, you may not receive full credit for that tool.

---

## Interaction Walkthrough

<!-- Walk through a complete interaction step by step: natural language query → each tool call (and why) → final fit card.
     Walk through this carefully — it's how graders follow your agent's reasoning without a live demo.
     Use a specific example — do not leave this as a template. -->

**User query:**
vintage graphic tee size XXS under $30


**Step 1 — Tool called:**
- Tool: search_listings
- Input: description='vintage graphic tee', size='XXS', max_price=30.0
- Why this tool: agent intially searches for listings based on the user's query
- Output: 0 result(s)

**Step 2 — Tool called:**
- Tool: search_listings
- Input: description='vintage graphic tee', size=None, max_price=30.0
- Why this tool: agent drops the size constraint and performs a relaxed search to find other similar listings
- Output: 20 result(s), top: 'Y2K Baby Tee — Butterfly Print'

**Step 3 — Tool called:**
- Tool: suggest_outfit
- Input: item='Y2K Baby Tee — Butterfly Print'
- Why this tool: the agent has now found a listing so it moves on to the next step
- Output: 'Outfit 1: Pair the Y2K Baby Tee with the baggy straight-leg jeans for a cute, casual look that blends Y2K charm with str'...

**Step 4 — Tool called:**
- Tool: create_fit_card
- Input: item='Y2K Baby Tee — Butterfly Print'
- Why this tool: the agent moves on to the last step of creating a caption as the last tool call successfully outputted.
- Output: "I just scored the cutest Y2K Baby Tee — Butterfly Print on depop for $18.0 and I'm obsessed with how it adds a touch of "...

**Final output to user:**
```
I did not find any listing for vintage graphic tee, size XXS, under $30. However I found listings for vintage graphic tee, under $30.

Y2K Baby Tee — Butterfly Print
$18.00  ·  depop  ·  Size S/M
Condition: excellent

Super cute early 2000s baby tee with butterfly graphic. Fitted crop length. Tag says medium but fits like a small.
```

---

## Error Handling and Fail Points

<!-- For each tool, describe the specific failure mode and what your agent does in response.
     This maps to the error handling section of the rubric (F5-C1). -->

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results match the query| perform relaxed searches to find more listings. If no listings found at all, returns "No listings found — try broader keywords or remove size/price filters."|
| `suggest_outfit` | Wardrobe is empty| returns styling tips as output from suggest_outfit|
| `create_fit_card` | Outfit input is missing or incomplete| returns "Could not generate fit card: missing outfit details."|

---

## Spec Reflection

<!-- Answer both questions with at least 2–3 sentences each. -->

**One way planning.md helped during implementation:**

Writing out a complete interaction step-by-step order before touching any code, made implementing the agent feel much more straightforward. Each step I'd planned mapped almost directly to a block of code. If I hadn't figured out that logic ahead of time, I probably would have gotten stuck on edge cases mid-implementation, like what to do when both size and price are too restrictive at once, or what fields the session needed so that handle_query() could build the relaxed-search message for the user.

**One divergence from your spec, and why:**

In my error handling table I wrote that suggest_outfit with an empty wardrobe should set session["error"]. When I actually implemented it, I realized that made the experience worse — users with no wardrobe would get an error and see two empty panels, even though suggest_outfit was still returning useful styling tips. So I changed it to treat an empty wardrobe as a normal case: the loop keeps going and the user still gets a full response. The spec was a little vague on whether this was a real failure or just a fallback, and this felt like the right call once I could see it running.

---

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.
