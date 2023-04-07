import os
import sys
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from flask import Flask, request, make_response, jsonify

# Initialize the Bolt app with the signing secret
app = App(signing_secret=os.environ["SLACK_SIGNING_SECRET"])

# Your bot's Slack API token
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]

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

    # Respond with a greeting
    response = f"Hello, {user_name}! :wave:"
    say(response)

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
    flask_app.run(port=3000)
