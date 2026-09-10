from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"


def test_paste_button_has_safari_clipboard_fallback():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "navigator.clipboard?.readText" in html
    assert "navigator.clipboard?.read" in html
    assert "window.isSecureContext" in html
    assert "const input = document.getElementById('inputText');" in html
    assert "input.focus();" in html
