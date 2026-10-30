# Design decisions

A design decision is any choice in the code that could reasonably have gone another way and that later work will depend on. The sheet is [DECISIONS.md](DECISIONS.md). The point of the sheet is that nobody discovers, two weeks later, that a number somebody said out loud became an API contract.

## What counts

Record it when the change introduces or alters one of these:

- A limit or range: how many cameras, how large an upload, how long a gap.
- A threshold or tuned constant: a confidence cutoff, a pixel error, a window size, a frame rate.
- A library or model choice: a dependency added, a model made the default.
- A data contract: a schema field, a file format, a joint order, a coordinate convention, a unit.
- An algorithm choice: a method picked over an alternative, or a published method altered.
- A procedure that the code enforces: a required pose, a required clap, a required file type.

Do not record: variable renames, formatting, comments, test fixtures, obvious bug fixes, or a value that only restates a decision already on the sheet. When unsure, record it with status `needs human research` and let review decide.

The sheet trains the detector in two separate ways. Whether a row stays on the sheet is the scope call. The status is a verdict on the decision. A row marked `out of scope` teaches the detector what not to record. Every other row a human has reviewed, whether approved, rejected or sent back for research, teaches it what to record, because each one was a real decision worth a human's time. Reviewing rows is therefore never wasted, even when the verdict is no.

## The sheet's columns

| Column | What goes in it |
|---|---|
| ID | `D-NNN`, sequential, never reused. Newest rows at the bottom. |
| Lineage | `from D-NNN` and `to D-NNN` links, one layer deep (see Lineage). Empty for a root decision. |
| Decision | The choice in one sentence, with the value: "At most 4 cameras per take". |
| Where | File and line at the time the row was written, for example `backend/mocap_pipeline/config.py:14`. Lines drift; the ID and the commit are the stable handles. |
| Made by, when | Author, date and short commit of the change that introduced the choice, from `git log -S`. |
| Rationale recorded | A quote from the commit message, a comment, a docstring or a README that explains the choice, or "none recorded". |
| Citation | A published source for the choice (see Citations), or "none". |
| Status | One of the six statuses below. |
| Reviewer notes | The reviewer's verdict line, dated and signed, and any lead that is not a citation. |

## Statuses

| Status | Meaning | Who sets it |
|---|---|---|
| `needs human research` | No published source was found for the choice. A human must research it or decide it stands on its own. | detector, or a human |
| `cited, pending review` | A source was found and is in the Citation column. A human has not yet approved it. | detector |
| `approved` | A human reviewed the citation and the choice. | human only |
| `more research requested` | A human read it and wants a better source or a comparison before approving. | human only |
| `rejected` | The choice is being reversed. Note the replacement decision in Reviewer notes. | human only |
| `out of scope` | A human decided this is not a design decision. Kept as a training example. | human only |

The detector never sets `approved`, `rejected`, `more research requested` or `out of scope`, and never edits a row a human has already moved to one of those. The one exception is the Lineage column, described next.

## Lineage

Decisions replace each other over time. The Lineage column records that, one layer deep: a row names only the decisions it directly replaces and the decisions that directly replace it, never anything further back or forward. To follow a longer chain, walk the links.

| Shape | What the rows say |
|---|---|
| Linear: D-024 replaces D-001 | D-024 has `from D-001`. D-001 has `to D-024`. |
| Branch: D-001 is split into D-024 and D-025 | Both have `from D-001`. D-001 has `to D-024, D-025`. |
| Merge: D-003 and D-004 are settled together by D-026 | D-026 has `from D-003, D-004`. Each of those has `to D-026`. |

Rules:

- A root decision has an empty Lineage cell.
- Whoever adds a new row writes its `from` links. The detector writes them when a change alters a decision already on the sheet, instead of editing that row.
- The matching `to` link on the older row is a pointer, not a judgement, so adding it is allowed on any row, including reviewed ones. This is the only edit permitted on a reviewed row.
- A row with a `to` link is superseded. It keeps its status as the record of the verdict it received; no separate "superseded" status exists.
- Links point only at sheet IDs. Papers and external sources go in the Citation column.
- IDs stay flat and sequential. Do not encode lineage in the ID.

