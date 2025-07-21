import json
import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

WARHORN_APPLICATION_TOKEN = os.getenv("WARHORN_APPLICATION_TOKEN")
WARHORN_API_ENDPOINT = "https://warhorn.net/graphql"

# Corrected event_sessions_query to use startsAfter and ISO8601DateTime
# MODIFIED: Added 'links { url name }' selection
event_sessions_query = """
query EventSessions($events: [String!]!, $startsAfter: ISO8601DateTime) {
  eventSessions(events: $events, startsAfter: $startsAfter) {
    nodes {
      id
      name
      startsAt
      location
      maxPlayers
      availablePlayerSeats
      gmSignups {
        user {
          name
        }
      }
      playerSignups {
        user {
          name
        }
      }
      scenario {
        name
        gameSystem {
          name
        }
      }
      links { # NEW: Request links directly
        url
        name
      }
    }
  }
}
"""

class WarhornClient:
    def __init__(self, api_endpoint, app_token):
        self.api_endpoint = api_endpoint
        self.app_token = app_token

    def run_query(self, query, variables=None):
        headers = {
            "Authorization": f"Bearer {self.app_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = requests.post(self.api_endpoint, headers=headers, data=json.dumps(payload))
        print(f"Warhorn API response status: {response.status_code}")
        print(f"Warhorn API raw response: {response.text}")
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError as e:
            print(f"JSON decoding error: {e}")
            print(f"Response content: {response.text}")
            raise

    def get_event_sessions(self, event_slug):
        current_utc_time = datetime.now(timezone.utc).isoformat()
        return self.run_query(event_sessions_query, variables={"events": [event_slug], "startsAfter": current_utc_time})

    # REMOVED: get_single_event_session method as it's no longer needed

if __name__ == "__main__":
    client = WarhornClient(WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN)
    pandodnd_slug = "pandodnd"
    try:
        print(f"Attempting to fetch event sessions for slug: {pandodnd_slug}")
        sessions = client.get_event_sessions(pandodnd_slug)
        print("Successfully fetched event sessions:")
        print(json.dumps(sessions, indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Error fetching event sessions: {e}")