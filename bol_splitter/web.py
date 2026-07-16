"""A tiny local web UI for the BOL splitter.

Tab 1: pick one or more scanned batch PDFs and press Split.
Tab 2: the resulting individual BOLs, laid out in their folder tree
       (Company / Customer / Year / Month), each with a download link.

Runs the same pipeline as the CLI. Local, single-user, no external resources.
Start with:  docker compose up ui   → open http://localhost:8000
"""

import os
import tempfile
import uuid

from flask import Flask, abort, render_template_string, request, send_file

from .config import load_candidates
from .pipeline import process_batch
from .store_lookup import StoreMatcher

app = Flask(__name__)

OUT_DIR = os.environ.get("BOL_OUTPUT", "/data/output")
CANDIDATES = os.environ.get("BOL_CANDIDATES", "candidates.json")
STORE_INDEX = os.environ.get("BOL_STORE_INDEX", "store_index.json")

# Most recent run, for the Results tab.
_view = {"folders": {}, "total": 0, "review_total": 0, "inputs": []}

PAGE = """
<!doctype html><html><head><meta charset="utf-8"><title>BOL Splitter</title>
<style>
  body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f5f6f8;color:#1c2430}
  header{background:#1d3557;color:#fff;padding:16px 24px;font-size:20px;font-weight:600}
  .tabs{display:flex;gap:4px;background:#fff;border-bottom:1px solid #e2e6ea;padding:0 24px}
  .tab{padding:14px 18px;cursor:pointer;border-bottom:3px solid transparent;font-weight:500;color:#5b6570}
  .tab.active{color:#1d3557;border-bottom-color:#1d3557}
  .panel{display:none;padding:28px 24px;max-width:1040px}
  .panel.active{display:block}
  .drop{border:2px dashed #b9c2cc;border-radius:10px;padding:40px;text-align:center;background:#fff}
  input[type=file]{margin:14px 0}
  button{background:#1d3557;color:#fff;border:0;border-radius:8px;padding:12px 22px;font-size:15px;cursor:pointer}
  button:hover{background:#264d80}
  .summary{color:#5b6570;margin:0 0 18px}
  .folder{background:#fff;border:1px solid #e2e6ea;border-radius:10px;margin-bottom:16px;overflow:hidden}
  .folder-name{padding:12px 16px;background:#eef2f6;font-weight:600;font-size:14px}
  .folder-name .rev-hdr{color:#a5590a}
  table{width:100%;border-collapse:collapse}
  td,th{padding:9px 16px;text-align:left;border-top:1px solid #eef1f4;font-size:14px}
  th{color:#5b6570;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
  .badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:12px;font-weight:600}
  .ok{background:#e3f4e8;color:#1d7a3a}.rev{background:#fdeede;color:#a5590a}
  a.dl{color:#1d3557;font-weight:600;text-decoration:none}a.dl:hover{text-decoration:underline}
  .empty{color:#5b6570}
</style></head><body>
<header>📦 BOL Splitter</header>
<div class="tabs">
  <div class="tab {{ 'active' if tab=='upload' else '' }}" onclick="show('upload')">Upload</div>
  <div class="tab {{ 'active' if tab=='results' else '' }}" onclick="show('results')">
    Results {% if view.total %}({{ view.total }}){% endif %}
  </div>
</div>

<div id="upload" class="panel {{ 'active' if tab=='upload' else '' }}">
  <form method="post" action="/split" enctype="multipart/form-data">
    <div class="drop">
      <div style="font-size:16px;font-weight:600">Add one or more scanned BOL batches (PDF)</div>
      <input type="file" name="files" accept="application/pdf" multiple required>
      <div><button type="submit">Split</button></div>
    </div>
  </form>
</div>

<div id="results" class="panel {{ 'active' if tab=='results' else '' }}">
  {% if not view.total %}<p class="empty">No results yet — upload files on the Upload tab.</p>{% endif %}
  {% if view.total %}
    <p class="summary">{{ view.total }} file(s) from {{ view.inputs|length }} batch(es)
       — {{ view.review_total }} need review</p>
  {% endif %}
  {% for folder, files in view.folders.items() %}
    <div class="folder">
      <div class="folder-name">
        {% if folder.startswith('Needs Review') %}<span class="rev-hdr">⚠️ {{ folder }}</span>
        {% else %}📁 {{ folder }}{% endif %}
      </div>
      <table>
        <tr><th>File</th><th>Pages</th><th>Date</th><th>Status</th><th></th></tr>
        {% for d in files %}
        <tr>
          <td>📄 {{ d.name }}</td><td>{{ d.pages }}</td><td>{{ d.date or '—' }}</td>
          <td>{% if d.needs_review %}<span class="badge rev">Needs review</span>{% else %}<span class="badge ok">Filed</span>{% endif %}</td>
          <td><a class="dl" href="/file?p={{ d.rel|urlencode }}">download</a></td>
        </tr>
        {% endfor %}
      </table>
    </div>
  {% endfor %}
</div>

<script>
function show(t){for(const p of document.querySelectorAll('.panel'))p.classList.toggle('active',p.id===t);
const tabs=document.querySelectorAll('.tab');tabs[0].classList.toggle('active',t==='upload');tabs[1].classList.toggle('active',t==='results');}
</script>
</body></html>
"""


def _render(tab):
    return render_template_string(PAGE, tab=tab, view=_view)


@app.route("/")
def index():
    return _render("upload")


@app.route("/split", methods=["POST"])
def split():
    os.makedirs(OUT_DIR, exist_ok=True)
    candidates = load_candidates(CANDIDATES)
    matcher = StoreMatcher(STORE_INDEX)

    folders: dict[str, list] = {}
    inputs: list[str] = []
    total = review_total = 0

    for f in request.files.getlist("files"):
        if not f.filename:
            continue
        inputs.append(f.filename)
        tmp = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.pdf")
        f.save(tmp)
        try:
            result = process_batch(tmp, OUT_DIR, candidates, matcher)
        finally:
            os.remove(tmp)

        for d in result.documents:
            rel = os.path.relpath(d.output_path, OUT_DIR)
            folder = os.path.dirname(rel).replace(os.sep, " / ") or "."
            folders.setdefault(folder, []).append({
                "name": os.path.basename(rel),
                "pages": f"{d.source_pages[0]}-{d.source_pages[-1]}",
                "date": d.date,
                "needs_review": d.needs_review,
                "rel": rel,
            })
            total += 1
            review_total += 1 if d.needs_review else 0

    # Clean folders first (alphabetical), Needs Review last.
    ordered = dict(sorted(folders.items(), key=lambda kv: (kv[0].startswith("Needs Review"), kv[0])))

    global _view
    _view = {"folders": ordered, "total": total, "review_total": review_total, "inputs": inputs}
    return _render("results")


@app.route("/file")
def file():
    rel = request.args.get("p", "")
    target = os.path.realpath(os.path.join(OUT_DIR, rel))
    if os.path.commonpath([target, os.path.realpath(OUT_DIR)]) != os.path.realpath(OUT_DIR):
        abort(403)  # no escaping the output dir
    if not os.path.isfile(target):
        abort(404)
    return send_file(target, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
