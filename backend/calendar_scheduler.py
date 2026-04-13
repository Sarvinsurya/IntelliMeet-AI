"""
backend/calendar_scheduler.py
==============================
Use HR's Google Calendar: find free slots and create interview events
when a candidate scores above threshold.
"""
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Business hours configuration
DEFAULT_DAYS_AHEAD = 7
DEFAULT_DURATION_MINUTES = 30
DEFAULT_TZ = "Asia/Kolkata"  # Indian Standard Time (IST)
# Working hours: 10:00 AM to 7:30 PM IST
# Latest meeting can start at 6:30 PM (to end by 7:30 PM for 60-min meetings)
WORK_START_HOUR = 10
WORK_START_MINUTE = 0
WORK_END_HOUR = 19  # 7 PM
WORK_END_MINUTE = 30  # 7:30 PM
# Latest meeting start time (must end before WORK_END)
LATEST_MEETING_START_HOUR = 18  # 6 PM
LATEST_MEETING_START_MINUTE = 30  # 6:30 PM


def _parse_rfc3339(s: str) -> datetime:
    """Parse RFC3339 string to datetime (timezone-aware)."""
    s = s.replace("Z", "+00:00")
    if s.endswith("+00:00"):
        return datetime.fromisoformat(s)
    return datetime.fromisoformat(s)


def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _is_within_business_hours(dt: datetime, duration_minutes: int) -> bool:
    """
    Check if a datetime slot is within business hours (10 AM - 7:30 PM IST).
    Meeting must start after 10:00 AM and end before 7:30 PM.
    Latest start time: 6:30 PM (for 60-min meeting to end by 7:30 PM).
    """
    import pytz
    
    # Convert to IST
    ist = pytz.timezone('Asia/Kolkata')
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_ist = dt.astimezone(ist)
    
    # Start time check: must be >= 10:00 AM
    start_limit = dt_ist.replace(hour=WORK_START_HOUR, minute=WORK_START_MINUTE, second=0, microsecond=0)
    if dt_ist < start_limit:
        return False
    
    # Calculate meeting end time
    meeting_end = dt_ist + timedelta(minutes=duration_minutes)
    
    # End time check: must be <= 7:30 PM
    end_limit = dt_ist.replace(hour=WORK_END_HOUR, minute=WORK_END_MINUTE, second=0, microsecond=0)
    if meeting_end > end_limit:
        return False
    
    # Latest start time check: ensure meeting can complete within business hours
    latest_start = dt_ist.replace(hour=LATEST_MEETING_START_HOUR, minute=LATEST_MEETING_START_MINUTE, second=0, microsecond=0)
    if dt_ist > latest_start:
        return False
    
    return True


def _get_next_business_hour_slot(dt: datetime, duration_minutes: int):
    """
    Given a datetime, return the next available business hour slot.
    If dt is before 10 AM, return 10 AM same day.
    If dt is after 6:30 PM (or would end after 7:30 PM), return 10 AM next day.
    """
    import pytz
    ist = pytz.timezone('Asia/Kolkata')
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_ist = dt.astimezone(ist)
    
    # If before 10 AM, move to 10 AM same day
    if dt_ist.hour < WORK_START_HOUR or (dt_ist.hour == WORK_START_HOUR and dt_ist.minute < WORK_START_MINUTE):
        next_slot = dt_ist.replace(hour=WORK_START_HOUR, minute=WORK_START_MINUTE, second=0, microsecond=0)
        return next_slot.astimezone(timezone.utc)
    
    # If meeting would end after 7:30 PM or start after 6:30 PM, move to 10 AM next day
    meeting_end = dt_ist + timedelta(minutes=duration_minutes)
    end_limit = dt_ist.replace(hour=WORK_END_HOUR, minute=WORK_END_MINUTE, second=0, microsecond=0)
    latest_start = dt_ist.replace(hour=LATEST_MEETING_START_HOUR, minute=LATEST_MEETING_START_MINUTE, second=0, microsecond=0)
    
    if meeting_end > end_limit or dt_ist > latest_start:
        # Move to 10 AM next day
        next_day = dt_ist + timedelta(days=1)
        next_slot = next_day.replace(hour=WORK_START_HOUR, minute=WORK_START_MINUTE, second=0, microsecond=0)
        return next_slot.astimezone(timezone.utc)
    
    return dt


