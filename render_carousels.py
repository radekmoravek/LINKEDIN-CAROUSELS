#!/usr/bin/env python3
"""
render_carousels.py — pulls queued carousels out of Notion, renders them with
generate_carousel.py, and attaches the finished PDF back to the Notion row.

Run by .github/workflows/render-carousels.yml (manual trigger).

Environment:
    NOTION_TOKEN      internal integration token  (GitHub secret)
    CAROUSEL_DB_ID    the "LinkedIn Carousels" database id  (GitHub secret)
    NOTION_VERSION    optional, defaults below
    ONLY_PAGE_ID      optional, render just this one page

Flow per row with Status = Queued:
    read slide script from the page body
      -> render PDF
      -> upload to Notion
      -> attach to the PDF property, Status = Rendered
    on failure: Status = Failed, message written to Last Error
"""

import os
import re
import subprocess
import sys
import tempfile

import requests

TOKEN = os.environ.get("NOTION_TOKEN", "")
DB_ID = os.environ.get("CAROUSEL_DB_ID", "")
VERSION = os.environ.get("NOTION_VERSION", "2025-09-03")
ONLY = os.environ.get("ONLY_PAGE_ID", "").strip()

API = "https://api.notion.com/v1"
HEAD = {"Authorization": f"Bearer {TOKEN}", "Notion-Version": VERSION}
JSON_HEAD = {**HEAD, "Content-Type": "application/json"}

OUT_DIR = "out"


def die(msg):
    print(f"::error::{msg}")
    sys.exit(1)


# ---------------------------------------------------------------- notion io

def query_queued():
    """Find rows with Status = Queued. Handles both the data-source and the
    legacy database query endpoints, since which one applies depends on the
    Notion-Version pinned above."""
    body = {"filter": {"property": "Status", "select": {"equals": "Queued"}}}
    for path in (f"{API}/data_sources/{DB_ID}/query", f"{API}/databases/{DB_ID}/query"):
        r = requests.post(path, headers=JSON_HEAD, json=body, timeout=30)
        if r.status_code == 200:
            return r.json().get("results", [])
        if r.status_code not in (400, 404):
            die(f"Notion query failed [{r.status_code}]: {r.text[:400]}")
    die("Could not query the database — check CAROUSEL_DB_ID and that the "
        "integration has been invited to the database.")


def get_page(page_id):
    r = requests.get(f"{API}/pages/{page_id}", headers=HEAD, timeout=30)
    if r.status_code != 200:
        die(f"Could not read page {page_id}: {r.text[:300]}")
    return r.json()


def rich_text(parts):
    return "".join(p.get("plain_text", "") for p in parts)


def read_script(page_id):
    """Slide script lives in the page body. Prefer code blocks; if there are
    none, rebuild it from paragraphs, bullets and dividers."""
    blocks, cursor = [], None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        r = requests.get(f"{API}/blocks/{page_id}/children", headers=HEAD,
                         params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Could not read page body: {r.text[:300]}")
        data = r.json()
        blocks += data.get("results", [])
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    code = [rich_text(b["code"]["rich_text"]) for b in blocks if b["type"] == "code"]
    if code:
        return "\n\n".join(code).strip()

    lines = []
    for b in blocks:
        t = b["type"]
        if t == "divider":
            lines.append("///")
        elif t == "bulleted_list_item":
            lines.append("- " + rich_text(b[t]["rich_text"]))
        elif t in ("paragraph", "heading_1", "heading_2", "heading_3",
                   "numbered_list_item", "quote"):
            lines.append(rich_text(b[t]["rich_text"]))
    return "\n".join(lines).strip()


def upload_pdf(path, filename):
    r = requests.post(f"{API}/file_uploads", headers=JSON_HEAD, timeout=30,
                      json={"filename": filename, "content_type": "application/pdf",
                            "mode": "single_part"})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"file_uploads create failed: {r.text[:300]}")
    obj = r.json()
    upload_id, url = obj["id"], obj["upload_url"]

    with open(path, "rb") as fh:
        r = requests.post(url, headers=HEAD, timeout=120,
                          files={"file": (filename, fh, "application/pdf")})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"file upload failed: {r.text[:300]}")
    return upload_id


def patch_page(page_id, props):
    r = requests.patch(f"{API}/pages/{page_id}", headers=JSON_HEAD,
                       json={"properties": props}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"page update failed: {r.text[:300]}")


def mark_failed(page_id, message):
    try:
        patch_page(page_id, {
            "Status": {"select": {"name": "Failed"}},
            "Last Error": {"rich_text": [{"text": {"content": message[:1900]}}]},
        })
    except Exception as exc:                                  # noqa: BLE001
        print(f"::warning::could not write failure back to Notion: {exc}")


# ---------------------------------------------------------------- rendering

def slugify(name, fallback):
    s = name.lower()
    for a, b in zip("áčďéěíňóřšťúůýž", "acdeeinorstuuyz"):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or fallback


def plain_prop(page, key):
    prop = page["properties"].get(key, {})
    if prop.get("type") == "rich_text":
        return rich_text(prop["rich_text"]).strip()
    if prop.get("type") == "title":
        return rich_text(prop["title"]).strip()
    return ""


def render(page):
    page_id = page["id"]
    title = plain_prop(page, "Name") or "carousel"
    slug = plain_prop(page, "Slug") or slugify(title, page_id[:8])
    print(f"→ {title}  ({slug})")

    script = read_script(page_id)
    if not script:
        raise RuntimeError("The page body is empty — no slide script found.")
    if "[" not in script:
        raise RuntimeError("No layout tags found. Each slide must start with "
                           "[cover] / [list] / [stat] / [compare] / [table] / [outro].")

    os.makedirs(OUT_DIR, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8",
                                     delete=False) as fh:
        fh.write(script)
        script_path = fh.name

    out_base = os.path.join(OUT_DIR, slug)
    proc = subprocess.run(
        [sys.executable, "generate_carousel.py", script_path,
         "--out", out_base, "--no-png"],
        capture_output=True, text=True)
    os.unlink(script_path)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:1500])

    pdf = f"{out_base}.pdf"
    upload_id = upload_pdf(pdf, f"{slug}.pdf")
    patch_page(page_id, {
        "PDF": {"files": [{"type": "file_upload",
                           "file_upload": {"id": upload_id},
                           "name": f"{slug}.pdf"}]},
        "Status": {"select": {"name": "Rendered"}},
        "Last Error": {"rich_text": []},
    })
    print(f"  attached {slug}.pdf")


def main():
    if not TOKEN or not DB_ID:
        die("NOTION_TOKEN and CAROUSEL_DB_ID must be set.")

    pages = [get_page(ONLY)] if ONLY else query_queued()
    if not pages:
        print("Nothing queued — set a row's Status to Queued and run again.")
        return

    failures = 0
    for page in pages:
        try:
            render(page)
        except Exception as exc:                              # noqa: BLE001
            failures += 1
            print(f"::warning::{exc}")
            mark_failed(page["id"], str(exc))

    print(f"\ndone — {len(pages) - failures} rendered, {failures} failed")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
