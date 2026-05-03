import tree_sitter_python as tsp
import tree_sitter

lang = tree_sitter.Language(tsp.language())
parser = tree_sitter.Parser(lang)

# Simulate what the test does
docstring_text = '"'
source = f'def my_func():\n    """{docstring_text}"""\n    pass\n'
print("Source repr:", repr(source))
print("Source bytes:", repr(source.encode("utf-8")))

# Write to file like the test does (with encoding="utf-8")
import tempfile, os
with tempfile.TemporaryDirectory() as tmp:
    fpath = os.path.join(tmp, "test_file.py")
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(source)
    
    # Read back as bytes
    with open(fpath, "rb") as f:
        raw_bytes = f.read()
    print("File bytes:", repr(raw_bytes))
    
    # Normalize
    normalized = raw_bytes.replace(b"\r\n", b"\n")
    print("Normalized:", repr(normalized))
    
    # Parse
    tree = parser.parse(normalized)
    
    # Check tree
    fn = tree.root_node.children[0]
    for c in fn.children:
        if c.type == "ERROR":
            print(f"ERROR node: text={c.text!r}, start={c.start_byte}, end={c.end_byte}")
            for ec in c.children:
                print(f"  child: {ec.type} text={ec.text!r}")
