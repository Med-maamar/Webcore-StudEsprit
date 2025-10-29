from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

# google-api-python-client based implementation
try:  # Lazy imports so the app can run without these packages installed
    from googleapiclient.discovery import build  # type: ignore
except Exception:  # pragma: no cover
    build = None  # type: ignore
try:
    from google.oauth2 import service_account as sa  # type: ignore
except Exception:  # pragma: no cover
    sa = None  # type: ignore
try:
    from google.oauth2.credentials import Credentials as OAuthCredentials  # type: ignore
except Exception:  # pragma: no cover
    OAuthCredentials = None  # type: ignore
try:
    from google.auth.transport.requests import Request  # type: ignore
except Exception:  # pragma: no cover
    Request = None  # type: ignore

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def _pseudo_meet_link() -> str:
    import random, string

    def block(n):
        return "".join(random.choices(string.ascii_lowercase, k=n))

    return f"https://meet.google.com/{block(3)}-{block(4)}-{block(3)}"


def _as_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()


def _creds_service_account():
    if sa is None or Request is None:
        return None
    path_or_json = os.getenv("SERVICE_ACCOUNT_JSON")
    subject = os.getenv("GOOGLE_CALENDAR_USER_EMAIL") or os.getenv("MEET_ORGANIZER_EMAIL")
    if not (path_or_json and subject):
        return None
    try:
        if os.path.isfile(path_or_json):
            with open(path_or_json, "r", encoding="utf-8") as f:
                info = json.load(f)
        else:
            info = json.loads(path_or_json)
        creds = sa.Credentials.from_service_account_info(info, scopes=SCOPES, subject=subject)
        creds.refresh(Request())
        return creds
    except Exception as e:  # pragma: no cover
        logger.warning("Service account error: %s", e)
        return None


def _creds_oauth():
    if OAuthCredentials is None or Request is None:
        return None
    # Access token direct
    token = os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN") or os.getenv("GOOGLE_ACCESS_TOKEN")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN") or os.getenv("GOOGLE_REFRESH_TOKEN")
    try:
        if token:
            creds = OAuthCredentials(
                token=token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES,
            )
            return creds
        if refresh_token and client_id and client_secret:
            creds = OAuthCredentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES,
            )
            creds.refresh(Request())
            return creds
    except Exception as e:  # pragma: no cover
        logger.warning("OAuth credentials error: %s", e)
    return None


def _calendar_service():
    if build is None:
        return None
    creds = _creds_service_account() or _creds_oauth()
    if not creds:
        return None
    try:
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:  # pragma: no cover
        logger.warning("Calendar build error: %s", e)
        return None


def generate_meet_link(title: str, date_time: datetime, duration: int = 30) -> str:
    """Create a Calendar event with Meet and return the Meet URL.

    Uses google-api-python-client; falls back to a pseudo code if no credentials.
    """
    service = _calendar_service()
    if service is None:
        return _pseudo_meet_link()

    tz = os.getenv("GOOGLE_CALENDAR_TIMEZONE") or "UTC"
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID") or "primary"
    start = date_time
    end = date_time + timedelta(minutes=int(duration or 30))

    body = {
        "summary": title or "Entretien",
        "start": {"dateTime": _as_rfc3339(start), "timeZone": tz},
        "end": {"dateTime": _as_rfc3339(end), "timeZone": tz},
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    try:
        event = (
            service.events().insert(calendarId=calendar_id, body=body, conferenceDataVersion=1).execute()
        )
        conf = (event or {}).get("conferenceData") or {}
        for ep in conf.get("entryPoints", []):
            if ep.get("entryPointType") == "video" and ep.get("uri"):
                return ep["uri"]
        link = event.get("hangoutLink")
        if link:
            return link
    except Exception as e:  # pragma: no cover
        logger.warning("Calendar insert failed: %s", e)
    return _pseudo_meet_link()
