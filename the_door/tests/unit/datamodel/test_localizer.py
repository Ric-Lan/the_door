from the_door.models import ASTNode, ExtractionResult
from the_door.core.datamodel.datamodel_localizer import DataModelLocalizer


def _node(node_id, name, file):
    return ASTNode(node_id=node_id, type="method", name=name, file=file, language="python")


def test_code_candidates_hit_and_miss(tmp_path):
    result = ExtractionResult(nodes=[
        _node("m1", "save_user", "svc/user.py"),        # name hit
        _node("m2", "render_page", "ui/view.py"),        # miss
        _node("m3", "load", "app/models/user.py"),       # dir hit
    ])
    loc = DataModelLocalizer().localize(result, str(tmp_path))
    ids = {c.node_id for c in loc.code_candidates}
    assert ids == {"m1", "m3"}
    assert all(c.kind == "code_site" for c in loc.code_candidates)


def test_schema_candidates_from_filesystem(tmp_path):
    (tmp_path / "init.sql").write_text("CREATE TABLE u(id int);", encoding="utf-8")
    (tmp_path / "seed.csv").write_text("id,name\n", encoding="utf-8")
    sub = tmp_path / "conf"
    sub.mkdir()
    (sub / "schema.json").write_text("{}", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")  # miss

    loc = DataModelLocalizer().localize(ExtractionResult(nodes=[]), str(tmp_path))
    files = {c.file for c in loc.schema_candidates}
    assert files == {"init.sql", "seed.csv", "conf/schema.json"}
    assert all(c.kind == "schema_file" and c.node_id == "" for c in loc.schema_candidates)


def test_zero_hits(tmp_path):
    loc = DataModelLocalizer().localize(
        ExtractionResult(nodes=[_node("m9", "render", "ui/v.py")]), str(tmp_path))
    assert loc.code_candidates == ()
    assert loc.schema_candidates == ()
