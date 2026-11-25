"""Print an alert for every trade OPENED since the journal snapshot taken before this run.

Usage: python3 trade_alerts.py <journal before the run> <journal after the run> <status.txt>
Prints nothing when no trade was opened. The journal is append-only, so the new text is
whatever follows the old file's length.
"""
import re
import sys

before_path, after_path, status_path = sys.argv[1:4]
old = open(before_path, encoding="utf-8").read()
new = open(after_path, encoding="utf-8").read()
added = new[len(old):] if new.startswith(old) else new   # if the journal was reset, scan it all

opens = [s.strip() for s in re.split(r"\n(?=## #\d+ )", "\n" + added)
         if re.match(r"## #\d+ OPEN ", s.strip())]
if not opens:
    sys.exit(0)

status = open(status_path, encoding="utf-8").read().strip()
equity = status.splitlines()[0] if status else ""
out = ["@booneng new paper trade" + ("s" if len(opens) > 1 else "") + " opened.", ""]
for s in opens:
    out += [s.replace("## ", "### ", 1), ""]
out += ([f"`{equity}`", ""] if equity else []) + ["_Paper money only. Not financial advice._"]
print("\n".join(out))
