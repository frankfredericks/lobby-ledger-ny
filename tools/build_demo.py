"""Bundle the site and fixture data into one self-contained HTML file.

    python tests/make_fixtures.py
    python -m pipeline.run --fixtures tests/fixtures --out build/demo-data
    python tools/build_demo.py build/demo-data build/demo.html
"""
import json
import pathlib
import re
import sys

data_dir, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
site = pathlib.Path(__file__).resolve().parent.parent / "site"
html = (site / "index.html").read_text()
data = {j: json.loads((data_dir / f"{j}.json").read_text()) for j in ("city", "state")}
blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")

html = html.replace('<link rel="stylesheet" href="styles.css">', f"<style>{(site / 'styles.css').read_text()}</style>")
inline = (f"<script>window.__DEMO__=true;window.__DATA__={blob};</script>\n"
          f"<script>{(site / 'config.js').read_text()}</script>\n<script>{(site / 'charts.js').read_text()}</script>\n"
          f"<script>{(site / 'app.js').read_text()}</script>")
html = re.sub(r'<script src="config.js"></script>\s*<script src="charts.js"></script>\s*<script src="app.js"></script>', lambda m: inline, html)
# The demo is one file, so the methodology page is embedded in the footer and
# links to it open that section instead of navigating away.
meth = (site / "methodology.html").read_text()
body = re.search(r"<main>(.*)</main>", meth, re.S).group(1)
body = re.sub(r"<h1>(.*?)</h1>", r"<h2>\1</h2>", body)
html = html.replace('href="methodology.html', 'data-m="1" href="methodology.html')
html = html.replace("</footer>", f'<details id="methodology"><summary>How this works and its limits</summary>{body}</details></footer>')
html = html.replace("</body>", """<script>
document.addEventListener("click", (ev) => {
  const a = ev.target.closest("a[data-m]");
  if (!a) return;
  ev.preventDefault();
  const d = document.getElementById("methodology");
  d.open = true;
  const id = (a.getAttribute("href").split("#")[1]) || "methodology";
  (document.getElementById(id) || d).scrollIntoView({ block: "start" });
});
</script>
</body>""")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html)
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
