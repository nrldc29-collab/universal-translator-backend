"""AILang standard library — built-in functions available in all .ai files."""
import json
import re

__all__ = [
    "lower", "upper", "trim", "length", "contains", "starts_with", "ends_with",
    "join", "split", "replace", "slice", "keys", "values",
    "to_json", "extract_json", "get_value", "dict_set", "dict_get",
    "int_", "float_", "str_", "bool_",
    "print_", "format_",
]

def lower(s): return str(s).lower()
def upper(s): return str(s).upper()
def trim(s): return str(s).strip()
def length(x): return len(x) if x is not None else 0
def contains(s, sub): return str(sub).lower() in str(s).lower() if s and sub else False
def starts_with(s, prefix): return str(s).startswith(str(prefix))
def ends_with(s, suffix): return str(s).endswith(str(suffix))
def join(lst, sep=""): return str(sep).join(str(x) for x in (lst or []))
def split(s, sep=" "): return str(s).split(str(sep))
def replace(s, old, new): return str(s).replace(str(old), str(new))
def slice(obj, start, end=None):
    try:
        if end is None: return obj[int(start):]
        return obj[int(start):int(end)]
    except Exception: return obj
def keys(d): return list(d.keys()) if isinstance(d, dict) else []
def values(d): return list(d.values()) if isinstance(d, dict) else []

def to_json(obj):
    try: return json.dumps(obj, ensure_ascii=False)
    except Exception: return str(obj)

def extract_json(s):
    """Extract the first JSON object or array from a string."""
    if not s: return False
    s = str(s).strip()
    # try direct parse
    try: return json.loads(s)
    except Exception: pass
    # try extracting from markdown code block
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if m:
        try: return json.loads(m.group(1).strip())
        except Exception: pass
    # find first { or [
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        idx = s.find(start_char)
        if idx >= 0:
            depth = 0
            for i in range(idx, len(s)):
                if s[i] == start_char: depth += 1
                elif s[i] == end_char: depth -= 1
                if depth == 0:
                    try: return json.loads(s[idx:i+1])
                    except Exception: break
    return False

def get_value(d, key, default=None):
    if isinstance(d, dict): return d.get(str(key), default)
    if isinstance(d, list):
        try: return d[int(key)]
        except Exception: return default
    return default

def dict_set(d, key, value):
    result = dict(d) if isinstance(d, dict) else {}
    result[str(key)] = value
    return result

def dict_get(d, key, default=None):
    return get_value(d, key, default)

def int_(x):
    try: return int(x)
    except Exception: return 0

def float_(x):
    try: return float(x)
    except Exception: return 0.0

def str_(x): return str(x) if x is not None else ""
def bool_(x): return bool(x)
def print_(x): print(x); return x
def format_(fmt, *args): return str(fmt).format(*args)

