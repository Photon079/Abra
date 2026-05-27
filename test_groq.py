import os
from dotenv import load_dotenv
load_dotenv()

from groq import Groq

groq_key = os.getenv("GROQ_API_KEY")
print("Key found:", groq_key[:15] if groq_key else "None")

try:
    client = Groq(api_key=groq_key)
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "user", "content": "Say hello!"}
        ],
        model="llama-3.3-70b-versatile"
    )
    print("Success! Response:", chat_completion.choices[0].message.content)
except Exception as e:
    print("Error:", e)
