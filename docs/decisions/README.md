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

When a pull request merges into `main`, and once an hour as a sweep for direct pushes, the workflow in `.github/workflows/design-decisions.yml` runs Claude over the commits on `main` since the one recorded in `.last-reviewed`, with the procedure below. If it adds rows, it opens a pull request against `main` from the branch `design-decisions/pending`, requests review from the maintainers, and adds later findings to that same pull request until it is merged. Quiet hours add nothing. Merging the PR is the review act: edit the Status and Reviewer notes columns in the PR before merging. (GitHub's `push` event cannot be used: the Claude action refuses it.)

The same procedure runs locally through the `design-interrogator` subagent in `.claude/agents/`, for example "use the design-interrogator subagent on 762e384..HEAD".

The same procedure also runs as a scheduled cloud routine, "Design decisions, hourly", because the GitHub workflow needs the Claude GitHub App installed by the repository owner. The routine's prompt is kept in [routine-prompt.md](routine-prompt.md). Every hour it checks main for commits newer than the one recorded in `.last-reviewed`, reviews them, advances the marker, and pushes to the branch `design-decisions/pending`. It opens a pull request only when rows were added, and adds later findings to that pull request as comments until it is merged. The workflow and the routine share the branch and the marker, so running both never reviews a commit twice. How to review what either of them finds, from a laptop or a phone, is in `docs/procedures/reviewing-design-decisions.md`.

Procedure the detector follows:

1. Read this file and the current sheet.
2. Read the diff of the commit range and the commit messages.
3. List candidate decisions using the "What counts" rules. Skip anything already on the sheet unless the change alters it.
4. For each candidate, look for the rationale in the commit message, the diff's comments and docstrings, and the READMEs. Quote it if found. Write "none recorded" if not.
5. Search for a published source that supports the choice: a paper, a standard, or the documentation of the library or model chosen. Prefer a DOI. Mark a DOI `(unverified)` if it could not be opened. Never invent a source. If nothing is found, say so.
6. Add a row with the next free ID, status `cited, pending review` when a source was found, otherwise `needs human research`. If the change alters a decision already on the sheet, the new row gets `from D-NNN` in Lineage and the old row gets the matching `to` link.
7. Write a short report listing the new rows and the commits they came from.

## Citations

A citation is a paper, book, standard, or the official documentation of the chosen library or model. A blog post or forum answer is not a citation but may be noted in Reviewer notes as a lead. Record author, title, venue, year and DOI where one exists. When a DOI has been opened and matches, leave it bare. When it has not, append `(unverified)`.
