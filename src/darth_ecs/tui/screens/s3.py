"""S3 bucket configuration screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static, Switch


class S3Screen(Screen):
    """Optional: configure S3 buckets."""

    def __init__(self, state: dict) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        with Vertical(classes="form-container"):
            yield Static("S3 Buckets (Optional)", classes="title")
            yield Static(
                f"Buckets added: {len(self._state.get('s3_buckets', []))}",
                id="count",
            )

            yield Label("Bucket name (logical):", classes="section-label")
            yield Input(placeholder="media", id="bucket_name")

            yield Label("Enable CloudFront?", classes="section-label")
            yield Switch(id="bucket_cf", value=False)

            yield Label("Enable CORS?", classes="section-label")
            yield Switch(id="bucket_cors", value=False)

            yield Label("Public read?", classes="section-label")
            yield Switch(id="bucket_public", value=False)

            with Vertical(classes="button-row"):
                yield Button("+ Add Bucket", id="add", variant="default")
                yield Button("Next →", id="next", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add":
            self._add_bucket()
        elif event.button.id == "next":
            name = self.query_one("#bucket_name", Input).value.strip()
            if name:
                self._add_bucket()
            self.app.advance_to("alb")

    def _add_bucket(self) -> None:
        name = self.query_one("#bucket_name", Input).value.strip()
        if not name:
            self.notify("Bucket name is required", severity="error")
            return

        bucket = {
            "name": name,
            "cloudfront": self.query_one("#bucket_cf", Switch).value,
            "cors": self.query_one("#bucket_cors", Switch).value,
            "public_read": self.query_one("#bucket_public", Switch).value,
        }

        self._state.setdefault("s3_buckets", []).append(bucket)
        count = len(self._state["s3_buckets"])
        self.query_one("#count", Static).update(f"Buckets added: {count}")

        self.query_one("#bucket_name", Input).value = ""
        self.query_one("#bucket_cf", Switch).value = False
        self.query_one("#bucket_cors", Switch).value = False
        self.query_one("#bucket_public", Switch).value = False

        self.notify(f"Added bucket '{name}'")
