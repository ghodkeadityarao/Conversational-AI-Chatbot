# Conversational AI Chatbot

This project is a Flask-based chatbot application that uses Google's Generative AI (`gemini-pro`) to provide intelligent conversational responses. It features user intent handling, context awareness, and a web-based chat interface.

## Features

- **AI-Powered Chat**: Integrates with the Gemini model to generate natural and contextual responses.
- **User Context**: Stores user-specific information (e.g., names) for personalized conversations.
- **Basic Intent Handling**: Provides quick responses for common queries such as the current time or weather.
- **Error Handling**: Gracefully manages errors and provides user-friendly messages.
- **Web Interface**: Includes a simple web-based chat interface.

---

## Technologies Used

- **Python**: Core programming language for the backend.
- **Flask**: Web framework for serving the application and managing routes.
- **Google Generative AI**: Powered by the Gemini model for chatbot capabilities.
- **HTML**: For the chat interface (`chat.html`).
- **Regular Expressions (re)**: For cleaning and formatting responses.
- **dotenv**: For managing environment variables securely.

---

## Setup and Configuration

1. Clone the repository:

  ```bash
  git clone https://github.com/ghodkeadityarao/Conversational-AI-Chatbot.git
  ```

  ``` bash
  cd Conversational-AI-Chatbot
  ```

2. Install Requirements:
  ```bash
  pip install -r requirements.txt 
  ```

3. Set up your environment variables: (Enter the API Key in the space given)
  ``` bash
  GOOGLE_API_KEY=your_google_api_key
  ```

To get your personal API key, go to `Google AI Studio` and create API key.
Website: `https://aistudio.google.com/app/apikey`

4. Run the application:
  ``` bash
  python app.py
  ```

5. Open your browser and navigate to:
  ```bash
  http://127.0.0.1:5000
  ```

6. You can click on `help` to understand how the bot works.

## How to Use the Bot

Once the chatbot is running, follow these steps to interact with it effectively:

1. **Access the Chat Interface**:
   - Open your web browser and navigate to:
     
     ```plaintext
     http://127.0.0.1:5000
     ```

2. **Start a Conversation**:
   - Type your message into the chat input box and press `"Send"`.

3. **Introduce Yourself** (Optional):
   - You can personalize the chat by introducing yourself with a message like: `My name is [Your Name]`
   - The bot will remember your name during the session and use it to personalize responses.

4. **Ask Questions or Chat**:
   - Feel free to ask questions or have a general conversation. The bot can:
     - Provide information (e.g., "What time is it?")
     - Help with simple queries (e.g., "Tell me a joke.")
     - Respond intelligently to your messages.

5. **Receive AI-Generated Responses**:
   - For messages without pre-programmed intents, the bot uses Google Generative AI (`gemini-pro`) to generate context-aware and conversational responses.

6. **Error Handling**:
   - If the bot doesn't understand your message or an issue arises, it will respond with:
     ```
     I’m sorry, I didn’t understand that. Could you please rephrase?
     ```

8. **Stop or Reset the Chat**:
   - To refresh the chat session or reset the bot's memory, simply reload the page.

---

## Sample Interface and Conversation

- `Interface`
  
![image](https://github.com/user-attachments/assets/cbc623bb-f20c-4d2d-8012-f72b9c60da78)

- `Conversation`

![image](https://github.com/user-attachments/assets/8c5c1780-4e1f-4a28-bf42-09b56fefab20)

![image](https://github.com/user-attachments/assets/89bbd14d-428d-465d-bf7f-f5bc8b79faf8)

  
