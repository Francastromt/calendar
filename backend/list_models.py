import google.generativeai as genai
import os

GENAI_KEY = "AIzaSyB5qpyeK4Y87w1flk5hOxohXv0-E-H76A0"
genai.configure(api_key=GENAI_KEY)

print("Listing available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error: {e}")
