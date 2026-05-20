"""
inspect_chroma.py — 将 Chroma 向量库内容导出为可视化 HTML
用法：
    conda run -n MediAgent python scripts/inspect_chroma.py
    # 然后用浏览器打开 scripts/chroma_inspect.html
"""
import sys, pathlib, html, math

import chromadb

CHROMA_DIR = pathlib.Path(__file__).resolve().parents[1] / "src" / "server_new" / "data" / "chroma"

client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collections = client.list_collections()

# ---------- 收集数据 ----------
kb_data = []
for col in collections:
    c = client.get_collection(col.name)
    total = c.count()
    if total == 0:
        kb_data.append({"name": col.name, "total": 0, "docs": {}})
        continue

    # 分批拉取（避免内存爆炸）
    BATCH = 500
    offset = 0
    doc_chunks: dict[int, list[dict]] = collections.OrderedDict() if False else {}
    while offset < total:
        r = c.get(limit=BATCH, offset=offset, include=["documents", "metadatas", "embeddings"])
        for doc_text, meta, emb in zip(r["documents"], r["metadatas"], r["embeddings"]):
            doc_id = meta.get("doc_id", "unknown")
            if doc_id not in doc_chunks:
                doc_chunks[doc_id] = []
            emb_list = list(emb) if emb is not None else []
            norm = math.sqrt(sum(v * v for v in emb_list)) if emb_list else 0
            doc_chunks[doc_id].append({
                "chunk_index": meta.get("chunk_index", "?"),
                "text": doc_text,
                "emb_dim": len(emb_list),
                "emb_norm": norm,
                "emb_preview": [round(float(v), 6) for v in emb_list[:10]],
            })
        offset += BATCH

    # 按 chunk_index 排序
    for doc_id in doc_chunks:
        doc_chunks[doc_id].sort(key=lambda x: x["chunk_index"])

    kb_data.append({"name": col.name, "total": total, "docs": doc_chunks})

# ---------- 生成 HTML ----------
def esc(s):
    return html.escape(str(s))

kb_count = len(kb_data)
total_chunks = sum(kb["total"] for kb in kb_data)
total_docs = sum(len(kb["docs"]) for kb in kb_data)

kb_sections_html = []
for kb in kb_data:
    kb_name = kb["name"]
    if kb["total"] == 0:
        kb_sections_html.append(f"""
<details class="kb-section">
  <summary class="kb-summary">
    <span class="kb-title">{esc(kb_name)}</span>
    <span class="kb-meta">空 collection</span>
  </summary>
</details>""")
        continue

    doc_sections_html = []
    for doc_id, chunks in kb["docs"].items():
        chunk_rows = []
        for chunk in chunks:
            text_preview = esc(chunk["text"][:200]) + ("…" if len(chunk["text"]) > 200 else "")
            full_text = esc(chunk["text"])
            dim = chunk["emb_dim"]
            norm = f"{chunk['emb_norm']:.4f}"
            preview_vals = ", ".join(str(v) for v in chunk["emb_preview"])
            emb_html = f'<span class="emb-meta">dim={dim} &nbsp;|v|={norm}</span><details><summary>前10个分量</summary><pre class="full-text">[{esc(preview_vals)}, …]</pre></details>'
            chunk_rows.append(f"""
          <tr>
            <td class="idx-cell">{esc(chunk["chunk_index"])}</td>
            <td class="text-cell">
              <span class="preview">{text_preview}</span>
              <details><summary>展开全文</summary><pre class="full-text">{full_text}</pre></details>
            </td>
            <td class="emb-cell">{emb_html}</td>
          </tr>""")

        doc_sections_html.append(f"""
    <details class="doc-section">
      <summary class="doc-summary">
        <span class="doc-id">doc_id: <b>{esc(doc_id)}</b></span>
        <span class="doc-meta">{len(chunks)} chunks</span>
      </summary>
      <div class="doc-body">
        <table>
          <thead><tr><th style="width:50px">#</th><th>Chunk 内容</th><th style="width:230px">向量</th></tr></thead>
          <tbody>{"".join(chunk_rows)}
          </tbody>
        </table>
      </div>
    </details>""")

    kb_sections_html.append(f"""
<details class="kb-section" open>
  <summary class="kb-summary">
    <span class="kb-title">{esc(kb_name)}</span>
    <span class="kb-meta">{len(kb["docs"])} 个文档 &nbsp;·&nbsp; {kb["total"]} 个 chunks</span>
  </summary>
  <div class="kb-body">{"".join(doc_sections_html)}
  </div>
</details>""")

all_kb_html = "\n".join(kb_sections_html)

