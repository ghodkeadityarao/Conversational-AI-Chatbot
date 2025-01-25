import datetime
import os
import re

import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

# Load environment variables
load_dotenv()

# Configure the Generative AI model
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-pro")
chat = model.start_chat(history=[])

# Flask app
app = Flask(__name__)

# Dictionary to store user context
user_context = {}

# Function to clean and format the bot response
def clean_and_format_response(response):
    response = re.sub(r"\s+", " ", response)  # Replace multiple spaces/newlines with a single space
    response = response.strip()  # Remove leading/trailing spaces

    response = response.replace("**", "")  
    response = response.replace("* ", "\n") 
    return response

def handle_intents(user_message):
    if "what time" in user_message.lower() or "current time" in user_message.lower():
        return f"The current time is {datetime.datetime.now().strftime('%H:%M:%S')}."

    elif "weather" in user_message.lower():
        return "I’m sorry, I don't have access to real-time weather data. Could you check your local weather service?"

    return None 

# Main Page
@app.route("/", methods=["GET", "POST"])
def home():
    return render_template("chat.html")

# Chat
@app.route("/chat", methods=["POST"])
def chat_route():
    user_message = request.json.get("message") # Get the user's message from the request
    if not user_message:
        return jsonify({"error": "Message is required!"}), 400
    
    if "my name is" in user_message.lower():    # Extract the user's name
        name = user_message.split("my name is")[-1].strip()
        user_context['name'] = name
        return jsonify({"user": user_message, "bot": f"Nice to meet you, {name}! How can I assist you today?"})

    intent_response = handle_intents(user_message)
    if intent_response:
        return jsonify({"user": user_message, "bot": intent_response})

    try:
        response = chat.send_message(user_message, stream=False) # Send the user's message to the model
        bot_message = "".join(chunk.text for chunk in response) # Get the bot's response from the model

        clean_bot_message = clean_and_format_response(bot_message)
        
        if not clean_bot_message:
            clean_bot_message = "I’m sorry, I didn’t understand that. Could you please rephrase?"

        return jsonify({"user": user_message, "bot": clean_bot_message}) # Return the bot's response
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500 # Return an error if something goes wrong

if __name__ == "__main__":
    app.run(debug=True) # Run the Flask app
