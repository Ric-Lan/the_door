from the_door.core.datamodel.datamodel_hints import code_site_reason, schema_file_reason


def test_code_site_reason_name_hit():
    assert code_site_reason("save_user", "svc/user.py") == "name contains 'save'"
    assert code_site_reason("UserRepository", "a/b.py") == "name contains 'repository'"


def test_code_site_reason_dir_hit():
    assert code_site_reason("plain", "app/models/user.py") == "file under 'models/'"
    assert code_site_reason("plain", "schema/x.py") == "file under 'schema/'"


def test_code_site_reason_miss():
    assert code_site_reason("render", "ui/view.py") is None


def test_schema_file_reason_suffix():
    assert schema_file_reason("db/init.sql") == "schema file (.sql)"
    assert schema_file_reason("data/seed.csv") == "schema file (.csv)"


def test_schema_file_reason_json_hint():
    assert schema_file_reason("conf/schema.json") == "schema-like json (name contains 'schema')"
    assert schema_file_reason("model.json") == "schema-like json (name contains 'model')"


def test_schema_file_reason_json_miss_and_other_miss():
    assert schema_file_reason("package.json") is None
    assert schema_file_reason("src/app.py") is None


def test_path_separator_normalized():
    assert code_site_reason("plain", "app\\\\models\\\\user.py") == "file under 'models/'"
