#!/usr/bin/env python3
"""Refresh the citation numbers on the Research tab from Google Scholar.

Google Scholar has no public API and blocks browser requests from other sites,
so the site cannot fetch counts live the way it fetches GitHub stars. Instead,
run this script now and then; it reads the public profile page and rewrites
the numbers in index.html in place:

    python3 tools/refresh_citations.py          # update index.html
    python3 tools/refresh_citations.py --check  # only print what would change

Each citation pill carries data-citations="<profile>:<paper id> ..." (one or
more Scholar entry ids, summed).
"""

import html
import re
import sys
import urllib.request

PROFILE = "u6Y0pW4AAAAJ"
URL = f"https://scholar.google.com/citations?user={PROFILE}&hl=en&pagesize=100"
INDEX = "index.html"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")


def fetch_profile():
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        page = resp.read().decode("utf-8", "replace")
    per_paper = {}
    for row in re.findall(r'<tr class="gsc_a_tr">(.*?)</tr>', page, re.S):
        ident = re.search(r'citation_for_view=([^&"]+)', row)
        count = re.search(r'class="gsc_a_ac gs_ibl"[^>]*>(\d*)</a>', row)
        if ident:
            per_paper[html.unescape(ident.group(1))] = int(count.group(1) or 0) if count else 0
    if not per_paper:
        sys.exit("could not parse the Scholar page; it may be rate limiting, try again later")
    return per_paper


def main():
    check = "--check" in sys.argv
    per_paper = fetch_profile()
    src = open(INDEX, encoding="utf-8").read()
    out = src
    changes = []

    def swap(pattern, new_value, label):
        nonlocal out
        m = re.search(pattern, out)
        if not m:
            changes.append(f"  {label}: marker not found")
            return
        if m.group(1) != str(new_value):
            changes.append(f"  {label}: {m.group(1)} -> {new_value}")
            out = out[:m.start(1)] + str(new_value) + out[m.end(1):]

    for m in re.finditer(r'data-citations="([^"]+)">(\d+)<', src):
        ids = m.group(1).split()
        missing = [i for i in ids if i not in per_paper]
        if missing:
            changes.append(f"  {ids[0]}: not on the profile any more ({', '.join(missing)})")
            continue
        total = sum(per_paper[i] for i in ids)
        swap(r'data-citations="' + re.escape(m.group(1)) + r'">(\d+)<', total, ids[0])

    # a pill with zero citations stays hidden; show it once the paper is cited
    def toggle_hidden(m):
        tag, middle, count = m.group(1), m.group(2), int(m.group(3))
        has_hidden = " hidden" in tag
        if count > 0 and has_hidden:
            changes.append("  showing a pill that now has citations")
            tag = tag.replace(" hidden", "")
        elif count == 0 and not has_hidden:
            changes.append("  hiding a pill with zero citations")
            tag = tag[:-1] + " hidden>"
        return tag + middle + str(count) + "<"

    pill = re.compile(r'(<a [^>]*class="gh-stat cite-stat"[^>]*>)'
                      r'(\s*<ion-icon[^>]*></ion-icon>\s*<span data-citations="[^"]+">)(\d+)<')
    out = pill.sub(toggle_hidden, out)

    if not changes:
        print("already up to date")
        return
    print("changes:" if not check else "would change:")
    print("\n".join(changes))
    if not check and out != src:
        open(INDEX, "w", encoding="utf-8").write(out)
        print(f"wrote {INDEX}")


if __name__ == "__main__":
    main()