def get_free_slots(creds, calendar_id: str = "primary", days_ahead: int = DEFAULT_DAYS_AHEAD,
                   duration_minutes: int = DEFAULT_DURATION_MINUTES):
    """
    Query calendar freebusy and return list of (start, end) free slots, each at least duration_minutes.
    Returns list of (datetime, datetime) in UTC.
    """
    from googleapiclient.discovery import build
    service = build("calendar", "v3", credentials=creds)
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days_ahead)
    body = {
        "timeMin": _to_rfc3339(now),
        "timeMax": _to_rfc3339(time_max),
        "items": [{"id": calendar_id}],
    }
    try:
        resp = service.freebusy().query(body=body).execute()
    except Exception as e:
        logger.warning("Freebusy query failed: %s", e)
        raise RuntimeError(f"Calendar freebusy failed: {e}. Enable Calendar API and add scopes (see backend/CALENDAR_SETUP.txt), then delete token.json and reconnect.") from e
    cal = resp.get("calendars", {}).get(calendar_id, {})
    busy_list = cal.get("busy", [])
    errors = cal.get("errors", [])
    if errors:
        err_msg = "; ".join(str(e) for e in errors)
        logger.warning("Calendar %s errors: %s", calendar_id, errors)
        raise RuntimeError(f"Calendar returned errors: {err_msg}") from None

    # Sort and merge overlapping busy intervals
    delta = timedelta(minutes=duration_minutes)
    if not busy_list:
        # Entire window is free; find first business hour slot
        next_slot = _get_next_business_hour_slot(now, duration_minutes)
        if _is_within_business_hours(next_slot, duration_minutes):
            yield (next_slot, next_slot + delta)
        return
    busy_times = []
    for b in busy_list:
        start = _parse_rfc3339(b["start"])
        end = _parse_rfc3339(b["end"])
        busy_times.append((start, end))
    busy_times.sort(key=lambda x: x[0])
    merged = []
    for s, e in busy_times:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    # Free slots = gaps between merged busy, and before first / after last
    free_slots = []
    delta = timedelta(minutes=duration_minutes)
    # Before first busy
    if merged:
        gap_start = now
        gap_end = merged[0][0]
        if (gap_end - gap_start) >= delta:
            free_slots.append((gap_start, gap_end))
    # Between busy intervals
    for i in range(len(merged) - 1):
        gap_start = merged[i][1]
        gap_end = merged[i + 1][0]
        if (gap_end - gap_start) >= delta:
            free_slots.append((gap_start, gap_end))
    # After last busy
    if merged:
        gap_start = merged[-1][1]
        gap_end = time_max
        if (gap_end - gap_start) >= delta:
            free_slots.append((gap_start, gap_end))
    if not merged:
        free_slots = [(now, time_max)]

    # Return first free chunk within business hours
    for slot_start, slot_end in free_slots:
        if (slot_end - slot_start) >= delta:
            # Adjust slot_start to next business hour if needed
            adjusted_start = _get_next_business_hour_slot(slot_start, duration_minutes)
            
            # Check if adjusted slot still fits within the gap and business hours
            adjusted_end = adjusted_start + delta
            if adjusted_end <= slot_end and _is_within_business_hours(adjusted_start, duration_minutes):
                yield (adjusted_start, adjusted_end)
                return
            
            # If adjusted slot doesn't fit in this gap, try finding any slot within this gap
            # that fits business hours by checking 30-minute increments
            current = slot_start
            while current + delta <= slot_end:
                if _is_within_business_hours(current, duration_minutes):
                    yield (current, current + delta)
                    return
                current += timedelta(minutes=30)
    
    # If no slots found in any gap, return None (caller will handle "no free slots" error)


