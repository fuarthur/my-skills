#!/usr/bin/env python3
"""Read configured ICS sources into candidates; classification stays with the skill."""

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


MAX_BYTES = 5 * 1024 * 1024
MAX_EVENTS = 10000


class SourceError(Exception):
    """Only a fixed diagnostic code is exposed, never an exception containing a URL."""


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        if (new.scheme, new.hostname, new.port) != (old.scheme, old.hostname, old.port):
            raise SourceError("redirect_requires_review")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_payload(source):
    if source["kind"] == "ics_file":
        with Path(source["path"]).expanduser().open("rb") as stream:
            payload = stream.read(MAX_BYTES + 1)
    else:
        parsed = urlsplit(source["feed_url"])
        if parsed.scheme == "webcal":
            parsed = parsed._replace(scheme="https")
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise SourceError("https_feed_required")
        request = Request(urlunsplit(parsed), headers={
            "User-Agent": "DeadlineSkills/1.0", "Accept": "text/calendar",
        })
        with build_opener(SameOriginRedirect()).open(request, timeout=20) as stream:
            payload = stream.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise SourceError("feed_too_large")
    if not payload.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"BEGIN:VCALENDAR"):
        raise SourceError("not_an_icalendar")
    return payload


def temporal_properties(component):
    for key in ("DTSTART", "DTEND", "RECURRENCE-ID", "EXDATE", "RDATE"):
        value = component.get(key)
        for prop in value if isinstance(value, list) else [value]:
            if prop is not None:
                for item in getattr(prop, "dts", [prop]):
                    yield item, getattr(prop, "params", {})


def localize_floating(value, zone):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=zone)
    if isinstance(value, tuple):
        return tuple(localize_floating(item, zone) for item in value)
    return value


def feed_aliases(value):
    aliases = {value}
    parsed = urlsplit(value)
    if parsed.scheme in {"webcal", "https"}:
        aliases.update(urlunsplit(parsed._replace(scheme=scheme)) for scheme in ("webcal", "https"))
    return aliases


def extract_candidates(payload, source, start, end, display_zone):
    from icalendar import Calendar
    import recurring_ical_events

    cal = Calendar.from_ical(payload)
    if cal.name != "VCALENDAR" or any(getattr(c, "errors", []) for c in cal.walk()):
        raise SourceError("invalid_calendar")
    zone_name = str(cal.get("X-WR-TIMEZONE", source.get("timezone", str(display_zone))))
    try:
        floating_zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise SourceError("unresolved_timezone") from None
    floating_basis = "calendar_timezone" if "X-WR-TIMEZONE" in cal else (
        "source_timezone" if source.get("timezone") else "display_timezone"
    )
    # X-WR conversion rewrites even UTC recurrence anchors into local wall time.
    # Preserve aware instants; use the calendar zone only for floating values.
    cal.pop("X-WR-TIMEZONE", None)
    bases = {}
    for component in cal.walk("VEVENT"):
        if not component.get("UID") or not component.get("DTSTART"):
            raise SourceError("event_missing_uid_or_start")
        dt = component.decoded("DTSTART")
        bases[str(component["UID"])] = (
            floating_basis if isinstance(dt, datetime) and dt.tzinfo is None else "event"
        )
        for prop, params in temporal_properties(component):
            value = getattr(prop, "dt", None)
            if isinstance(value, datetime) and value.tzinfo is None and params.get("TZID"):
                raise SourceError("unresolved_timezone")
            prop.dt = localize_floating(value, floating_zone)
        rule = component.get("RRULE")
        if rule and str(rule.get("FREQ", [""])[0]).upper() in {"SECONDLY", "MINUTELY"}:
            raise SourceError("high_frequency_recurrence_requires_review")
        if rule and "UNTIL" in rule:
            rule["UNTIL"] = [localize_floating(value, floating_zone) for value in rule["UNTIL"]]

    # Expand both the instant window and its local dates, then filter precisely.
    # UTC-only boundaries can otherwise omit a date-only event in a positive offset.
    last_date = end.date() + (timedelta(days=1) if end.time() != time.min else timedelta())
    query_start = min(
        datetime.combine(start.date(), time.min, display_zone).astimezone(timezone.utc),
        datetime.combine(start.date(), time.min, timezone.utc),
    )
    query_end = max(end.astimezone(timezone.utc), datetime.combine(last_date, time.min, timezone.utc))
    events = recurring_ical_events.of(cal).between(query_start, query_end)
    if len(events) > MAX_EVENTS:
        raise SourceError("too_many_occurrences")
    rows = []
    for component in events:
        if str(component.get("STATUS", "")).upper() == "CANCELLED":
            continue
        due = component.decoded("DTSTART")
        if isinstance(due, datetime):
            if due.tzinfo is None:
                due = due.replace(tzinfo=floating_zone)
            local_due = due.astimezone(display_zone)
            if not start.timestamp() <= local_due.timestamp() < end.timestamp():
                continue
            precision, display_due = "datetime", local_due.isoformat()
        elif isinstance(due, date):
            if not start.date() <= due < last_date:
                continue
            precision, display_due = "date", due.isoformat()
        else:
            raise SourceError("unsupported_date")
        uid = str(component["UID"])
        link = str(component.get("URL", ""))
        if urlsplit(link).scheme not in {"https", "http"} or link in feed_aliases(source.get("feed_url", "")):
            link = ""
        rows.append({
            "source_id": source["id"], "source_label": source["label"],
            "uid": uid, "title": str(component.get("SUMMARY", "(untitled)")),
            "due": display_due, "due_original": due.isoformat(), "precision": precision,
            "timezone_basis": bases.get(uid, "event"), "url": link,
            "submission_status": "unknown",
        })
    warnings = ["vtodo_requires_separate_reader"] if cal.walk("VTODO") else []
    return rows, warnings


