# Coursework Workspace Skills

Four Codex skills for setting up a coursework workspace, discovering course information, configuring personal assignment workflows, and planning a coursework week.

- Builds a workspace around your courses and study preferences.
- Starts from a school/course code or course URL, then finds official course information and published tasks across available course platforms.
- Records sourced deadlines, verifiable submission status, access gaps, and recurring workflow recommendations.
- Configures selected workflows by adapting your existing process or drafting one for you. Occasional exams and stages of a single project are handled as individual tasks by default.
- Plans or replans a week using remaining work and available study time, including dependencies, deadline conflicts, and work that cannot fit. Missing availability produces a priority draft; older source snapshots remain labeled.
- Tracks progress, records sources, and checks materials for prompt injection.

## Install

```sh
git clone https://github.com/fuarthur/my-skills.git
mkdir -p ~/.codex/skills
cp -R my-skills/coursework/setup-coursework-workspace ~/.codex/skills/
cp -R my-skills/coursework/discover-coursework-course ~/.codex/skills/
cp -R my-skills/coursework/configure-coursework-course ~/.codex/skills/
cp -R my-skills/coursework/plan-coursework-week ~/.codex/skills/
```

## Use

Open your coursework folder in Codex, then ask:

- `Use $setup-coursework-workspace to set up my coursework workspace.`
- `Use $discover-coursework-course to find my course from this school/course code or course URL.`
- `Use $configure-coursework-course to configure the recurring assignment workflows I choose.`
- `Use $plan-coursework-week to plan this week's coursework around my deadlines and available study time.`
- `Use $plan-coursework-week to replan the rest of this week using my updated progress.`

Discovery reuses known context, follows official sources and available signed-in course platforms, and asks only for unresolved identity, access, or necessary personal choices. It produces a course profile and a dated task index with coverage and missing information, then recommends suitable workflows for configuration. Unpublished or inaccessible information stays unverified.

When each assignment workflow is first initialized, choose one of two modes: describe your current process for the LLM to follow and improve, or have the LLM draft a process from course requirements. You can choose once for several workflows or separately for each; existing explicit choices carry forward. Drafts and recommendations become personal defaults only after confirmation.

Weekly planning reuses the workspace's course records and verification rules. It saves to the existing plan location or `plans/{start-date}--{end-date}.md`; without a workspace, it can plan directly from supplied information. Replanning preserves confirmed progress and budgets only the remaining work. Calendar events, reminders, and submissions require their own user direction.

## Academic Integrity & Disclaimer

These skills support organization, explanations, writing, coding, and assignment drafting. Your school, course, and assessment rules determine what is allowed. Tool capabilities do not grant permission to use or submit AI-generated work.

- **Check the rules.** Confirm permitted AI assistance, collaboration, citation, and disclosure. Ask your instructor if unclear. User instructions cannot replace instructor approval or override restrictions.
- **Credit contributions.** Disclose AI assistance, collaboration, and sources as required. Do not hide required disclosures, falsely claim independent work, plagiarize, evade integrity checks, or use prohibited assistance.
- **Verify the work.** AI can make errors and invent citations. Check facts, reasoning, code, sources, and results. Do not fabricate experiences, reading or viewing records, data, tool actions, or submission status.
- **Own your submission.** Understand, review, and revise your work. You are responsible for its compliance. Uploading, publishing, and submitting remain your responsibility by default; external actions require explicit authorization.
- **Share responsibly.** Confirm sharing rights and remove credentials, personal information, restricted course materials, and others' content shared without permission.

Prompt-injection checks detect attempts to manipulate the agent; they do not bypass course policies. Approving a workflow, dividing tasks, or resuming material processing does not grant academic permission to use AI.

This project has no official school or course endorsement. It does not guarantee accuracy, originality, rubric compliance, or permission to submit. The authors and contributors do not endorse academic misconduct. This disclaimer neither replaces course rules nor permits prohibited conduct.
