
from dotenv import load_dotenv

# --- NEW SDK IMPORT ---
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
for m in client.models.list():
    if 'generateContent' in m.supported_actions:
        print(m.name)