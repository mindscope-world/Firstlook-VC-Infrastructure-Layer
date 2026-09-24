"""WebVTT transcript parsing (Zoom exports transcripts as VTT)."""

from __future__ import annotations

import re

_TIMING = re.compile(r"(\d{1,2}:)?(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{1,2}:)?(\d{2}):(\d{2})[.,](\d{3})")


def _seconds(h: str | None, m: str, s: str, ms: str) -> float:
    return int((h or "0:")[:-1]) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_vtt(text: str) -> list[dict]:
    """Return segments [{speaker, start, end, text}]. Speaker comes from a
    "Name: text" prefix (Zoom) or a <v Name> voice tag (WebVTT spec)."""
    segments: list[dict] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [x for x in block.strip().splitlines() if x.strip()]
        timing_idx = next((i for i, x in enumerate(lines) if _TIMING.search(x)), None)
        if timing_idx is None:
            continue
        m = _TIMING.search(lines[timing_idx])
        assert m is not None
        start = _seconds(m.group(1), m.group(2), m.group(3), m.group(4))
        end = _seconds(m.group(5), m.group(6), m.group(7), m.group(8))
        body = " ".join(lines[timing_idx + 1 :]).strip()
        speaker = None
        voice = re.match(r"<v\s+([^>]+)>(.*?)(</v>)?$", body)
        if voice:
            speaker, body = voice.group(1).strip(), voice.group(2).strip()
        else:
            named = re.match(r"^([^:]{1,60}):\s+(.*)$", body)
            if named:
                speaker, body = named.group(1).strip(), named.group(2).strip()
        body = re.sub(r"<[^>]+>", "", body)
        if not body:
            continue
        # Merge consecutive cues from the same speaker.
        if segments and segments[-1]["speaker"] == speaker and start - segments[-1]["end"] < 2:
            segments[-1]["text"] += " " + body
            segments[-1]["end"] = end
        else:
            segments.append({"speaker": speaker, "start": start, "end": end, "text": body})
    return segments