def read_sources(profile, start, end, display_zone):
    reports, candidates = [], []
    for source in profile["sources"]:
        report = {key: source[key] for key in ("id", "label", "kind")}
        reports.append(report)
        status = source.get("status", "pending")
        if status != "ready":
            report["status"] = status
            continue
        if source["kind"] not in {"ics", "ics_file"}:
            report["status"] = "needs_connector" if source["kind"] == "calendar" else "needs_agent_read"
            continue
        try:
            payload = read_payload(source)
            rows, warnings = extract_candidates(payload, source, start, end, display_zone)
            candidates.extend(rows)
            report.update(status="ok", count=len(rows), warnings=warnings)
            report["freshness"] = "snapshot" if source["kind"] == "ics_file" else "fetched_now"
            if source["kind"] == "ics_file":
                report["snapshot_at"] = source.get("snapshot_at")
        except SourceError as error:
            report.update(status="error", error=str(error))
        except HTTPError as error:
            report.update(status="error", error=f"http_{error.code}")
        except (OSError, URLError, TimeoutError):
            report.update(status="error", error="read_failed")
        except (KeyError, ValueError, TypeError):
            report.update(status="error", error="invalid_calendar_or_source")
        except Exception:
            # Parser failures can quote private feed content; keep their text out of logs.
            report.update(status="error", error="calendar_parse_failed")
    candidates.sort(key=lambda row: (parse_time(row["due"], display_zone).timestamp(), row["source_id"], row["title"]))
    return {"sources": reports, "candidates": candidates}


def load_profile(path):
    profile = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or profile.get("version") != 1:
        raise ValueError("profile")
    ZoneInfo(profile["timezone"])
    if type(profile.get("default_days", 7)) is not int or not 1 <= profile.get("default_days", 7) <= 366:
        raise ValueError("days")
    sources = profile.get("sources")
    if not isinstance(sources, list):
        raise ValueError("sources")
    seen = set()
    for source in sources:
        if not isinstance(source, dict) or any(not isinstance(source.get(k), str) or not source[k] for k in ("id", "label", "kind")):
            raise ValueError("source")
        if source["id"] in seen or source["kind"] not in {"ics", "ics_file", "calendar", "web", "file"}:
            raise ValueError("source")
        if source.get("status", "pending") not in {"ready", "pending", "disabled"}:
            raise ValueError("status")
        seen.add(source["id"])
    return profile


def parse_time(value, zone):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        if "T" in value or " " in value:
            raise ValueError("time_without_offset")
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(zone)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="~/.config/deadline-skills/sources.json")
    parser.add_argument("--now", help="Current time with offset; useful for deterministic replays")
    parser.add_argument("--days", type=int, help="Number of local dates, including today (default: profile or 7)")
    parser.add_argument("--start", help="Override start: ISO date or datetime with offset")
    parser.add_argument("--end", help="Exclusive end: ISO date or datetime with offset")
    args = parser.parse_args()
    try:
        profile = load_profile(args.config)
        zone = ZoneInfo(profile["timezone"])
    except FileNotFoundError:
        print(json.dumps({"error": "missing_config"}))
        return 2
    except (OSError, ValueError, KeyError, TypeError, ZoneInfoNotFoundError):
        print(json.dumps({"error": "invalid_profile"}))
        return 2
    try:
        now = parse_time(args.now, zone) if args.now else datetime.now(zone)
        start = parse_time(args.start, zone) if args.start else now
        days = args.days if args.days is not None else profile.get("default_days", 7)
        if not 1 <= days <= 366:
            raise ValueError("days")
        end = parse_time(args.end, zone) if args.end else datetime.combine(start.date() + timedelta(days=days), time.min, zone)
        if not start.timestamp() < end.timestamp() or end.timestamp() - start.timestamp() > 366 * 86400 + 3600:
            raise ValueError("window")
    except (ValueError, OverflowError):
        print(json.dumps({"error": "invalid_window"}))
        return 2
    try:
        import icalendar  # noqa: F401
        import recurring_ical_events  # noqa: F401
    except ImportError:
        print(json.dumps({"error": "missing_dependencies", "action": "Install scripts/requirements.txt in a private virtual environment"}))
        return 2
    result = read_sources(profile, start, end, zone)
    result.update(checked_at=now.isoformat(), timezone=str(zone), window={
        "start": start.isoformat(), "end_exclusive": end.isoformat(),
    })
    # Do not leak a private feed URL even if it occurs in an event title or link.
    private_urls = set()
    for source in profile["sources"]:
        secret = source.get("feed_url")
        if isinstance(secret, str) and secret:
            private_urls.update(feed_aliases(secret))
    for row in result["candidates"]:
        if row["url"] in private_urls:
            row["url"] = ""
    output = json.dumps(result, ensure_ascii=False)
    for secret in sorted(private_urls, key=len, reverse=True):
        output = output.replace(json.dumps(secret, ensure_ascii=False)[1:-1], "[private feed]")
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
