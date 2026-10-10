import base64
import json
import os
from datetime import datetime
import gradio as gr
from openai import OpenAI
from PIL import Image

# 1. Connect to local Ollama Vision
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

JOURNAL_FILE = "nature_journal.json"


def encode_image(image_path):
    """Encodes PIL image to Base64 for Ollama VLM."""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


def inspect_nature(image):
    if image is None:
        return "⚠️ Please take a photo or upload an image of something in nature!", get_journal_history()

    # Save temp image
    temp_path = "temp_capture.jpg"
    image.save(temp_path)
    base64_img = encode_image(temp_path)

    system_prompt = (
        "You are an encouraging field naturalist and nature guide. "
        "The goal is NOT to give an exhaustive scientific species essay. "
        "Instead, the goal is to get the user to put their phone down and physically observe the specimen.\n\n"
        "Output format strictly in Markdown:\n"
        "1. **Specimen Notice**: 1 sentence stating what broad element of nature this is (e.g., Tree bark, Lichen, Fern).\n"
        "2. **3 Sensory Clues (Touch Grass Challenge)**:\n"
        "   - 🔎 *Look Closer*: Point out an intricate micro-pattern (veins, spots, edges).\n"
        "   - ✋ *Touch & Feel*: A prompt to touch it (roughness, dampness, temperature, fuzziness).\n"
        "   - 👃 *Smell or Environment*: A prompt about its scent, moisture, or what is growing right next to it.\n"
        "3. **Field Inquiry**: 1 question to ponder about its ecological role."
    )

    # Call local open-weight vision model
    response = client.chat.completions.create(
        model="moondream",  # or "moondream"
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
                    },
                ],
            }
        ],
        temperature=0.3,
    )

    result_text = response.choices[0].message.content

    # Save to local journal
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "notes": result_text[:120].replace("\n", " "),
    }
    save_to_journal(entry)

    return result_text, get_journal_history()


def save_to_journal(entry):
    entries = []
    if os.path.exists(JOURNAL_FILE):
        try:
            with open(JOURNAL_FILE, "r") as f:
                entries = json.load(f)
        except Exception:
            entries = []
    entries.insert(0, entry)
    with open(JOURNAL_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def get_journal_history():
    if not os.path.exists(JOURNAL_FILE):
        return "*Your journal is empty. Take a photo outdoors to log your first discovery!*"
    try:
        with open(JOURNAL_FILE, "r") as f:
            entries = json.load(f)
        output = "### 📓 Recent Trail Discoveries\n"
        for item in entries[:5]:
            output += f"- **{item['timestamp']}**: {item['notes']}...\n"
        return output
    except Exception:
        return ""


# Gradio UI Layout
custom_theme = gr.themes.Soft(primary_hue="emerald")

with gr.Blocks(theme=custom_theme, title="Nature Detective") as demo:
    gr.Markdown("# 🌿 Nature Detective: The Micro-World Explorer")
    gr.Markdown(
        "**Theme: Touch Grass.** Don't just identify nature on a screen — inspect it with your hands and senses. "
        "Powered by an offline open-weight vision model."
    )

    with gr.Row():
        with gr.Column(scale=1):
            cam_input = gr.Image(
                sources=["webcam", "upload"],
                type="pil",
                label="Snap a leaf, bark, rock, or insect",
            )
            investigate_btn = gr.Button("🔍 Investigate Specimen", variant="primary")

        with gr.Column(scale=1):
            guide_output = gr.Markdown(
                label="Observation Clues",
                value="*Snap a photo and click Investigate to receive your field challenge...*",
            )
            journal_display = gr.Markdown(value=get_journal_history())

    investigate_btn.click(
        fn=inspect_nature,
        inputs=[cam_input],
        outputs=[guide_output, journal_display],
    )

if __name__ == "__main__":
    demo.launch(share=True)