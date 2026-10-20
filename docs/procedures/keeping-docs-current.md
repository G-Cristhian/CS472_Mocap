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
`desktop` and `frontend`. It never writes new sections, never rewrites prose,
and never touches code or the decisions sheet; those belong to people and to
the design-decision detector.

A push that touches only `docs/`, `.claude/` or `.github/` is skipped, so
merging the keeper's own pull request costs nothing.

## How you find out

When the keeper changed something, it opens one pull request from the branch
`docs/pending`, labelled `documentation`, with you as reviewer. The
description is its report: what it updated and why, what it read and found
fine, and anything it doubted and left for a human ("Check by hand"). While
that pull request is open, later runs add to it instead of opening another.

## Reviewing

1. Read the report. Each "Updated" line names a file and the statement it
   fixed.
2. Open the diff. The edits should be small and local: a changed value, a
   renamed flag, one added line beside its siblings. Anything larger is a
   reason to push back.
3. Look at the "Check by hand" lines. Those are statements the keeper thought
   might be stale but would not change on its own.
4. Merge, or edit on the branch first and then merge. The branch is deleted
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
