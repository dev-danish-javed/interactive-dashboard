from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
# pip install -q -U google-genai
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

if False:
    response_old = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            thinking_config= types.ThinkingConfig(thinking_budget=0),
            system_instruction="You are a car. Your name is Neko."
        ),
        contents = "Hello, how are you ?",
    )

chat = client.chats.create(model="gemini-2.5-flash")

response = chat.send_message("I have 2 dogs in my house.")
print(response.text)

response = chat.send_message("How many paws are in my house?")
print(response.text)

print(''.center(150, '='), end="\n\n")
for message in chat.get_history():
    print(f'role - {message.role}',end=": ")
    print(message.parts[0].text)