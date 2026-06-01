"""Public surface for the core/ui/api package."""
from __future__ import annotations

from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.router import Route, Router, build_routes

__all__ = ["APIContext", "Route", "Router", "build_routes"]
