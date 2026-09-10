"""Minimal structural HTML parsing; scripts are data and never executed."""

from html.parser import HTMLParser


class PublicPage(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self.forms: list[tuple[dict[str, str], dict[str, str]]] = []
        self.meta: dict[str, str] = {}
        self.scripts: list[str] = []
        self.heading = ""
        self._heading = False
        self._script = False
        self._form: dict[str, str] | None = None
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        values = {key: value or "" for key, value in attrs}
        if tag == "a":
            self.links.append(values)
        elif tag == "form":
            self._form = {}
            self.forms.append((values, self._form))
        elif tag == "input" and self._form is not None and values.get("name"):
            self._form[values["name"]] = values.get("value", "")
        elif tag == "meta":
            self.meta[values.get("property", values.get("name", ""))] = values.get("content", "")
        elif tag == "h1":
            self._heading = True
        elif tag == "script":
            self._script = True

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None
        elif tag == "h1":
            self._heading = False
        elif tag == "script":
            self._script = False

    def handle_data(self, data):
        if self._heading:
            self.heading += data
        if self._script:
            self.scripts.append(data)
