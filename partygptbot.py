import os
import sys
import openai
import sqlite3
import re
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import Flask, request, make_response, jsonify

# Initialize the Bolt app with the signing secret
app = App(signing_secret=os.environ["SLACK_SIGNING_SECRET"])

# Your bot's Slack API token
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]

# Set up the OpenAI client 
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
openai.api_key = OPENAI_API_KEY

# Initialize the Slack WebClient
client = WebClient(token=SLACK_BOT_TOKEN)

@app.event("app_mention")
def handle_app_mention(body, say):
    # Get user information
    user = body["event"]["user"]
    try:
        user_info = client.users_info(user=user)
        user_name = user_info["user"]["real_name"]
    except SlackApiError as e:
        print(f"Error: {e}")
        user_name = "User"

    # Get the bot user ID
    try:
        auth_info = client.auth_test()
        bot_user_id = auth_info["user_id"]
    except SlackApiError as e:
        print(f"Error: {e}")
        bot_user_id = None

    # Get the message text
    message_text = body["event"]["text"]
    if bot_user_id:
        message_text = re.sub(f"<@{bot_user_id}>", "", message_text).strip()

    # Save the user's message to the database
    conn = sqlite3.connect("conversation_history.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversation_history (speaker, message) VALUES (?, ?)",
        (user_name, message_text),
    )
    conn.commit()

    # Retrieve the conversation history from the database
    cursor.execute("SELECT speaker, message FROM conversation_history")
    conversation_history = cursor.fetchall()
    conn.close()

    # Compose the messages for gpt-3.5-turbo
    messages = [{"role": "system", "content": "You are an AI trained by OpenAI. You have a fun, freewheeling, party-on vibe!"}]
    for speaker, message in conversation_history:
        messages.append({"role": speaker.lower(), "content": message})

    messages.append({"role": "user", "content": message_text})

    # Send the message to ChatGPT
    try:
        gpt_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=200,
            n=1,
            stop=None,
            temperature=0.7,  # Increase the temperature for a more creative and varied output
        )

        # Extract the generated response
        chatgpt_response = gpt_response.choices[0].message["content"].strip()

    except Exception as e:
        print(f"Error: {e}")
        chatgpt_response = "I'm sorry, I couldn't process your message."

    # Save the AI response to the database
    conn = sqlite3.connect("conversation_history.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversation_history (speaker, message) VALUES (?, ?)",
        ("AI", chatgpt_response),
    )
    conn.commit()
    conn.close()

    # Send the reply to the Slack channel
    say(chatgpt_response)

@app.command("/reset_history")
def reset_history(ack, respond, command):
    # Acknowledge the command request
    ack()

    # Delete the conversation history for the channel from the database
    conn = sqlite3.connect("conversation_history.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversation_history")
    conn.commit()
    conn.close()

    # Respond with a confirmation message
    response_text = "Conversation history has been reset."
    try:
        respond(response_type="in_channel", text=response_text)
    except Exception as e:
        print(f"Error sending response: {e}")

def init_db():
    conn = sqlite3.connect("conversation_history.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker TEXT NOT NULL,
            message TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

# Initialize the Flask app
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# Define the route to handle Slack events
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    # Check if the incoming request is a URL verification event
    if request.is_json and "challenge" in request.json:
        response = make_response(request.json["challenge"], 200)
        response.content_type = "text/plain"
        return response 

    # Handle other Slack events
    return handler.handle(request)

# Handle /reset_history
@flask_app.route("/slack/reset_history",methods=["POST"])
def slack_reset_history():
    return handler.handle(request)

if __name__ == "__main__":
    # Start the Flask app
    init_db()
    flask_app.run(host="0.0.0.0", port=8080)
