"""
Checks that edits to Python files changed only comments and docstrings.

    python .github/scripts/check_comment_only.py <base-ref> <file> [<file> ...]

For each file, parses the version at <base-ref> and the working copy and
compares the two syntax trees with every docstring removed. Comments never
reach the syntax tree, so equal trees mean only comments, docstrings or
layout changed. Prints one line per file:

    ok <file>
    code-changed <file>
    does-not-parse <file>
    new-file <file>

and exits 1 if any file is not ok. The docs-upkeep workflow puts back every
file that is not ok, so the docs keeper can fix comments but never code.
"""
import ast
import subprocess
import sys

DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def without_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, DOCSTRING_OWNERS) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                node.body = node.body[1:] or [ast.Pass()]
    return tree


def shape(source: str) -> str:
    return ast.dump(without_docstrings(ast.parse(source)), include_attributes=False)


def at_ref(ref: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True)
    return result.stdout.decode("utf-8") if result.returncode == 0 else None


def check(ref: str, path: str) -> str:
    before = at_ref(ref, path)
    if before is None:
        return "new-file"
    with open(path, encoding="utf-8") as fp:
        after = fp.read()
    try:
        after_shape = shape(after)
    except SyntaxError:
        return "does-not-parse"
    return "ok" if shape(before) == after_shape else "code-changed"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    ref, paths = argv[0], argv[1:]
    bad = 0
    for path in paths:
        verdict = check(ref, path)
        print(f"{verdict} {path}")
        bad += verdict != "ok"
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
