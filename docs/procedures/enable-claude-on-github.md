# Enable Claude on the GitHub repository

For the repository owner. Takes about fifteen minutes. Needed once, before the design-decision workflow in `.github/workflows/design-decisions.yml` can run. Until then the same job runs as an hourly cloud routine that needs no owner action; see `docs/decisions/routine-prompt.md` and the section at the end of this file.

Every step here needs admin on `G-Cristhian/CS472_Mocap`. The repository is owned by a personal account, and GitHub gives collaborators on a personal repository write access only; there is no admin role to hand out. So as of 2026-10-16 all four steps are Cristhian's. (Moving the repository into a GitHub organization, which is free, would let other members be made admins and would let the app be installed once for every repository the team creates.)

You also need an Anthropic Console account at https://console.anthropic.com with billing set up.

## 1. Install the Claude GitHub App (repository owner only)

The workflow authenticates through the app, so this comes first. A GitHub App installs on the account that owns the repository; a collaborator who opens the install dialog sees only their own repositories.

As of 2026-10-16 the app is not installed. The team's existing agent-made pull requests were pushed from Claude Code sessions under Cristhian's own account, which does not involve the app.

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

Set a monthly spend limit on the Console workspace while you are there, under Limits. The workflow runs once per push to main and a run costs cents, but a limit means a bug cannot run up a bill.

## 3. Let Actions open pull requests

Repository Settings, Actions, General, scroll to Workflow permissions:

- select "Read and write permissions"
- tick "Allow GitHub Actions to create and approve pull requests"

Without the tick, the workflow edits the sheet and then fails at the pull-request step.

## 4. Merge the workflow

The workflow, the agent definition and the decisions sheet arrive in one pull request. Merge it to `main`. The first push to `main` after that is the first live run.

## 5. Test it by hand

Actions tab, "Design decisions", Run workflow, enter a range such as `762e384..main`, Run. Within a few minutes you should see:

- a run that finishes green
- a pull request titled "Design decisions found in ..." on a `design-decisions/` branch, with Giancarlo requested as reviewer

If the run is red at the "Interrogate the commits" step, the usual causes are a missing `ANTHROPIC_API_KEY` secret or the app not installed on this repository. If it is red at "Open a review PR", step 3 was skipped.

## 6. Reviewing what it finds

Review happens in that pull request. Edit the Status and Reviewer notes columns of the new rows in `docs/decisions/DECISIONS.md` before merging. The statuses and what they mean are in `docs/decisions/README.md`.

## Without the owner: the hourly routine

A scheduled cloud routine does the same job without the GitHub App, using a collaborator's own GitHub token. Any collaborator with push access can set this up for their account:

1. Install the Claude Code CLI if `claude` is not recognised: `npm install -g @anthropic-ai/claude-code`.
2. Make sure `gh auth status` shows you signed in to GitHub.
3. Run `claude`, then inside the session `/login` (claude.ai account, not an API key), then `/web-setup`. It asks to send your `gh` token to your Claude account and prints "Connected as <username>". From then on cloud sessions and routines under your account can clone and push any repository that token can reach.
4. The routine "Design decisions, hourly" at https://claude.ai/code/routines then runs under that access. Its prompt is `docs/decisions/routine-prompt.md`. Enable it there if it is disabled.

Routines draw down the subscription usage of the account that owns them, visible at https://claude.ai/settings/usage.
