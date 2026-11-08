"""Verificações estáticas do site em docs/site (sem navegador): links locais, ids usados pelo JS,
evidências do catálogo e ausência de dependências externas."""
import json
import os
import re
import struct
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from infofrota_ai.api import create_app
    TEM_FASTAPI = True
except ImportError:
    TEM_FASTAPI = False

RAIZ = Path(__file__).resolve().parent.parent
SITE = RAIZ / "docs" / "site"
HTML = (SITE / "index.html").read_text(encoding="utf-8")
JS = {p.name: p.read_text(encoding="utf-8") for p in (SITE / "assets" / "js").glob("*.js")}


class SiteTest(unittest.TestCase):
    def test_arquivos_locais_existem(self):
        for ref in re.findall(r'(?:src|href)="([^"#:]+)"', HTML):
            self.assertTrue((SITE / ref).exists(), f"referência quebrada: {ref}")
        for ref in re.findall(r'url\("(\.\./[^"]+)"\)', (SITE / "assets/css/tokens.css").read_text()):
            self.assertTrue((SITE / "assets/css" / ref).resolve().exists(), ref)

    def test_sem_recursos_externos(self):
        self.assertNotRegex(HTML, r'(?:src|href)="https?://(?!github\.com/David-Evora/InfoFrota)')
        for nome, txt in JS.items():
            self.assertNotRegex(txt, r"https?://(?!github\.com/David-Evora/InfoFrota)[^\s\"']*\.(?:js|css|woff2?)", nome)

    def test_ids_usados_pelo_js_existem(self):
        ids = set(re.findall(r'id="([^"]+)"', HTML))
        for nome, txt in JS.items():
            for i in re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)', txt) + re.findall(r'getElementById\("([^"]+)"\)', txt):
                if nome == "ai.js" and i.startswith("scen"):
                    continue          # abas criadas dinamicamente
                self.assertIn(i, ids, f"{nome} usa #{i}, que não existe no HTML")

    def test_icones_do_sprite(self):
        sprite = set(re.findall(r'<symbol id="(i-[a-z0-9-]+)"', HTML))
        usados = set(re.findall(r'"(i-[a-z0-9-]+)"', "".join(JS.values()))) | set(re.findall(r'href="#(i-[a-z0-9-]+)"', HTML))
        self.assertFalse(usados - sprite, f"ícones ausentes do sprite: {usados - sprite}")

    def test_evidencias_do_catalogo_existem(self):
        txt = JS["features-data.js"] + JS["architecture.js"]
        caminhos = set()
        for bloco in re.findall(r"(?:evidence|f): \[([^\]]*)\]", txt):
            caminhos |= set(re.findall(r'"([^"]+)"', bloco))
        self.assertGreater(len(caminhos), 10)
        for c in caminhos:
            self.assertTrue((RAIZ / c).exists(), f"evidência inexistente no repositório: {c}")

    def test_catalogo_estrutura(self):
        txt = JS["features-data.js"]
        status = set(re.findall(r'status: "(\w+)"', txt))
        self.assertLessEqual(status, {"impl", "exp", "val", "plan"})
        self.assertIn("plan", status)                       # o que não existe aparece como planejado
        cats = set(re.findall(r'\{ id: "(\w+)", nome:', txt))
        for c in re.findall(r'cat: "(\w+)"', txt):
            self.assertIn(c, cats)

    def test_snapshot_valido_e_sintetico(self):
        txt = (SITE / "assets/data/snapshot.js").read_text(encoding="utf-8")
        dados = json.loads(txt[txt.index("=") + 1:].rstrip().rstrip(";"))
        self.assertEqual(len(dados["mapa_calor"]["valores"]), 7)
        self.assertTrue(all(len(r) == 24 for r in dados["mapa_calor"]["valores"]))
        self.assertGreaterEqual(len(dados["cenarios"]), 5)
        self.assertTrue(any(c.get("bloqueado") for c in dados["cenarios"]))

    def test_sem_segredos_nem_emoji(self):
        todo = HTML + "".join(JS.values())
        self.assertNotRegex(todo, r"(?i)(gsk_[A-Za-z0-9]{10,}|sk-ant-|sk-[A-Za-z0-9]{20,}|api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9]{12,})")
        self.assertNotRegex(todo, "[\U0001F300-\U0001FAFF☀-➿]")

    def test_seo_basico(self):
        for trecho in ('<html lang="pt-BR"', 'name="viewport"', 'name="description"', 'property="og:title"', 'property="og:image"', "<h1"):
            self.assertIn(trecho, HTML)
        self.assertEqual(HTML.count("<h1"), 1)
        with open(SITE / "assets/img/og.png", "rb") as f:
            cab = f.read(24)
        self.assertEqual(struct.unpack(">II", cab[16:24]), (1200, 630))

    def test_imagens_com_alt(self):
        for tag in re.findall(r"<img\b[^>]*>", HTML):
            self.assertIn("alt=", tag)

    @unittest.skipUnless(TEM_FASTAPI, "fastapi não instalado")
    def test_servido_pela_api(self):
        os.environ.pop("INFOFROTA_WEB", None)
        r = TestClient(create_app()).get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("InfoFrota", r.text)


if __name__ == "__main__":
    unittest.main()
