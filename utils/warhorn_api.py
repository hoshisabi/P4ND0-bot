import json
import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

load_dotenv()

WARHORN_APPLICATION_TOKEN = os.getenv("WARHORN_APPLICATION_TOKEN")
WARHORN_API_ENDPOINT = "https://warhorn.net/graphql"
EASTERN = ZoneInfo("America/New_York")
OBS_TITLE_PREFIX = "PandoDnD plays: "

# Final event_sessions_query including the 'uuid' field
event_sessions_query = """
#graphql
query EventSessions($events: [String!]!, $startsAfter: ISO8601DateTime) {
  eventSessions(events: $events, startsAfter: $startsAfter) {
    nodes {
      id
      name
      startsAt
      endsAt
      location
      maxPlayers
      availablePlayerSeats
      uuid
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
      playerWaitlistEntries {
        user {
          name
        }
      }
      scenario {
        name
        externalUrl
        gameSystem {
          name
        }
      }
    }
  }
}
"""


def parse_warhorn_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def start_of_today_eastern(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    now_et = now.astimezone(EASTERN)
    start_et = now_et.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_et.astimezone(timezone.utc)


def find_current_session(nodes: list, now: datetime | None = None) -> dict | None:
    """Pick the session /gotime should use: in-progress, then today, then next upcoming."""
    if not nodes:
        return None

    now = now or datetime.now(timezone.utc)

    in_progress = [
        s for s in nodes
        if parse_warhorn_dt(s["startsAt"]) <= now
        and (not s.get("endsAt") or now < parse_warhorn_dt(s["endsAt"]))
    ]
    if in_progress:
        return max(in_progress, key=lambda s: parse_warhorn_dt(s["startsAt"]))

    today = now.astimezone(EASTERN).date()
    today_sessions = [
        s for s in nodes
        if parse_warhorn_dt(s["startsAt"]).astimezone(EASTERN).date() == today
    ]
    if today_sessions:
        started_today = [s for s in today_sessions if parse_warhorn_dt(s["startsAt"]) <= now]
        if started_today:
            return max(started_today, key=lambda s: parse_warhorn_dt(s["startsAt"]))
        return min(today_sessions, key=lambda s: parse_warhorn_dt(s["startsAt"]))

    future = [s for s in nodes if parse_warhorn_dt(s["startsAt"]) > now]
    if future:
        return min(future, key=lambda s: parse_warhorn_dt(s["startsAt"]))

    return max(nodes, key=lambda s: parse_warhorn_dt(s["startsAt"]))


def format_obs_copy(session: dict) -> str:
    title = f"{OBS_TITLE_PREFIX}{session['name']}"
    lines = [
        f"Title for OBS: {title}",
        f'"Go Live Notification": {title}',
    ]
    scenario = session.get("scenario") or {}
    external_url = scenario.get("externalUrl")
    if external_url:
        lines.append(external_url)
    return "\n".join(lines)

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

    def get_event_sessions(self, event_slug, starts_after: datetime | None = None):
        if starts_after is None:
            starts_after = datetime.now(timezone.utc)
        return self.run_query(
            event_sessions_query,
            variables={"events": [event_slug], "startsAfter": starts_after.isoformat()},
        )

    def get_sessions_for_gotime(self, event_slug, now: datetime | None = None):
        now = now or datetime.now(timezone.utc)
        return self.get_event_sessions(event_slug, starts_after=start_of_today_eastern(now))

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