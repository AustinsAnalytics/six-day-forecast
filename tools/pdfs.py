"""Print the featured Monday packets to PDF (English and Spanish) with headless Chrome -> site/packets/*.pdf

    python tools/pdfs.py

Serves site/ on a local port for the duration, so the packet page loads its data the same way it does online.
"""
import functools
import http.server
import json
import subprocess
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 8691


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(Quiet, directory=str(SITE))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    out = SITE / "packets"
    out.mkdir(exist_ok=True)
    httpd = serve()
    made = []
    with tempfile.TemporaryDirectory() as prof:
        for team in ("JAX", "JUP"):
            idx = json.loads((SITE / "data" / "packets" / team / "index.json").read_text())
            start = idx["series"][-1]["start"]
            for lang in ("en", "es"):
                pdf = out / f"{team}-{start}-{lang}.pdf"
                url = f"http://127.0.0.1:{PORT}/packet.html?team={team}&start={start}&lang={lang}"
                subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                                "--virtual-time-budget=20000", f"--user-data-dir={prof}", f"--print-to-pdf={pdf}", url],
                               check=True, capture_output=True)
                made.append(pdf.name)
    httpd.shutdown()
    (out / "index.json").write_text(json.dumps(made, indent=1))
    print("\n".join(made))


if __name__ == "__main__":
    main()
