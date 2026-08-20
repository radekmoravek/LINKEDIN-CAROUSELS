# Solid Safety — LinkedIn carousels

Renders the Claude Design carousel template to a print-ready PDF. Slide content
lives in Notion; a manual GitHub Action turns it into a branded PDF and attaches
it back to the Notion row. Posting to LinkedIn stays manual — the API does not
support document (PDF carousel) posts for personal profiles.

## Local use

    python generate_carousel.py slides_example.txt --out zarazeni_objektu

Produces `zarazeni_objektu.pdf` plus a folder of PNGs. Requires `pillow` and `numpy`.

## Slide script

Blocks separated by `///`, each starting with a layout tag:

| Tag | Keys |
|---|---|
| `[cover]` | eyebrow, title, sub |
| `[list]` | eyebrow, title, `- Heading :: description` (2–4) |
| `[stat]` | eyebrow, number, lead, note |
| `[compare]` | eyebrow, title, left + items, right + items, note |
| `[table]` | eyebrow, title, `cols: A \| B \| C`, repeated `row:` lines, note |
| `[outro]` | eyebrow, title, sub — all optional |

The outro slide is appended automatically unless the script ends with one, so
the closing CTA and portrait are identical on every carousel. Edit the defaults
in `OUTRO_TITLE` / `OUTRO_SUB` at the top of `generate_carousel.py`.

## Notion workflow

1. New row in **LinkedIn Carousels**, slide script in a code block in the page body
2. Set **Status** to `Queued`
3. GitHub → Actions → **Render carousels** → *Run workflow*
4. PDF appears in the **PDF** column, Status flips to `Rendered`
5. Download it, post on LinkedIn via *Add a document*

Failures set Status to `Failed` and write the reason to **Last Error**.

## Setup

Repository secrets:

- `NOTION_TOKEN` — internal integration token (same one the publisher uses)
- `CAROUSEL_DB_ID` — `4c3fd9a4-02d0-406b-a872-32e21d54e53a`

**The integration must be invited to the new database** — open it in Notion,
`...` → Connections → add the integration. Without this every run 404s.

## Files

    generate_carousel.py   the renderer
    render_carousels.py    Notion queue -> PDF -> Notion attachment
    slides_example.txt     working example
    fonts/                 Source Serif 4 + Archivo, pinned static instances
    bg.jpg, portrait.jpg   artwork from the Claude Design project
