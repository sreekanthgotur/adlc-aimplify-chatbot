"""ASGI entry point."""

from aimplify_intake.api.app import create_app

app = create_app()