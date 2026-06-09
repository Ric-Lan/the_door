"""Enable `python -m the_door` to invoke the same CLI entry point as the
installed `the-door` console script (the_door.cli.main:main).

This makes the from-source dev invocation `python -m the_door mcp-serve`
(documented in CLAUDE.md / .mcp.json) work without requiring the package
to be pip-installed.
"""
from the_door.cli.main import main

if __name__ == "__main__":
    main()
