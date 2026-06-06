"""CLI command: scan — scan codebase for known vulnerabilities."""
from __future__ import annotations
import json
import sys
import click


@click.command("scan")
@click.argument("codebase_path", type=click.Path(exists=True))
@click.option("--json", "output_json", is_flag=True, help="Output raw vulnerabilities as JSON")
@click.option("--offline", is_flag=True, help="Use local OSV database (air-gapped mode)")
@click.option("-o", "--output", "output_file", type=click.Path(), default=None, help="Write output to file")
def scan_cmd(codebase_path: str, output_json: bool, offline: bool, output_file: str | None):
    """Scan codebase for known vulnerabilities using osv-scanner."""
    from pathlib import Path
    from the_door.core.vulnerability.vulnerability_scanner import VulnerabilityScanner

    scanner = VulnerabilityScanner(offline=offline)

    if not scanner.check_availability():
        click.echo("osv-scanner is not installed. Install it from: https://github.com/google/osv-scanner", err=True)
        click.echo("  brew install osv-scanner  (macOS)", err=True)
        click.echo("  go install github.com/google/osv-scanner/cmd/osv-scanner@latest  (Go)", err=True)
        sys.exit(1)

    result = scanner.scan(Path(codebase_path))

    # Print warnings
    for warning in result.warnings:
        click.echo(f"Warning: {warning}", err=True)

    if output_json:
        # Raw JSON output
        data = [
            {"cve_id": e.cve_id, "package": e.package, "version": e.version,
             "severity": e.severity, "cvss": e.cvss, "source": e.source}
            for e in result.entries
        ]
        text = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        # Human-readable summary
        if not result.entries:
            text = "✅ 未偵測到已知漏洞 (No known vulnerabilities detected)"
        else:
            lines = []
            # Count by severity
            counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for e in result.entries:
                counts[e.severity] = counts.get(e.severity, 0) + 1

            # Header
            header_parts = []
            if counts["critical"] + counts["high"] > 0:
                header_parts.append(f"🔴 {counts['critical'] + counts['high']} 個高風險")
            if counts["medium"] > 0:
                header_parts.append(f"🟠 {counts['medium']} 個中風險")
            if counts["low"] > 0:
                header_parts.append(f"{counts['low']} 個低風險")
            lines.append(" | ".join(header_parts))
            lines.append("")

            # Details sorted by severity
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            sorted_entries = sorted(result.entries, key=lambda e: (severity_order.get(e.severity, 9), -(e.cvss or 0.0)))
            for e in sorted_entries:
                action = "立即更新" if e.severity in ("critical", "high") else ("建議更新" if e.severity == "medium" else "留意追蹤")
                lines.append(f"  {e.severity.upper():8s} {e.cve_id:20s} {e.package}@{e.version}  → {action}")

            # DB freshness
            if result.db_freshness:
                lines.append("")
                if result.db_freshness.mode == "online":
                    lines.append(f"資料來源：OSV.dev（掃描時間：{result.db_freshness.timestamp[:16]}）")
                else:
                    lines.append(f"資料來源：本地 OSV 資料庫（更新時間：{result.db_freshness.timestamp[:16]}）")
                if result.db_freshness.stale_warning:
                    lines.append(f"⚠ {result.db_freshness.stale_warning}")

            text = "\n".join(lines)

    if output_file:
        from pathlib import Path as P
        P(output_file).write_text(text, encoding="utf-8")
        click.echo(f"Output written to {output_file}")
    else:
        click.echo(text)

    from the_door.cli.post_run_hook import cli_post_run_hook
    cli_post_run_hook(codebase_path, json_mode_active=output_json)
