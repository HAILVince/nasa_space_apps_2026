"""Safe Markdown subset -> HTML for SI answers (everything is escaped first)."""

import html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _inline(s: str) -> str:
    s = html.escape(s)
    s = _CODE.sub(r"<code>\1</code>", s)
    s = _BOLD.sub(r"<strong>\1</strong>", s)
    s = _LINK.sub(r'<a href="\2" rel="nofollow noopener" target="_blank">\1</a>', s)
    return s


def render_answer(text: str) -> str:
    """Tiny, safe Markdown subset -> HTML: everything is escaped first, then
    paragraphs, bullet lists, **bold**, `code` and http(s) links."""
    out, items = [], []

    def flush_list():
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) >= 2 and all(ln.strip().startswith("|") for ln in lines):
            flush_list()
            rows = [[_inline(c.strip()) for c in ln.strip().strip("|").split("|")] for ln in lines
                    if not re.fullmatch(r"[\s|:\-]+", ln)]
            head, body = rows[0], rows[1:]
            out.append("<div class=\"table\"><table><thead><tr>" + "".join(f"<th>{c}</th>" for c in head)
                       + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
                                                         for r in body) + "</tbody></table></div>")
            continue
        para = []
        for ln in lines:
            if _BULLET.match(ln):
                if para:
                    out.append("<p>" + "<br>".join(para) + "</p>")
                    para = []
                items.append(_inline(_BULLET.sub("", ln, count=1)))
            else:
                flush_list()
                heading = ln.lstrip("#").strip() if ln.lstrip().startswith("#") else None
                if heading is not None:
                    out.append(f"<h3>{_inline(heading)}</h3>")
                else:
                    para.append(_inline(ln))
        if para:
            out.append("<p>" + "<br>".join(para) + "</p>")
        flush_list()
    return "".join(out)