## How the detector works

The detector is the GitHub workflow `.github/workflows/design-decisions.yml`. It runs after every push to `main`, whether a pull request merge or a direct push. (GitHub's `push` event cannot drive the Claude action directly, so `push-to-main.yml` runs on the push and the detector runs when it completes.) Each run:

1. Checks out `main`, and merges in the branch `design-decisions/pending` if one exists, so rows found earlier and not yet reviewed are kept. If that merge conflicts with an edit made on `main`, the run drops the branch's version and reviews again from the marker on `main`, so the rows are found again rather than lost.
2. Takes the range from the commit recorded in `.last-reviewed` to the head of `main`. If every commit in that range touches only this folder, `.claude/` or `.github/`, there is nothing to review and the run stops here at no cost.
3. Runs Claude over the range with the procedure below, using the rules in this file and the working rules in `.claude/agents/design-interrogator.md`.
4. Writes the head of `main` into `.last-reviewed`, and if the sheet changed, pushes the sheet and the marker to `design-decisions/pending` and opens a pull request against `main` titled "[AI] Design decisions found since ...", labelled `design-decision`, with Giancarlo requested as reviewer. While that pull request is open, later runs update it instead of opening another. When nothing was found, nothing is pushed and the marker stays where it was, so the next run looks at the same range plus whatever is new.

Merging the pull request is the review act: set the Status and Reviewer notes of each new row on the branch, then merge. The branch is deleted on merge. The mechanics, from a laptop or a phone, are in `docs/procedures/reviewing-design-decisions.md`; switching the workflow on for a new repository is in `docs/procedures/enable-claude-on-github.md`.

To run it by hand, open the Actions tab, pick "Design decisions" and press Run workflow. Two optional inputs: a commit range such as `762e384..main`, and a dry-run switch that prints the report without opening or updating the pull request. The full Claude transcript is printed in the "Interrogate the commits" step and saved as the run artifact `claude-execution-output`. Runs bill the repository's `ANTHROPIC_API_KEY` secret; one commit costs about 10 to 20 cents.

The same procedure runs locally through the `design-interrogator` subagent in `.claude/agents/`, for example "use the design-interrogator subagent on 762e384..HEAD". That path writes rows to your working copy and nothing else; you commit and push them yourself.

A scheduled cloud routine was planned as a stand-in while the workflow could not run. It was never created, and the workflow has run on its own since the Claude GitHub App was installed on 2026-10-17, so the routine and its prompt file were dropped on 2026-10-18.

Procedure the detector follows:

1. Read this file and the current sheet.
2. Read the diff of the commit range and the commit messages.
3. List candidate decisions using the "What counts" rules. Skip anything already on the sheet unless the change alters it.
4. For each candidate, look for the rationale in the commit message, the diff's comments and docstrings, and the READMEs. Quote it if found. Write "none recorded" if not.
5. Search for a published source that supports the choice: a paper, a standard, or the documentation of the library or model chosen. Prefer a DOI. Mark a DOI `(unverified)` if it could not be opened. Never invent a source. If nothing is found, say so.
6. Add a row with the next free ID, status `cited, pending review` when a source was found, otherwise `needs human research`. If the change alters a decision already on the sheet, the new row gets `from D-NNN` in Lineage and the old row gets the matching `to` link.
7. Write a short report in the shape the agent file gives: the range and commit count, the new rows with their statuses and lineage, and what was considered and skipped, with the reason. The report becomes the pull request description.

## Citations

A citation is a paper, book, standard, or the official documentation of the chosen library or model. A blog post or forum answer is not a citation but may be noted in Reviewer notes as a lead. Record author, title, venue, year and DOI where one exists. When a DOI has been opened and matches, leave it bare. When it has not, append `(unverified)`.

## Files in this folder

| File | What it is |
|---|---|
| `DECISIONS.md` | The sheet. |
| `README.md` | This file: what counts, the columns, statuses, lineage, how the detector works, citations. |
| `.last-reviewed` | One commit SHA: the last commit on `main` the detector has reviewed. Advanced only by the detector, through the review pull request. Delete it to make the next run review everything since `0e1eea9`, the seed commit. |
