import os
import re
import httpx
from pathlib import Path
from dotenv import load_dotenv

# repo root is the parent of scripts/
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")

def main():
    print("=== STRAVA OAUTH EXCHANGE HELPER ===")
    print("1. Open the following URL in your browser and authorize:")
    print(f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri=http://localhost&response_type=code&scope=activity:read_all")
    print("\n2. After clicking Authorize, copy the FULL URL of the resulting blank page.")
    
    url_input = input("\n3. Paste the FULL URL here: ").strip()
    if not url_input:
        print("Error: URL cannot be empty.")
        return

    # Parse code from URL
    match = re.search(r"[?&]code=([a-f0-9]+)", url_input)
    if not match:
        print("Error: Could not find 'code' parameter in the pasted URL.")
        print("Make sure you copy the entire URL (e.g., http://localhost/?state=&code=...)")
        return
    
    code = match.group(1)
    print(f"\nExtracted Authorization Code: {code}")
    print("Exchanging code for a high-permission access token...")

    # Exchange token
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    }
    
    try:
        response = httpx.post("https://www.strava.com/oauth/token", data=payload)
        res_data = response.json()
        
        if response.status_code == 200:
            access_token = res_data.get("access_token")
            refresh_token = res_data.get("refresh_token")
            print("\nSuccess! Generated high-permission token.")
            print(f"Access Token: {access_token}")
            
            # Update .env file
            with open(ENV_PATH, "r") as f:
                content = f.read()
            
            # Replace access token
            pattern = r'STRAVA_ACCESS_TOKEN\s*=\s*["\']?[a-f0-9]+["\']?'
            replacement = f'STRAVA_ACCESS_TOKEN="{access_token}"'
            
            if re.search(pattern, content):
                new_content = re.sub(pattern, replacement, content)
            else:
                new_content = content + f'\nSTRAVA_ACCESS_TOKEN="{access_token}"\n'
                
            with open(ENV_PATH, "w") as f:
                f.write(new_content)
                
            print(f"\nSuccessfully updated {ENV_PATH} with your new token!")
            print("You are fully set up!")
        else:
            print("\nExchange Failed:")
            print(response.text)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
