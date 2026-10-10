import base64
import json
import logging
import os
import random
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from openai import OpenAI
import httpx

# Load local environment if present
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("wildnotes")

app = FastAPI(
    title="WildNotes",
    description="The Mindful Offline Naturalist & Sensory Field Companion",
    version="2.1.0",
)

# Enable CORS for deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
JOURNAL_FILE = os.path.join(BASE_DIR, "nature_journal.json")

# Config from environment (flexible for cloud deployments like Render, Railway, HuggingFace)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 7860))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CLOUD_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
CLOUD_OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

# Ensure static directories exist
os.makedirs(os.path.join(STATIC_DIR, "images"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)


# ==============================================================================
# JOURNAL UTILITIES
# ==============================================================================

def load_journal():
    if not os.path.exists(JOURNAL_FILE):
        return []
    try:
        with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error reading journal: {e}")
        return []


def save_journal(entries):
    try:
        with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving journal: {e}")


def add_journal_entry(title: str, notes: str, specimen_type: str = "Living Wonder", sensory_data: dict = None):
    entries = load_journal()
    new_entry = {
        "id": f"specimen-{int(datetime.now().timestamp() * 1000)}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "title": title,
        "specimen_type": specimen_type,
        "notes": notes,
        "sensory_data": sensory_data or {},
    }
    entries.insert(0, new_entry)
    save_journal(entries)
    return new_entry


# ==============================================================================
# HUMAN NATURALIST PROMPT TEMPLATES
# ==============================================================================

HUMAN_SYSTEM_PROMPT = (
    "You are an empathetic, encouraging field naturalist and nature guide who cares deeply about the earth. "
    "Your mission is NOT to overwhelm the user with sterile scientific jargon or robotic taxonomic essays. "
    "Your mission is to invite them to pause, breathe in the fresh air, and engage their physical senses with the living world around them.\n\n"
    "Look at this image and speak directly to the human observer in a warm, poetic, yet observant voice. Format your response into these 4 sections:\n\n"
    "### WHAT WE NOTICE TOGETHER\n"
    "One gentle, appreciative sentence naming this wonder (e.g. 'A delicate curl of fiddlehead fern emerging through the damp moss').\n\n"
    "### 3 SENSORY CHALLENGES (TOUCH GRASS)\n"
    "- 🔎 **Look Closer**: One sentence pointing their eyes toward a hidden micro-detail — a branching vein network, water droplet refraction, or velvet edge.\n"
    "- ✋ **Touch & Feel**: One physical prompt asking them to gently touch the specimen (is it cool, spongy, rough, silky, or damp?).\n"
    "- 👃 **Scent & Surroundings**: One prompt about the microclimate aroma — damp cedar, rain-soaked soil, or the companions growing right beside it.\n\n"
    "### FIELD INQUIRY\n"
    "One thoughtful question about this organism's quiet role in the larger web of life.\n\n"
    "### MINDFUL PAUSE\n"
    "One comforting sentence reminding the observer to take a slow deep breath, lower their shoulders, and feel grateful for this quiet moment outside."
)

# Handcrafted sensory observations for cloud demo fallback when Ollama is offline
DEMO_SENSORY_OBSERVATIONS = [
    {
        "title": "Delicate Spiral Fiddlehead Fern",
        "type": "Botanical Wonder",
        "analysis": (
            "### WHAT WE NOTICE TOGETHER\n"
            "A spiral fiddlehead fern cradling morning dew against the rich forest loam.\n\n"
            "### 3 SENSORY CHALLENGES (TOUCH GRASS)\n"
            "- 🔎 **Look Closer**: Trace the golden spiral ratio where the tiny fronds curl inward like a sleeping watch spring.\n"
            "- ✋ **Touch & Feel**: Rest the tip of your pinky on the stem — notice the cool, firm moisture and faint velvet fuzz.\n"
            "- 👃 **Scent & Surroundings**: Lean in close and breathe deeply; notice the clean scent of crushed chlorophyll and damp petrichor.\n\n"
            "### FIELD INQUIRY\n"
            "Why do you think ancient ferns adopted this tight spiral unfurling to protect their tender new growth?\n\n"
            "### MINDFUL PAUSE\n"
            "Take a slow breath of outdoor air. You don't have to hurry; nature never hurries, yet everything gets accomplished."
        )
    },
    {
        "title": "Golden Foliose Lichen & Oak Bark",
        "type": "Symbiotic Life",
        "analysis": (
            "### WHAT WE NOTICE TOGETHER\n"
            "A radiant crust of golden and sage lichen clinging tenaciously to damp oak bark.\n\n"
            "### 3 SENSORY CHALLENGES (TOUCH GRASS)\n"
            "- 🔎 **Look Closer**: Notice the miniature cup-shaped fruiting bodies and how the colors blend from sun-gold to soft sea-foam green.\n"
            "- ✋ **Touch & Feel**: Lightly graze your fingertips across the ridges — feel the papery crispness on top and the rough furrowed wood beneath.\n"
            "- 👃 **Scent & Surroundings**: Take a deep breath near the trunk; take in that rich, tannic wood aroma and damp forest cellar smell.\n\n"
            "### FIELD INQUIRY\n"
            "Remember that lichen is a partnership between fungi and algae — what quiet alliances are supporting your life today?\n\n"
            "### MINDFUL PAUSE\n"
            "Let your gaze soften. Feel your feet firmly planted on the earth beneath you."
        )
    },
    {
        "title": "Twin Bonnet Mushrooms & Velvet Moss",
        "type": "Fungi & Mycelium",
        "analysis": (
            "### WHAT WE NOTICE TOGETHER\n"
            "Two delicate bonnet mushrooms standing tall amidst a bed of emerald velvet moss.\n\n"
            "### 3 SENSORY CHALLENGES (TOUCH GRASS)\n"
            "- 🔎 **Look Closer**: Gaze under the cap to see the razor-thin radiating gills and the gentle morning light shining through.\n"
            "- ✋ **Touch & Feel**: Very gently touch the moss cushion around the base — notice how spongy and water-rich it feels.\n"
            "- 👃 **Scent & Surroundings**: Inhale near the forest floor; catch that distinctive earthy mushroom and composting leaf fragrance.\n\n"
            "### FIELD INQUIRY\n"
            "How does the underground mycelial network connect these mushrooms to the towering trees above them?\n\n"
            "### MINDFUL PAUSE\n"
            "Breathe in the quiet patience of the forest. The smallest beings often carry the greatest wonders."
        )
    }
]


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@app.get("/health")
def health_check():
    """Kubernetes/Docker/Cloud Provider liveness check."""
    return {"status": "healthy", "service": "wildnotes", "version": "2.1.0"}


@app.get("/api/status")
async def get_system_status():
    """Checks local Ollama or cloud vision availability."""
    # 1. Check local Ollama
    try:
        async with httpx.AsyncClient(timeout=2.0) as http_client:
            resp = await http_client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                active_model = "moondream:latest" if any("moondream" in m for m in models) else (
                    models[0] if models else "none"
                )
                return {
                    "connected": True,
                    "engine": "local_ollama",
                    "active_model": active_model,
                    "models": models,
                    "status_label": f"Local AI ({active_model.replace(':latest', '')})",
                }
    except Exception:
        pass

    # 2. Check Cloud API Key if configured
    if CLOUD_OPENAI_KEY:
        return {
            "connected": True,
            "engine": "cloud_openai",
            "active_model": "gpt-4o-mini",
            "models": ["gpt-4o-mini", "gpt-4o"],
            "status_label": "Cloud Vision Connected",
        }

    # 3. Fallback: Demo / Offline Simulator Mode (Zero-crash guarantee for cloud deployments)
    return {
        "connected": True,
        "engine": "curated_naturalist",
        "active_model": "Naturalist Engine (Offline)",
        "models": ["Naturalist Engine (Offline)"],
        "status_label": "Field Guide Ready",
    }


@app.get("/api/journal")
def get_journal():
    entries = load_journal()
    return {
        "total": len(entries),
        "entries": entries,
    }


@app.delete("/api/journal")
def clear_journal():
    save_journal([])
    return {"status": "cleared"}


@app.get("/api/journal/export")
def export_journal_markdown():
    entries = load_journal()
    md_content = "# 🌿 WildNotes — My Field Chronicle & Sensory Journal\n\n"
    md_content += f"*Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n"
    md_content += "> *\"In every walk with nature, one receives far more than he seeks.\" — John Muir*\n\n---\n\n"
    
    if not entries:
        md_content += "*No specimens recorded yet. Step outside, touch some grass, and log your first observation!*\n"
    else:
        for idx, item in enumerate(entries, 1):
            md_content += f"### {idx}. {item.get('title', 'Specimen Observation')}\n"
            md_content += f"- **Logged On**: `{item.get('timestamp')}`\n"
            md_content += f"- **Observation Category**: `{item.get('specimen_type', 'Living Wonder')}`\n\n"
            md_content += f"{item.get('notes')}\n\n"
            md_content += "---\n\n"

    headers = {"Content-Disposition": "attachment; filename=wildnotes_field_journal.md"}
    return HTMLResponse(content=md_content, media_type="text/markdown", headers=headers)


@app.post("/api/inspect")
async def inspect_specimen(
    file: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
    sample_id: Optional[str] = Form(None),
    model: Optional[str] = Form("moondream"),
):
    """Processes an image and returns thoughtful, tactile sensory prompts."""
    img_data_bytes = None

    if file and file.filename:
        img_data_bytes = await file.read()
    elif image_base64:
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        try:
            img_data_bytes = base64.b64decode(image_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")
    elif sample_id:
        sample_path = os.path.join(STATIC_DIR, "images", f"{sample_id}.jpg")
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                img_data_bytes = f.read()
        else:
            raise HTTPException(status_code=404, detail="Sample specimen not found")
    else:
        raise HTTPException(status_code=400, detail="Please snap or upload a photo of something in nature!")

    if not img_data_bytes:
        raise HTTPException(status_code=400, detail="Empty image data")

    b64_encoded = base64.b64encode(img_data_bytes).decode("utf-8")
    result_text = None
    engine_used = "local_ollama"

    # 1. Try local Ollama first
    try:
        ollama_client = OpenAI(base_url=f"{OLLAMA_BASE_URL}/v1", api_key="ollama")
        selected_model = model or "moondream"
        if selected_model == "moondream:latest":
            selected_model = "moondream"

        response = ollama_client.chat.completions.create(
            model=selected_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": HUMAN_SYSTEM_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_encoded}"},
                        },
                    ],
                }
            ],
            temperature=0.3,
            max_tokens=600,
            timeout=25.0,
        )
        result_text = response.choices[0].message.content or ""
    except Exception as ollama_err:
        logger.info(f"Local Ollama inference skipped/unavailable: {ollama_err}")

    # 2. Try Cloud API if configured and Ollama didn't return
    if not result_text and CLOUD_OPENAI_KEY:
        try:
            cloud_client = OpenAI(api_key=CLOUD_OPENAI_KEY, base_url=CLOUD_OPENAI_BASE_URL)
            response = cloud_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": HUMAN_SYSTEM_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64_encoded}"},
                            },
                        ],
                    }
                ],
                temperature=0.3,
                max_tokens=600,
            )
            result_text = response.choices[0].message.content or ""
            engine_used = "cloud_api"
        except Exception as cloud_err:
            logger.warning(f"Cloud vision fallback error: {cloud_err}")

    # 3. Fallback: Curated Naturalist Insight (Ensures 100% zero-crash experience on deployed sites)
    if not result_text:
        if sample_id and "fern" in sample_id:
            demo_pick = DEMO_SENSORY_OBSERVATIONS[0]
        elif sample_id and "lichen" in sample_id:
            demo_pick = DEMO_SENSORY_OBSERVATIONS[1]
        elif sample_id and "mushroom" in sample_id:
            demo_pick = DEMO_SENSORY_OBSERVATIONS[2]
        else:
            demo_pick = random.choice(DEMO_SENSORY_OBSERVATIONS)
        result_text = demo_pick["analysis"]
        engine_used = "curated_naturalist"

    # Extract friendly title for the journal
    specimen_title = "Living Wonder"
    specimen_type = "Botanical Wonder"
    lines = result_text.strip().split("\n")
    for i, line in enumerate(lines):
        if "WHAT WE NOTICE" in line.upper() or "SPECIMEN NOTICE" in line.upper():
            if i + 1 < len(lines):
                candidate = lines[i + 1].strip().strip("[]*# ")
                if candidate:
                    specimen_title = candidate[:80]
                    break

    entry = add_journal_entry(
        title=specimen_title,
        notes=result_text,
        specimen_type=specimen_type,
        sensory_data={"engine": engine_used},
    )

    return {
        "status": "success",
        "engine": engine_used,
        "entry": entry,
        "analysis": result_text,
        "total_discoveries": len(load_journal()),
    }


# Mount static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>WildNotes is starting up...</h1>")


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("🌿 WILDNOTES — Mindful Field Naturalist Companion")
    print("=" * 65)
    print(f"🚀 Running locally on: http://127.0.0.1:{PORT}")
    print(f"🌲 Serving host: {HOST}")
    print("🍃 Vision Engine: Ollama / Moondream (with zero-crash fallback)")
    print("=" * 65 + "\n")
    uvicorn.run("app:app", host=HOST, port=PORT, reload=False)