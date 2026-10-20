# Reviewing design decisions

For whoever is the reviewer, currently Giancarlo. Works from a laptop or a phone. The rules for what the statuses mean are in `docs/decisions/README.md`; this is only the mechanics.

## How you find out

The detector (the GitHub workflow `design-decisions.yml`, which runs after every push to `main`) opens one pull request from the branch `design-decisions/pending` and requests you as reviewer. GitHub notifies you by email and, if you have the GitHub mobile app, by push notification. While that pull request stays open, later runs add their findings to it instead of opening more. A push with nothing to review adds nothing.

## Reviewing on a laptop

1. Open the pull request. The description and comments list the new rows and the commits they came from.
2. Open `docs/decisions/DECISIONS.md` on the branch and, for each new row, set the Status column to one of `approved`, `rejected`, `more research requested` or `out of scope`, and write a line in Reviewer notes if the verdict needs one. Leave a row alone if you want to come back to it; it stays `cited, pending review` or `needs human research`.
3. Merge. Squash is fine; the branch is deleted on merge and the next run starts fresh from main.

## Reviewing on a phone

Two ways, pick whichever is open.

**GitHub mobile app.** Open the pull request, go to Files, open `DECISIONS.md`, tap the pencil to edit the file on the branch, change the Status cells, commit. Then merge from the pull request screen.

**Claude Code on the phone.** Open a Claude Code session on the repository and dictate the verdicts, for example: "On the design-decisions/pending branch, in docs/decisions/DECISIONS.md, mark D-025 approved, D-026 out of scope with the note 'variable rename', and leave D-027. Commit and push." Then merge from the GitHub app or the pull request page. The session can also run the detector's procedure by hand: "use the design-interrogator subagent on <sha>..HEAD".

## Running it by hand

On GitHub, open Actions, pick "Design decisions" and press Run workflow. Two optional inputs: a commit range such as `762e384..main` (the default is everything since the marker in `docs/decisions/.last-reviewed`), and a dry-run switch that prints the report in the job log without opening or updating the pull request. The full Claude transcript is printed in the "Interrogate the commits" step and saved as the run artifact `claude-execution-output`. Runs bill the Anthropic API key in the repository's `ANTHROPIC_API_KEY` secret; the cost of each run is in the transcript's final result block.

## When a row has no source

`needs human research` means the detector found no paper, standard or documentation for the choice. Either find one and put it in the Citation column, open a research issue (label `research`) and set `more research requested`, or decide the choice stands on its own and approve it with a note saying so.
