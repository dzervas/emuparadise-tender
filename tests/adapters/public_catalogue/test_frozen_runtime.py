"""Catalogue bootstrap and parsing cannot depend on Decky's missing wrappers."""

import os
import subprocess
import sys


def test_bootstrap_and_html_parsing_without_optional_stdlib_modules():
    # Fresh process: pytest and its dependencies may already have loaded the missing modules.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            '''
import sys
class MissingDeckyModules:
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ("html.parser", "_markupbase", "xml.etree") or fullname.startswith("xml.etree."):
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
sys.meta_path.insert(0, MissingDeckyModules())
import bootstrap
from adapters.public_catalogue.page import PublicPage
page = PublicPage("""
<!DOCTYPE html><!-- ignored <a href='wrong'> -->
<h1>Pok&eacute;mon &amp; &#x2605;</h1>
<a data-filter="gb" href="/game?x=1&amp;y=2"><span>Game &amp; Name</span></a>
<meta property="og:title" content="Game &quot;Title&quot;">
<form action="/download" method="post"><input name="session" value="a&amp;b"></form>
<style>.hidden { color: red }</style>
<script>window.location.href="https://example.org/file.zip?a=1&b=2";</script>
""")
assert page.heading == "Pokémon & ★"
assert len(page.links) == 1
assert page.links[0]["href"] == "/game?x=1&y=2"
assert page.links[0]["text"] == "Game & Name"
assert page.meta["og:title"] == 'Game "Title"'
assert page.forms[0][1] == {"session": "a&b"}
assert page.scripts == ['window.location.href="https://example.org/file.zip?a=1&b=2";']
assert "window.location" not in page.text and "color: red" not in page.text
''',
        ],
        env={**os.environ, "PYTHONPATH": "py_modules"},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
