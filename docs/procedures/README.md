# Procedures

Step-by-step guides for things the team does more than once. Each one says who it is for and what has to be true before you start. Code reference lives in `backend/mocap_pipeline/README.md`; these are the orders of operations.

| Procedure | When |
|---|---|
| [mac-setup.md](mac-setup.md) | before a session: install the pipeline on the laptop and prove it works without footage |
| [filming.md](filming.md) | the recording session: phones, room, performer, the take plan, getting the files off, checking them before leaving |
| [processing-a-take.md](processing-a-take.md) | after a session: from files to a skeleton and the four numbers to write down per take |
| [comparing-pose-models.md](comparing-pose-models.md) | deciding between stage 1 detectors on real takes, and recording the decision |
| [desktop-tester.md](desktop-tester.md) | running a take through the pipeline from the desktop app, with a progress bar and an instant preview |
| [reviewing-design-decisions.md](reviewing-design-decisions.md) | reviewing what the design-decision detector found, from a laptop or a phone |
| [enable-claude-on-github.md](enable-claude-on-github.md) | repository owner: switching on the detector's automatic runs |

Writing a new one: say who it is for, what must be true before step 1, then numbered steps with the exact commands. Put reasons in the pipeline README or the decisions sheet, not here.
