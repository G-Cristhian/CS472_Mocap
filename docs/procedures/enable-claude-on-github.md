# Enable Claude on the GitHub repository

For the repository owner. Takes about fifteen minutes. Needed once, before the design-decision workflow in `.github/workflows/design-decisions.yml` can run.

What you need: admin on `G-Cristhian/CS472_Mocap`, an Anthropic Console account at https://console.anthropic.com with billing set up, and the `gh` command signed in on your machine (`gh auth status`).

## 1. Install the Claude GitHub App (repository owner only)

The workflow authenticates through the app, so this comes first. A GitHub App installs on the account that owns the repository, so only Cristhian can do this step; a collaborator with admin sees only their own repositories in the install dialog. Steps 2 to 4 can be done by any repository admin.

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

## 4. Discord notification (optional)

1. In Discord, open the channel that should get the pings. Channel settings, Integrations, Webhooks, New Webhook. Name it, Copy Webhook URL.
2. GitHub: Settings, Secrets and variables, Actions, New repository secret. Name `DISCORD_WEBHOOK_URL`, paste the URL.

With no secret the workflow skips the Discord step and relies on GitHub's own review-request notification.

## 5. Merge the workflow

The workflow, the agent definition and the decisions sheet arrive in one pull request. Merge it to `main`. The first push to `main` after that is the first live run.

## 6. Test it by hand

Actions tab, "Design decisions", Run workflow, enter a range such as `762e384..main`, Run. Within a few minutes you should see:

- a run that finishes green
- a pull request titled "Design decisions found in ..." on a `design-decisions/` branch, with Giancarlo requested as reviewer
- a message in the Discord channel, if step 4 was done

If the run is red at the "Interrogate the commits" step, the usual causes are a missing `ANTHROPIC_API_KEY` secret or the app not installed on this repository. If it is red at "Open a review PR", step 3 was skipped.

## 7. Reviewing what it finds

Review happens in that pull request. Edit the Status and Reviewer notes columns of the new rows in `docs/decisions/DECISIONS.md` before merging. The statuses and what they mean are in `docs/decisions/README.md`.
