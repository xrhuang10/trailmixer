import re

def _to_seconds(v):
    # Already numeric
    if isinstance(v, (int, float)):
        return float(v)

    # Nested dicts from APIs: {"sec": 1.23}, {"seconds": 1.23}, {"text": "0s (00:00)"}
    if isinstance(v, dict):
        for k in ("sec", "seconds", "value", "time", "start", "end", "text"):
            if k in v:
                try:
                    return _to_seconds(v[k])
                except Exception:
                    pass
        raise ValueError(f"Unsupported timestamp dict: {v!r}")

    if not isinstance(v, str):
        raise ValueError(f"Unsupported timestamp type: {type(v)}")

    s = v.strip()

    # If it contains a parenthesized timecode, prefer that: "0s (00:00)" -> "00:00"
    m = re.search(r"\(([^)]+)\)", s)
    if m:
        s = m.group(1).strip()

    # Ends with 's' (e.g., "12.5s")
    if s.endswith("s"):
        try:
            return float(s[:-1])
        except Exception:
            pass

    # HH:MM:SS(.mmm)
    if re.match(r"^\d{1,2}:\d{2}:\d{2}(\.\d+)?$", s):
        hh, mm, ss = s.split(":")
        return int(hh) * 3600 + int(mm) * 60 + float(ss)

    # MM:SS(.mmm)
    if re.match(r"^\d{1,2}:\d{2}(\.\d+)?$", s):
        mm, ss = s.split(":")
        return int(mm) * 60 + float(ss)

    # Plain float-able string
    return float(s)
