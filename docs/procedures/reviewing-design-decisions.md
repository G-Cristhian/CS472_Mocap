# Reviewing design decisions

For whoever is the reviewer, currently Giancarlo. Works from a laptop or a phone. The rules for what the statuses mean are in `docs/decisions/README.md`; this is only the mechanics.

## How you find out

The detector (the hourly routine, or the GitHub workflow once the app is installed) opens one pull request from the branch `design-decisions/pending` and requests you as reviewer. GitHub notifies you by email and, if you have the GitHub mobile app, by push notification. While that pull request stays open, later runs add their findings to it as comments instead of opening more. Quiet hours add nothing.

## Reviewing on a laptop

1. Open the pull request. The description and comments list the new rows and the commits they came from.
2. Open `docs/decisions/DECISIONS.md` on the branch and, for each new row, set the Status column to one of `approved`, `rejected`, `more research requested` or `out of scope`, and write a line in Reviewer notes if the verdict needs one. Leave a row alone if you want to come back to it; it stays `cited, pending review` or `needs human research`.
3. Merge. Squash is fine; the branch is deleted on merge and the next run starts fresh from main.

## Reviewing on a phone

Two ways, pick whichever is open.

**GitHub mobile app.** Open the pull request, go to Files, open `DECISIONS.md`, tap the pencil to edit the file on the branch, change the Status cells, commit. Then merge from the pull request screen.

**Claude Code on the phone.** Open a Claude Code session on the repository and dictate the verdicts, for example: "On the design-decisions/pending branch, in docs/decisions/DECISIONS.md, mark D-025 approved, D-026 out of scope with the note 'variable rename', and leave D-027. Commit and push." Then merge from the GitHub app or the pull request page. The session can also run the routine's procedure by hand if you want a review before the next hour: "use the design-interrogator subagent on <sha>..HEAD".

## Running it by hand

From the routines page at claude.ai/code/routines, open "Design decisions, hourly" and run it now. Each run can be opened as a full session to read what the agent did. Routines draw down the subscription usage of the account that owns them; the total is at claude.ai/settings/usage, and no per-run token breakdown is shown.

## When a row has no source

`needs human research` means the detector found no paper, standard or documentation for the choice. Either find one and put it in the Citation column, open a research issue (label `research`) and set `more research requested`, or decide the choice stands on its own and approve it with a note saying so.
