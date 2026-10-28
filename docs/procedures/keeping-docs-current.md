# Keeping the docs current

For whoever reviews documentation, currently Giancarlo. Works from a laptop
or a phone.

## What runs

After every push to `main`, the workflow `.github/workflows/docs-upkeep.yml`
hands the commits since its last successful run to Claude with the rules in
`.claude/agents/docs-keeper.md`. The keeper looks for statements the change
made false: a flag or default, a file name, a step, a printed message, a
number a doc quotes, a function entry in the backend outline. It fixes each
one with the smallest edit, in these files only: everything under `docs/`
except the decisions sheet, plus the three READMEs under `backend/mocap_pipeline`,
`desktop` and `frontend`, and the two environment templates `frontend/.env.example`
and `backend/.env_` (variable names and comments, never a secret). It never
writes new sections, never rewrites prose,
and never touches the decisions sheet; that belongs to the design-decision
detector.

It also looks for comments and docstrings that mislead. That means comments
the change made false anywhere in the code, and dead comments in the files
the change touched: a name or file that no longer exists, a value that
disagrees with the code beside it, finished work still called a placeholder
or "for now", or a docstring whose parameters do not match the function. It
fixes those in Python files under `backend/` (not `backend/legacy/` or
migrations), changing only comment and docstring text. Every Python file it
edits goes through `.github/scripts/check_comment_only.py`, which compares
the code before and after with comments and docstrings ignored; any file
whose code changed is put back, and the report says so. Comments in
TypeScript, YAML and other files are listed in the report for a person to
fix. When a comment states what the code must do and the code does something
else, the keeper does not touch either: it reports a possible bug.

A push that touches only `docs/`, `.claude/` or `.github/` is skipped, and so
is a push made only of the keeper's own merged fixes, so merging its pull
request costs nothing.

## How you find out

When the keeper changed something, it opens one pull request from the branch
`docs/pending`, labelled `documentation`, with you as reviewer. The
description is its report: what it updated and why, what it read and found
fine, and anything it doubted and left for a human ("Check by hand"). While
that pull request is open, later runs add to it instead of opening another.

If someone edits the same lines on `main` while the pull request is open, the
next run cannot merge the branch. It does not stop: it drops the branch's
version, reviews again from the commit the branch was based on, and rewrites
the pull request from the result. Nothing is lost, but a fix you made on the
branch by hand is redone by the keeper, so merge soon after editing it.

## Reviewing

1. Read the report. Each "Updated" line names a file and the statement it
   fixed.
2. Open the diff. The edits should be small and local: a changed value, a
   renamed flag, one added line beside its siblings, a corrected comment.
   Anything larger is a reason to push back. In Python files only comment
   and docstring lines should change; the workflow has already checked that,
   but a reworded comment can still be wrong, so read it against the code.
3. Look at the "Check by hand" lines. Those are statements the keeper thought
   might be stale but would not change on its own.
4. Read "Possible bugs" first among the comment sections. Each is a place
   where a comment says what the code must do and the code disagrees; decide
   which one is wrong, and open an issue if it is the code. "Comments to fix
   by hand" are corrections in files the keeper may not edit, with the
   replacement text ready to paste.
5. Merge, or edit on the branch first and then merge. The branch is deleted
   on merge.

## Running it by hand

On GitHub, open Actions, pick "Docs upkeep" and press Run workflow. Two
optional inputs: a commit range such as `762e384..main`, and a dry-run switch
that prints the report without opening a pull request. The full Claude
transcript is in the "Check the docs against the change" step and the run
artifact `claude-execution-output`. Runs bill the repository's
`ANTHROPIC_API_KEY` secret; a one-commit run costs about 10 to 30 cents, more
when the backend outline needs reading.

The same rules run locally as a subagent: "use the docs-keeper subagent on
`<sha>..HEAD`". That path edits your working copy and nothing else; you
commit and push.

## Needs the same switch as the decision detector

Both workflows open pull requests, so both need the repository setting
"Allow GitHub Actions to create and approve pull requests" (step 3 in
[enable-claude-on-github.md](enable-claude-on-github.md)). Until it is on,
the run goes green up to the pull-request step and fails there; the fixes sit
on the `docs/pending` branch.
