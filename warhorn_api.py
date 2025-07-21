import json
import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

WARHORN_APPLICATION_TOKEN = os.getenv("WARHORN_APPLICATION_TOKEN")
WARHORN_API_ENDPOINT = "https://warhorn.net/graphql"

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
        # Removed coverImageUrl as it does not exist on Scenario type
      }
    }
  }
}
"""

# NEW QUERY FOR WAITLIST
waitlist_query = """
query SessionWaitlistEntries($eventSessionId: ID!) {
  sessionWaitlistEntries(eventSession: $eventSessionId) {
    nodes {
      id
      user {
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
        print(f"Warhorn API raw response: {response.text}") # Keep this for debugging
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

    # NEW METHOD TO GET WAITLIST
    def get_session_waitlist(self, session_id):
        try:
            result = self.run_query(waitlist_query, variables={"eventSessionId": session_id})
            if "data" in result and "sessionWaitlistEntries" in result["data"]:
                return result["data"]["sessionWaitlistEntries"]["nodes"]
            return []
        except Exception as e:
            print(f"Error fetching waitlist for session {session_id}: {e}")
            return []

if __name__ == "__main__":
    client = WarhornClient(WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN)
    pandodnd_slug = "pandodnd"
    try:
        print(f"Attempting to fetch event sessions for slug: {pandodnd_slug}")
        sessions_data = client.get_event_sessions(pandodnd_slug)
        print("Successfully fetched event sessions:")
        print(json.dumps(sessions_data, indent=2)) # Print the full response now

        # Example of fetching waitlist for the first session (if any)
        if sessions_data and "data" in sessions_data and sessions_data["data"]["eventSessions"]["nodes"]:
            first_session_id = sessions_data["data"]["eventSessions"]["nodes"][0]["id"]
            print(f"\nAttempting to fetch waitlist for session ID: {first_session_id}")
            waitlist = client.get_session_waitlist(first_session_id) 
            print("Successfully fetched waitlist:")
            print(json.dumps(waitlist, indent=2))

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")