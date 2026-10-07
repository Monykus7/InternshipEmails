"""Preserve requirement clauses while stripping employer HTML."""

from html import unescape

from bs4 import BeautifulSoup


def html_text(html: str) -> str:
    soup = BeautifulSoup(unescape(html), "html.parser")
    for block in soup.select("br, p, li, div, h1, h2, h3, h4"):
        block.append("\n")
    return "\n".join(" ".join(line.split()) for line in soup.get_text(" ").splitlines() if line.strip())
