import os
import sys
import openai
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

# Listen for app_mention events
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

    # Get the message text
    message_text = body["event"]["text"]

    # Send the message to ChatGPT
    try:
        gpt_response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=f"{user_name}: {message_text}\nAI:",
            max_tokens=50,
            n=1,
            stop=None,
            temperature=0.5,
        )

        # Extract the generated response
        chatgpt_response = gpt_response.choices[0].text.strip()

    except Exception as e:
        print(f"Error: {e}")
        chatgpt_response = "I'm sorry, I couldn't process your message."

    # Send the reply to the Slack channel
    say(chatgpt_response)

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

if __name__ == "__main__":
    # Start the Flask app
    flask_app.run(host="0.0.0.0", port=8080)
