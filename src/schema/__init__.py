"""The shape of every JSON document cct reads or writes, and the checks for it.

- config.py      ~/.cct/config.json
- usage.py       ~/.cct/usage/<account>.json
- session.py     ~/.cct/sessions/<key>.json
- statusline.py  the JSON Claude Code sends to statusline scripts on stdin

Types are TypedDicts, so the documents stay plain dicts in JSON and in code.
Readers of state files return None or drop a field when data is damaged:
a hand-edited file must never crash the statusline.
"""
