import os
import requests
from dotenv import load_dotenv

# Load env variables
load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    print("Error: GROQ_API_KEY not found in env.")
    exit(1)

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

try:
    response = requests.get("https://api.groq.com/openai/v1/models", headers=headers)
    if response.status_code == 200:
        models = response.json().get("data", [])
        print("Active Models List on Groq:")
        for model in models:
            print(f"- {model.get('id')}")
    else:
        print(f"Failed to fetch models. Status: {response.status_code}, Body: {response.text}")
except Exception as e:
    print(f"Error occurred: {e}")
