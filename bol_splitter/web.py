"""A small local web UI for the BOL splitter.

Tab 1 (Upload): stage one or more PDFs (each removable), then press Run.
Tab 2 (Output): the latest run's results in their folder tree
       (Company / Customer / Year / Month), a Needs Review section, and the
       manifest — mirroring what lands in the local output folder. The output
       is wiped and replaced on every run.

Local, single-user, no external resources.
Start with:  docker compose up ui   → open http://localhost:8000
"""

import os
import shutil
import tempfile
import uuid

from flask import Flask, abort, render_template_string, request, send_file

from .config import load_candidates
from .pipeline import process_batch
from .store_lookup import StoreMatcher

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB
app.config["MAX_FORM_MEMORY_SIZE"] = None
app.config["MAX_FORM_PARTS"] = 10000

OUT_DIR = os.environ.get("BOL_OUTPUT", "/data/output")
CANDIDATES = os.environ.get("BOL_CANDIDATES", "candidates.json")
STORE_INDEX = os.environ.get("BOL_STORE_INDEX", "store_index.json")

_view = {"folders": {}, "total": 0, "filed": 0, "review_total": 0,
         "inputs": [], "manifest": None, "errors": [], "error": None}

PAGE = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>BOL Splitter</title>
<style>
  :root{--navy:#1d3557;--ink:#1c2430;--muted:#6b7683;--line:#e6eaef;--bg:#eef1f5}
  *{box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
  header{background:var(--navy);color:#fff;padding:18px 28px;font-size:20px;font-weight:700}
  .tabs{display:flex;background:#fff;border-bottom:1px solid var(--line);padding:0 28px}
  .tab{padding:15px 6px;margin:0 12px;cursor:pointer;border-bottom:3px solid transparent;font-weight:600;color:var(--muted)}
  .tab.active{color:var(--navy);border-bottom-color:var(--navy)}
  .panel{display:none;padding:32px 0}.panel.active{display:block}
  .wrap{max-width:960px;margin:0 auto;padding:0 20px}

  .drop{background:#fff;border:2px dashed #c3ccd6;border-radius:14px;padding:36px 28px;text-align:center}
  .drop h2{margin:0 0 6px;font-size:18px}.drop p{margin:0 0 18px;color:var(--muted)}
  .choose{display:inline-block;background:#eef2f7;color:var(--navy);border:1px solid #d5dee8;
          padding:10px 18px;border-radius:9px;font-weight:600;cursor:pointer}.choose:hover{background:#e3ebf4}
  .staged{margin:20px auto 0;max-width:560px;text-align:left}
  .staged .item{display:flex;align-items:center;justify-content:space-between;gap:12px;
                background:#f6f8fa;border:1px solid var(--line);border-radius:9px;padding:10px 14px;margin-bottom:8px}
  .staged .item span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .rm{background:#fff;border:1px solid #e0c4c4;color:#b23b3b;border-radius:7px;padding:5px 11px;cursor:pointer;font-weight:700}
  .rm:hover{background:#fdeeee}
  .go{display:block;margin:22px auto 0;background:var(--navy);color:#fff;border:0;border-radius:10px;
      padding:13px 32px;font-size:15px;font-weight:600;cursor:pointer}.go:hover{background:#264d80}.go:disabled{opacity:.45;cursor:default}

  .stats{display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap}
  .stat{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 20px;min-width:120px}
  .stat b{display:block;font-size:26px;line-height:1.1}.stat span{color:var(--muted);font-size:13px}.stat.rev b{color:#a5590a}
  .manifest{margin:0 0 18px;font-size:14px}
  .folder{background:#fff;border:1px solid var(--line);border-radius:12px;margin-bottom:16px;overflow:hidden}
  .folder-name{padding:13px 18px;background:#f3f6f9;font-weight:600;font-size:14px}
  .folder.review .folder-name{background:#fdf1e5;color:#a5590a}
  .row{display:grid;grid-template-columns:1fr 90px 110px 120px 90px;gap:10px;align-items:center;padding:11px 18px;border-top:1px solid #f0f3f6;font-size:14px}
  .row.head{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em;font-weight:600}
  .fname{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .badge{justify-self:start;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600}
  .ok{background:#e3f4e8;color:#1d7a3a}.rev{background:#fdeede;color:#a5590a}
  a.dl{color:var(--navy);font-weight:600;text-decoration:none}a.dl:hover{text-decoration:underline}
  .empty{color:var(--muted)}
  .err{background:#fdecec;border:1px solid #f5c2c2;color:#a12020;padding:14px 18px;border-radius:10px}
  .overlay{display:none;position:fixed;inset:0;background:rgba(20,28,40,.55);z-index:9;align-items:center;justify-content:center;flex-direction:column;color:#fff}
  .overlay.on{display:flex}
  .spinner{width:52px;height:52px;border:5px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin 1s linear infinite;margin-bottom:18px}
  @keyframes spin{to{transform:rotate(360deg)}}
</style></head><body>
<header>📦 BOL Splitter</header>
<div class="tabs">
  <div class="tab {{ 'active' if tab=='upload' else '' }}" onclick="show('upload')">Upload</div>
  <div class="tab {{ 'active' if tab=='output' else '' }}" onclick="show('output')">Output{% if view.total %} ({{ view.total }}){% endif %}</div>
</div>

<div class="wrap">
  <div id="upload" class="panel {{ 'active' if tab=='upload' else '' }}">
    <form id="frm" method="post" action="/split" enctype="multipart/form-data">
      <div class="drop">
        <h2>Split scanned BOL batches</h2>
        <p>Add one or more PDF files, remove any you don't want, then press Run.</p>
        <label class="choose">Add files
          <input id="inp" type="file" name="files" accept="application/pdf" multiple hidden>
        </label>
        <div id="staged" class="staged"></div>
        <button id="go" class="go" type="submit" disabled>Run</button>
      </div>
    </form>
  </div>

  <div id="output" class="panel {{ 'active' if tab=='output' else '' }}">
    {% if view.error %}<div class="err">{{ view.error }}</div>
    {% elif not view.total and not view.errors %}<p class="empty">No output yet — add files and press Run.</p>
    {% else %}
      {% if view.errors %}<div class="err"><b>Couldn't read {{ view.errors|length }} file(s):</b>
        {% for e in view.errors %}<div>• {{ e.name }} — {{ e.msg }}</div>{% endfor %}</div>{% endif %}
      {% if view.total %}
      <div class="stats">
        <div class="stat"><b>{{ view.total }}</b><span>files split</span></div>
        <div class="stat"><b>{{ view.filed }}</b><span>filed</span></div>
        <div class="stat rev"><b>{{ view.review_total }}</b><span>need review</span></div>
      </div>
      {% if view.manifest %}<p class="manifest">📄 <a class="dl" href="/file?p={{ view.manifest|urlencode }}">manifest.json</a> — full log of this run</p>{% endif %}
      {% for folder, files in view.folders.items() %}
        <div class="folder {{ 'review' if folder.startswith('Needs Review') else '' }}">
          <div class="folder-name">{{ '⚠️' if folder.startswith('Needs Review') else '📁' }} {{ folder }}</div>
          <div class="row head"><div>File</div><div>Pages</div><div>Date</div><div>Status</div><div></div></div>
          {% for d in files %}
          <div class="row">
            <div class="fname" title="{{ d.name }}">{{ d.name }}</div><div>{{ d.pages }}</div><div>{{ d.date or '—' }}</div>
            <div>{% if d.needs_review %}<span class="badge rev">Needs review</span>{% else %}<span class="badge ok">Filed</span>{% endif %}</div>
            <div><a class="dl" href="/file?p={{ d.rel|urlencode }}">download</a></div>
          </div>
          {% endfor %}
        </div>
      {% endfor %}
      {% endif %}
    {% endif %}
  </div>
</div>

<div id="overlay" class="overlay"><div class="spinner"></div><div>Splitting…</div>
  <div style="opacity:.8;font-size:14px;margin-top:6px">Large batches can take a couple of minutes.</div></div>

<script>
function show(t){for(const p of document.querySelectorAll('.panel'))p.classList.toggle('active',p.id===t);
  const tabs=document.querySelectorAll('.tab');tabs[0].classList.toggle('active',t==='upload');tabs[1].classList.toggle('active',t==='output');}
const inp=document.getElementById('inp');
if(inp){
  let staged=[];
  const listEl=document.getElementById('staged'), go=document.getElementById('go');
  function sync(){const dt=new DataTransfer();staged.forEach(f=>dt.items.add(f));inp.files=dt.files;go.disabled=staged.length===0;render();}
  function render(){listEl.innerHTML='';staged.forEach((f,i)=>{
    const row=document.createElement('div');row.className='item';
    const name=document.createElement('span');name.textContent='📄 '+f.name;
    const btn=document.createElement('button');btn.type='button';btn.className='rm';btn.textContent='✕';
    btn.onclick=()=>{staged.splice(i,1);sync();};
    row.appendChild(name);row.appendChild(btn);listEl.appendChild(row);});}
  inp.addEventListener('change',()=>{
    [...inp.files].forEach(f=>{if(!staged.some(s=>s.name===f.name&&s.size===f.size))staged.push(f);});
    sync();
  });
  document.getElementById('frm').addEventListener('submit',(e)=>{
    if(staged.length===0){e.preventDefault();return;}
    go.disabled=true;document.getElementById('overlay').classList.add('on');
  });
}
</script>
</body></html>
"""


def _render(tab):
    return render_template_string(PAGE, tab=tab, view=_view)


def _clear_output():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in os.listdir(OUT_DIR):
        path = os.path.join(OUT_DIR, name)
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)


@app.route("/")
def index():
    return _render("upload")


@app.route("/split", methods=["POST"])
def split():
    global _view
    try:
        _clear_output()  # each run replaces the previous output
        candidates = load_candidates(CANDIDATES)
        matcher = StoreMatcher(STORE_INDEX)

        folders: dict[str, list] = {}
        inputs: list[str] = []
        errors: list[dict] = []
        total = filed = review_total = 0

        for f in request.files.getlist("files"):
            if not f.filename:
                continue
            inputs.append(f.filename)
            tmp = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.pdf")
            f.save(tmp)
            try:
                result = process_batch(tmp, OUT_DIR, candidates, matcher)
            except Exception as e:  # one bad file shouldn't fail the whole run
                errors.append({"name": f.filename, "msg": str(e).splitlines()[0][:160]})
                continue
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)

            for d in result.documents:
                rel = os.path.relpath(d.output_path, OUT_DIR)
                folder = os.path.dirname(rel).replace(os.sep, " / ") or "."
                folders.setdefault(folder, []).append({
                    "name": os.path.basename(rel),
                    "pages": f"{d.source_pages[0]}-{d.source_pages[-1]}",
                    "date": d.date, "needs_review": d.needs_review, "rel": rel,
                })
                total += 1
                filed += 0 if d.needs_review else 1
                review_total += 1 if d.needs_review else 0

        ordered = dict(sorted(folders.items(), key=lambda kv: (kv[0].startswith("Needs Review"), kv[0])))
        manifest = "manifest.json" if os.path.isfile(os.path.join(OUT_DIR, "manifest.json")) else None
        _view = {"folders": ordered, "total": total, "filed": filed, "review_total": review_total,
                 "inputs": inputs, "manifest": manifest, "errors": errors, "error": None}
    except Exception as e:
        _view = {"folders": {}, "total": 0, "filed": 0, "review_total": 0,
                 "inputs": [], "manifest": None, "errors": [], "error": f"Something went wrong: {e}"}
    return _render("output")


@app.route("/file")
def file():
    rel = request.args.get("p", "")
    target = os.path.realpath(os.path.join(OUT_DIR, rel))
    if os.path.commonpath([target, os.path.realpath(OUT_DIR)]) != os.path.realpath(OUT_DIR):
        abort(403)
    if not os.path.isfile(target):
        abort(404)
    return send_file(target, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)