html_content = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>Chroma 向量库检视</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #f5f7fa; margin: 0; padding: 20px; color: #333; }}
  h1 {{ color: #2c3e50; margin-bottom: 16px; }}
  .summary-bar {{ background: #fff; border-radius: 8px; padding: 16px 24px; margin-bottom: 20px;
                  box-shadow: 0 1px 4px rgba(0,0,0,.1); display:flex; gap:40px; }}
  .stat {{ text-align:center; }}
  .stat .num {{ font-size: 2em; font-weight: bold; color: #3498db; }}
  .stat .label {{ color: #888; font-size:.9em; }}

  input#search {{ width:100%; padding:10px; font-size:1em; border:1px solid #ddd;
                  border-radius:6px; margin-bottom:16px; box-sizing:border-box; }}

  /* KB 折叠块 */
  .kb-section {{ background:#fff; border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.1);
                 margin-bottom:14px; overflow:hidden; }}
  .kb-section > summary.kb-summary {{
    list-style: none; display:flex; align-items:center; justify-content:space-between;
    padding: 14px 20px; cursor:pointer; background:#2c3e50; color:#fff;
    user-select:none;
  }}
  .kb-section > summary.kb-summary::-webkit-details-marker {{ display:none; }}
  .kb-section > summary.kb-summary::before {{
    content: "▶"; margin-right: 10px; font-size:.8em; transition: transform .2s;
  }}
  .kb-section[open] > summary.kb-summary::before {{ transform: rotate(90deg); }}
  .kb-title {{ font-size: 1em; font-weight: bold; letter-spacing:.03em; }}
  .kb-meta {{ font-size: .85em; opacity: .8; }}

  /* KB 内容区 */
  .kb-body {{ padding: 12px 16px; display:flex; flex-direction:column; gap:8px; background:#f0f4f8; }}

  /* Doc 折叠块 */
  .doc-section {{ background:#fff; border-radius:7px; border:1px solid #dce3ea; overflow:hidden; }}
  .doc-section > summary.doc-summary {{
    list-style:none; display:flex; align-items:center; justify-content:space-between;
    padding: 10px 16px; cursor:pointer; background:#ebf5fb;
    user-select:none;
  }}
  .doc-section > summary.doc-summary::-webkit-details-marker {{ display:none; }}
  .doc-section > summary.doc-summary::before {{
    content: "▶"; margin-right: 8px; font-size:.75em; color:#1a5276; transition: transform .2s;
  }}
  .doc-section[open] > summary.doc-summary::before {{ transform: rotate(90deg); }}
  .doc-id {{ color:#1a5276; font-size:.92em; }}
  .doc-meta {{ color:#888; font-size:.82em; }}

  /* 文档内 chunk 表格 */
  .doc-body {{ padding: 0; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ background:#34495e; color:#fff; padding:8px 12px; text-align:left; font-size:.85em; }}
  td {{ padding:7px 12px; vertical-align:top; border-bottom:1px solid #eef; font-size:.87em; }}
  tr:last-child td {{ border-bottom:none; }}
  .idx-cell {{ width:50px; text-align:center; color:#888; }}
  .text-cell {{ }}
  .emb-cell {{ font-size:.81em; }}
  .emb-meta {{ color:#8e44ad; font-weight:bold; display:block; margin-bottom:2px; }}
  .preview {{ color:#2c3e50; }}
  details summary {{ cursor:pointer; color:#3498db; margin-top:4px; font-size:.84em; }}
  pre.full-text {{ white-space:pre-wrap; word-break:break-all; background:#f8f9fa;
                   padding:10px; border-radius:4px; margin-top:6px; font-size:.81em;
                   max-height:300px; overflow-y:auto; }}
</style>
</head>
<body>
<h1>Chroma 向量库检视</h1>
<div class="summary-bar">
  <div class="stat"><div class="num">{kb_count}</div><div class="label">Collections</div></div>
  <div class="stat"><div class="num">{total_docs}</div><div class="label">文档数</div></div>
  <div class="stat"><div class="num">{total_chunks}</div><div class="label">总 Chunks</div></div>
</div>
<input id="search" placeholder="搜索 chunk 内容…" oninput="filterSections(this.value)">
<div id="kb-container">
{all_kb_html}
</div>
<script>
function filterSections(q) {{
  q = q.toLowerCase().trim();
  document.querySelectorAll('.doc-section').forEach(doc => {{
    if (!q) {{ doc.style.display = ''; return; }}
    const txt = doc.innerText.toLowerCase();
    doc.style.display = txt.includes(q) ? '' : 'none';
    if (txt.includes(q)) doc.open = true;
  }});
  if (q) {{
    document.querySelectorAll('.kb-section').forEach(kb => {{
      const hasVisible = [...kb.querySelectorAll('.doc-section')]
        .some(d => d.style.display !== 'none');
      kb.style.display = hasVisible ? '' : 'none';
      if (hasVisible) kb.open = true;
    }});
  }} else {{
    document.querySelectorAll('.kb-section').forEach(kb => kb.style.display = '');
  }}
}}
</script>
</body>
</html>"""

out = pathlib.Path(__file__).parent / "chroma_inspect.html"
out.write_text(html_content, encoding="utf-8")
print(f"✅ 已生成: {out}")
print(f"   包含 {kb_count} 个 collection，共 {total_chunks} 个 chunks")
print(f"   用浏览器打开该文件即可查看")
