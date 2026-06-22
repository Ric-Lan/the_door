"""CLI: the-door locate — 人讀的 symbol 定位點查（secondary；資料非即時）。"""
from __future__ import annotations

import click

from the_door.core.structure_view import locator


def _echo_freshness(freshness: dict) -> None:
    status = freshness.get("status")
    if status == "stale":
        n = freshness.get("changed_count", 0)
        click.echo(f"⚠ structure-view 可能過時（{n} 個檔已變動）；重跑 extract_structure 以更新")
    elif status == "unknown":
        click.echo("⚠ 無法判斷 structure-view 新鮮度（未跑過 edge_residue）")


@click.group("locate")
def locate_group():
    """對既有 structure-view 做 symbol 定位點查（輔助功能；資料非即時、名稱比對非語意搜尋）。"""


@locate_group.command("search")
@click.argument("query")
@click.option("--codebase-path", default=".", help="Codebase root (default: cwd).")
@click.option("--limit", default=locator.SEARCH_DEFAULT_LIMIT, show_default=True,
              help="Max results.")
def search_cmd(query, codebase_path, limit):
    """用名稱/路徑子字串找 symbol。"""
    try:
        result = locator.search(codebase_path, query, limit)
    except locator.LocateError as exc:
        raise click.ClickException(str(exc))
    for r in result["results"]:
        click.echo(f"{r['match_kind']:4}  {r['file']}:{r['start_line']}  "
                   f"{r['node_id']}  (in:{r['in_degree']})")
    click.echo(f"matched {result['total_matched']}, shown {result['returned']}")
    _echo_freshness(result["freshness"])


@locate_group.command("node")
@click.argument("node_id")
@click.option("--codebase-path", default=".", help="Codebase root (default: cwd).")
def node_cmd(node_id, codebase_path):
    """看單一 node 的位置 + callers/callees。"""
    try:
        result = locator.node(codebase_path, node_id)
    except locator.LocateError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"{result['node_id']}  {result['file']}:"
               f"{result['start_line']}-{result['end_line']}")
    for label, key in (("callers", "callers"), ("callees", "callees")):
        click.echo(f"{label}:")
        for c in result[key]:
            loc = f"  {c.get('file')}:{c.get('start_line')}" if c.get("file") else ""
            click.echo(f"  {c['node_id']}{loc}")
    _echo_freshness(result["freshness"])
