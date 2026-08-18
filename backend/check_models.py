import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    print("ERROR: OPENROUTER_API_KEY not found")
    exit(1)

response = requests.get(
    "https://openrouter.ai/api/v1/models",
    headers={
        "Authorization": f"Bearer {api_key}"
    },
    timeout=10
)

print("HTTP Status:", response.status_code)

if response.status_code != 200:
    print("ERROR:")
    print(response.text)
    exit(1)

models = response.json().get("data", [])

print(f"\nFound {len(models)} models\n")

for model in models:
    model_id = model.get("id", "")
    pricing = model.get("pricing", {})

    prompt_price = pricing.get("prompt", "unknown")
    completion_price = pricing.get("completion", "unknown")

    print(
        f"{model_id}"
        f" | input={prompt_price}"
        f" | output={completion_price}"
    )