"""Secrets configuration screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static


class SecretsScreen(Screen):
    """Configure additional secrets (env vars injected into containers)."""

    def __init__(self, state: dict) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        with Vertical(classes="form-container"):
            yield Static("Secrets Configuration (Optional)", classes="title")
            yield Static(
                f"Secrets added: {len(self._state.get('secrets', []))}",
                id="count",
            )

            yield Label("Secret name (env var):", classes="section-label")
            yield Input(placeholder="DJANGO_SECRET_KEY", id="sec_name")

            yield Label("Source:", classes="section-label")
            with RadioSet(id="sec_source"):
                yield RadioButton("Generate (random value)", value=True, id="src_gen")
                yield RadioButton("Environment variable", id="src_env")

            yield Label("Length (for generated):", classes="section-label")
            yield Input(placeholder="50", id="sec_length", value="50")

            with Vertical(classes="button-row"):
                yield Button("+ Add Secret", id="add", variant="default")
                yield Button("Next →", id="next", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add":
            self._add_secret()
        elif event.button.id == "next":
            name = self.query_one("#sec_name", Input).value.strip()
            if name:
                self._add_secret()
            self.app.advance_to("review")

    def _add_secret(self) -> None:
        name = self.query_one("#sec_name", Input).value.strip()
        if not name:
            self.notify("Secret name is required", severity="error")
            return

        radio_set = self.query_one("#sec_source", RadioSet)
        pressed = radio_set.pressed_button
        source = "env" if pressed and pressed.id == "src_env" else "generate"

        length = int(self.query_one("#sec_length", Input).value.strip() or "50")

        secret = {
            "name": name,
            "source": source,
            "length": length,
            "generate_once": True,
        }

        self._state.setdefault("secrets", []).append(secret)
        count = len(self._state["secrets"])
        self.query_one("#count", Static).update(f"Secrets added: {count}")

        self.query_one("#sec_name", Input).value = ""
        self.notify(f"Added secret '{name}'")
