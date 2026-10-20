# Enable Claude on the GitHub repository

For the repository owner. Takes about fifteen minutes. Needed once, before the design-decision workflow in `.github/workflows/design-decisions.yml` can run. Done on 2026-10-17; kept for the next repository.

Every step here needs admin on `G-Cristhian/CS472_Mocap`. The repository is owned by a personal account, and GitHub gives collaborators on a personal repository write access only; there is no admin role to hand out. So as of 2026-10-16 all four steps are Cristhian's. (Moving the repository into a GitHub organization, which is free, would let other members be made admins and would let the app be installed once for every repository the team creates.)

You also need an Anthropic Console account at https://console.anthropic.com with billing set up.

## 1. Install the Claude GitHub App (repository owner only)

The workflow authenticates through the app, so this comes first. A GitHub App installs on the account that owns the repository; a collaborator who opens the install dialog sees only their own repositories.

Installed on 2026-10-17. Before that, the team's agent-made pull requests were pushed from Claude Code sessions under Cristhian's own account, which does not involve the app.

By hand, no tools needed: open https://github.com/apps/claude, click Install, choose "Only select repositories", pick `G-Cristhian/CS472_Mocap`, confirm.

Or from the Claude Code CLI. The CLI is a separate install from the desktop app; if `claude` is not recognised in your terminal, install it first (Node and npm must be present):

```
npm install -g @anthropic-ai/claude-code
```

Open a new terminal, `cd` into the repository, run `claude`, and once the session prompt appears type `/install-github-app`. That command is a slash command inside the Claude session, not a shell command. Pick `G-Cristhian/CS472_Mocap` when asked. The command installs the app, offers to store an API key as a repository secret, and offers to add a `claude.yml` workflow. Accept the secret step (it saves step 2). The `claude.yml` it offers is for `@claude` mentions on issues and pull requests, which is a separate feature; accept or decline as you like.

Or install it by hand: open https://github.com/apps/claude, choose Install, select the repository.

## 2. Add the API key secret

Skip if step 1 stored it.

1. Console: https://console.anthropic.com, API Keys, Create Key. Name it `cs472-mocap-github`. Copy it once; it is not shown again.
2. GitHub: repository Settings, Secrets and variables, Actions, New repository secret. Name `ANTHROPIC_API_KEY`, paste the key.

Set a monthly spend limit on the Console workspace while you are there, under Limits. The workflow runs once per push to `main` and skips pushes that touch only the sheet's own files; a run costs cents (about 10 to 20 cents for one commit), but a limit means a bug cannot run up a bill.

## 3. Let Actions open pull requests

Repository Settings, Actions, General, scroll to Workflow permissions:

- select "Read and write permissions"
- tick "Allow GitHub Actions to create and approve pull requests"

Without the tick, the workflow edits the sheet and then fails at the pull-request step.

## 4. Merge the workflow

The workflow, the agent definition and the decisions sheet arrive in one pull request. Merge it to `main`. The first push to `main` after that is the first live run.

## 5. Test it by hand

Actions tab, "Design decisions", Run workflow, enter a range such as `762e384..main`, tick dry run, Run. Within a few minutes you should see a green run whose "Did the sheet change?" step prints the report. Run it again without dry run and, if rows were found, a pull request titled "[AI] Design decisions found since ..." opens from the branch `design-decisions/pending` with Giancarlo requested as reviewer.

If the run is red at the "Interrogate the commits" step, the usual causes are a missing `ANTHROPIC_API_KEY` secret or the app not installed on this repository; the step's log says which. Note that the secret belongs to this repository only: a fork carrying the workflow fails every run until the file is deleted there. If it is red at "Open or update the review PR", step 3 was skipped.

## 6. Reviewing what it finds

Review happens in that pull request. Edit the Status and Reviewer notes columns of the new rows in `docs/decisions/DECISIONS.md` before merging. The statuses and what they mean are in `docs/decisions/README.md`.

## The hourly routine (dropped)

A scheduled cloud routine was planned as a stand-in while the workflow could not run. On 2026-10-16 creating it under a collaborator's account was refused with `repo_access_denied`: for a private repository owned by another personal account, the App install in step 1 is required for a routine as well. Once step 1 was done the workflow ran on its own, so the routine was never created and its prompt file (`docs/decisions/routine-prompt.md`) was removed on 2026-10-18. Forks of this repository that still carry the old workflow fail every scheduled run for lack of the secret; delete the workflow file there rather than adding a key.
