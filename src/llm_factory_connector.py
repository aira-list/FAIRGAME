import requests
import os
import dotenv

# Load environment variables from a .env file
dotenv.load_dotenv()
url = os.environ['LLM_FACTORY_URL']

def execute_prompt(llm, prompt):
    payload = {
    "model": llm, 
    "prompt": prompt
    }
    response = requests.post(f"{url}/execute_prompt", json=payload)
    if response.status_code == 200:
        try:
            response = response.json().get("response")
        except ValueError:
            response = response.text.strip()   
    
    return response