def create_calendar_event(creds, calendar_id: str, start_dt: datetime, end_dt: datetime,
                         summary: str, description: str = "", attendee_emails: list = None,
                         add_google_meet: bool = True):
    """Create a calendar event, optionally with a Google Meet link. Returns created event dict or None on failure."""
    import uuid
    from googleapiclient.discovery import build
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    body = {
        "summary": summary,
        "description": description or "",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": DEFAULT_TZ},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": DEFAULT_TZ},
    }
    if attendee_emails:
        body["attendees"] = [{"email": e} for e in attendee_emails if e]
    if add_google_meet:
        body["conferenceData"] = {
            "createRequest": {
                "requestId": uuid.uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
    try:
        service = build("calendar", "v3", credentials=creds)
        event = service.events().insert(
            calendarId=calendar_id,
            body=body,
            sendUpdates="all",
            conferenceDataVersion=1,
        ).execute()
        return event
    except Exception as e:
        logger.warning("Calendar event insert failed: %s", e)
        raise RuntimeError(f"Calendar event create failed: {e}. Check CALENDAR_SETUP.txt and that token has calendar scope.") from e


def schedule_interview(creds, calendar_id: str, candidate_name: str, candidate_email: str,
                       job_id: str, duration_minutes: int = DEFAULT_DURATION_MINUTES,
                       days_ahead: int = DEFAULT_DAYS_AHEAD, interviewer_email: str = None):
    """
    Find first free slot and create an interview event on the HR calendar. Invite candidate (and optionally interviewer).
    If interviewer_email is set, they are added as attendee so they get the invite and reschedule runs if they decline.
    Returns dict: { "ok": bool, "event_link": str|None, "start": str, "end": str, "error": str|None }
    """
    try:
        slots = list(get_free_slots(creds, calendar_id=calendar_id, days_ahead=days_ahead, duration_minutes=duration_minutes))
    except Exception as e:
        return {"ok": False, "event_link": None, "start": None, "end": None, "error": str(e)}
    if not slots:
        return {"ok": False, "event_link": None, "start": None, "end": None, "error": "No free slots found in the next %d days." % days_ahead}
    start_dt, end_dt = slots[0]
    summary = f"Interview: {candidate_name}"
    description = f"Automatically scheduled for candidate above threshold (Job: {job_id})."
    attendee_emails = []
    if candidate_email:
        attendee_emails.append(candidate_email)
    if interviewer_email and (interviewer_email or "").strip():
        ie = (interviewer_email or "").strip()
        if ie and ie.lower() != (candidate_email or "").strip().lower():
            attendee_emails.append(ie)
    try:
        event = create_calendar_event(creds, calendar_id, start_dt, end_dt, summary, description, attendee_emails, add_google_meet=True)
    except Exception as e:
        return {"ok": False, "event_link": None, "start": start_dt.isoformat(), "end": end_dt.isoformat(), "error": str(e)}
    if not event:
        return {"ok": False, "event_link": None, "start": start_dt.isoformat(), "end": end_dt.isoformat(), "error": "Failed to create event"}
    # htmlLink opens the event in the HR's Google Calendar (event is on this calendar)
    link = event.get("htmlLink") or event.get("link")
    meet_link = None
    if event.get("conferenceData", {}).get("entryPoints"):
        for ep in event["conferenceData"]["entryPoints"]:
            if ep.get("entryPointType") == "video" or ep.get("entryPointType") == "videoCall":
                meet_link = ep.get("uri")
                break
    meet_link = meet_link or event.get("conferenceData", {}).get("hangoutLink")
    return {
        "ok": True,
        "event_link": link,
        "meet_link": meet_link,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "event_id": event.get("id"),
        "calendar_id": calendar_id,
        "candidate_invited": bool(candidate_email),
        "candidate_email": candidate_email or None,
        "error": None,
    }


def get_event_attendee_response(creds, calendar_id: str, event_id: str, attendee_email: str):
    """
    Get the response status of an attendee for an event.
    Returns: "accepted" | "declined" | "tentative" | "needsAction" | None (if not found or error).
    """
    from googleapiclient.discovery import build
    try:
        service = build("calendar", "v3", credentials=creds)
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        email_lower = (attendee_email or "").strip().lower()
        for att in event.get("attendees", []):
            if (att.get("email") or "").lower() == email_lower:
                return att.get("responseStatus", "needsAction")
        return "needsAction"
    except Exception as e:
        logger.warning("Get event attendee response failed: %s", e)
        return None


def get_event_any_attendee_declined(creds, calendar_id: str, event_id: str):
    """
    Check if any attendee (candidate or interviewer) has declined the event.
    Returns: (any_declined: bool, declined_emails: list[str])
    """
    from googleapiclient.discovery import build
    try:
        service = build("calendar", "v3", credentials=creds)
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        declined = []
        for att in event.get("attendees", []):
            if (att.get("responseStatus") or "").lower() == "declined":
                declined.append((att.get("email") or "").strip())
        return (len(declined) > 0, declined)
    except Exception as e:
        logger.warning("Get event attendees failed: %s", e)
        return (False, [])


def cancel_event(creds, calendar_id: str, event_id: str):
    """Cancel (delete) a calendar event. Returns True on success."""
    from googleapiclient.discovery import build
    try:
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(calendarId=calendar_id, eventId=event_id, sendUpdates="all").execute()
        return True
    except Exception as e:
        logger.warning("Cancel event failed: %s", e)
        return False
