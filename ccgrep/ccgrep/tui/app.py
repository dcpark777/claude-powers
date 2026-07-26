"""tui/app.py — minimal v1 TUI: search input, results list, preview pane.

Deliberately thin: the deterministic core is the product; this is the shell.
Keys: type to search (debounced on Enter), up/down select, Enter on a result
shows preview, `o` prints the resume command and exits, `q` quits.
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from .. import search as search_mod
from ..store import Store


class CcgrepApp(App):
    CSS = """
    #results { width: 45%; }
    #preview { width: 55%; border-left: solid $accent; padding: 0 1; }
    """
    BINDINGS = [("q", "quit", "quit"), ("o", "open", "resume cmd")]

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.hits = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(placeholder="search your Claude Code history…", id="query")
        with Horizontal():
            yield ListView(id="results")
            yield Static("", id="preview")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.hits = search_mod.search(self.store, event.value, limit=20)
        lv = self.query_one("#results", ListView)
        lv.clear()
        for h in self.hits:
            mark = {"green": "+", "thrash": "~", "unknown": " "}[h.outcome]
            seen = f" ({h.seen_count}x)" if h.seen_count > 1 else ""
            lv.append(ListItem(Static(
                f"[{mark}] {h.repo} {(h.ts_end or '')[:10]}{seen}\n"
                f"  {h.prompt[:60]}")))
        if self.hits:
            lv.index = 0
            self._preview(0)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.index is not None:
            self._preview(event.list_view.index)

    def _preview(self, i: int) -> None:
        if not (0 <= i < len(self.hits)):
            return
        h = self.hits[i]
        lines = search_mod.show(self.store, h.id, lines=30)
        self.query_one("#preview", Static).update(
            f"{h.id}  outcome={h.outcome}\n\n" + "\n".join(lines))

    def action_open(self) -> None:
        lv = self.query_one("#results", ListView)
        if lv.index is not None and 0 <= lv.index < len(self.hits):
            h = self.hits[lv.index]
            self.exit(message=f"claude --resume {h.session_id}")


def run_tui(store: Store) -> None:
    app = CcgrepApp(store)
    result = app.run()
    if result:
        print(result)
