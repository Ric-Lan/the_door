from __future__ import annotations
from the_door.core.flow_guard import Decision, FlowGuard


class CheckpointRenderer:
    def __init__(self, guard: FlowGuard | None = None):
        self._guard = guard or FlowGuard()

    def prompt(self, decision: Decision) -> str:
        if decision.is_resolved:
            return decision.chosen  # type: ignore[return-value]

        self._print_checkpoint(decision)

        while True:
            try:
                raw = input("請輸入選項：").strip()
            except EOFError:
                raise EOFError("非互動環境，無法等待使用者輸入")

            resolved = self._guard.check(
                decision.checkpoint_name,
                decision.status,
                decision.options,
                choice=raw,
            )
            if resolved.is_resolved:
                return resolved.chosen  # type: ignore[return-value]
            print(f"⚠ 無效選項：{raw!r}，請重新輸入")

    def _print_checkpoint(self, decision: Decision) -> None:
        print(f"\n[CHECKPOINT: {decision.checkpoint_name}]")
        print(f"狀態：{decision.status}")
        print("請選擇：")
        for opt in decision.options:
            print(f"  {opt.key}) {opt.label}")
            if opt.next_call:
                print(f"     → {opt.next_call}")
        print()
