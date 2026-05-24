from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckpointOption:
    key: str
    label: str
    next_call: str = ""


@dataclass
class Decision:
    checkpoint_name: str
    status: str
    options: list[CheckpointOption]
    chosen: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.chosen is not None


class FlowGuard:
    def check(
        self,
        name: str,
        status: str,
        options: list[CheckpointOption],
        choice: str | None = None,
    ) -> Decision:
        if not options:
            raise ValueError("options must not be empty")
        keys = [o.key for o in options]
        if len(keys) != len(set(keys)):
            dupes = [k for k in keys if keys.count(k) > 1]
            raise ValueError(f"duplicate option key: {dupes[0]}")

        resolved_choice = None
        if choice is not None:
            normalized = choice.upper()
            if normalized in {o.key.upper() for o in options}:
                resolved_choice = next(
                    o.key for o in options if o.key.upper() == normalized
                )

        return Decision(
            checkpoint_name=name,
            status=status,
            options=options,
            chosen=resolved_choice,
        )
