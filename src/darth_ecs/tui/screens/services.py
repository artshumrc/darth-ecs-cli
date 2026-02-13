"""Services screen — add ECS services (name, Dockerfile, port, domain)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static


class ServicesScreen(Screen):
    """Configure one or more ECS services."""

    def __init__(self, state: dict) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        with Vertical(classes="form-container"):
            yield Static("Services Configuration", classes="title")
            yield Static(
                f"Services added: {len(self._state.get('services', []))}",
                id="count",
            )

            yield Label("Service name:", classes="section-label")
            yield Input(placeholder="django", id="svc_name")

            yield Label("Dockerfile path:", classes="section-label")
            yield Input(
                placeholder="Dockerfile", id="svc_dockerfile", value="Dockerfile"
            )

            yield Label("Build context:", classes="section-label")
            yield Input(placeholder=".", id="svc_context", value=".")

            yield Label(
                "Container port (leave empty for workers):", classes="section-label"
            )
            yield Input(placeholder="8000", id="svc_port", value="8000")

            yield Label("Domain (required if port is set):", classes="section-label")
            yield Input(placeholder="myapp.example.com", id="svc_domain")

            yield Label("Health check path:", classes="section-label")
            yield Input(placeholder="/health", id="svc_health", value="/health")

            yield Label("Command override (optional):", classes="section-label")
            yield Input(placeholder="", id="svc_command")

            with Vertical(classes="button-row"):
                yield Button("+ Add Service", id="add", variant="default")
                yield Button("Next →", id="next", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add":
            self._add_service()
        elif event.button.id == "next":
            # Add the current form if filled
            name = self.query_one("#svc_name", Input).value.strip()
            if name:
                self._add_service()
            if not self._state.get("services"):
                self.notify("Add at least one service", severity="error")
                return
            self.app.advance_to("rds")

    def _add_service(self) -> None:
        name = self.query_one("#svc_name", Input).value.strip()
        if not name:
            self.notify("Service name is required", severity="error")
            return

        port_str = self.query_one("#svc_port", Input).value.strip()
        port = int(port_str) if port_str else None
        domain = self.query_one("#svc_domain", Input).value.strip() or None
        command = self.query_one("#svc_command", Input).value.strip() or None

        if port is not None and not domain:
            self.notify("Domain is required when port is set", severity="error")
            return

        svc = {
            "name": name,
            "dockerfile": self.query_one("#svc_dockerfile", Input).value.strip()
            or "Dockerfile",
            "build_context": self.query_one("#svc_context", Input).value.strip() or ".",
            "port": port,
            "domain": domain,
            "health_check_path": self.query_one("#svc_health", Input).value.strip()
            or "/health",
            "command": command,
        }

        self._state.setdefault("services", []).append(svc)
        count = len(self._state["services"])
        self.query_one("#count", Static).update(f"Services added: {count}")

        # Clear form for next service
        self.query_one("#svc_name", Input).value = ""
        self.query_one("#svc_port", Input).value = "8000"
        self.query_one("#svc_domain", Input).value = ""
        self.query_one("#svc_command", Input).value = ""

        self.notify(f"Added service '{name}'")
