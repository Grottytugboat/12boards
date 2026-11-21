# Project instructions

<!-- sonder-repository-context:start -->
## Repository context

- Read `PROJECT.md` for the verified scope of `Grottytugboat/12boards` and `.sonder/project.json` for its sourced context record.
- This repository maps to Conatus project `twelve-board-store`. Repository-specific scope matters when a brand has more than one repository.
- Relevant private business context is in [Grottytugboat/sonder-knowledge](https://github.com/Grottytugboat/sonder-knowledge). Retrieve it through an authenticated connection only when needed for the authorised task.
- Keep private task details, correspondence, financial terms, credentials and unpublished decisions out of these files and deployable assets. Use the private task source linked from `PROJECT.md`.
- Follow existing repository and directory instructions. A context record does not expand task, deployment or publication authority.
<!-- sonder-repository-context:end -->


<!-- sonder-project-memory:start -->
## Shared project memory

Use `PROJECT.md` for the current handoff and `.sonder/project.json` for its small
machine-readable summary. Read them before substantive work, together with the
applicable repository instructions. This section adds no new authority to merge,
deploy, message people, spend money or change access.

- Tim and Ying's existing task Page owns live priorities and assignments:
  https://chatgpt.com/space/page_1ccdd86738d08191b5785f134dd12faf.
  Do not recreate completed/removed tasks from old notes or turn this record into
  another backlog. Use a project's existing execution system when it has one.
- This repository owns implementation, validation and deployment evidence. Read
  the relevant source before making a current claim. A commit is not proof of a
  working preview, production deployment, payment or business outcome.
- `Grottytugboat/sonder-knowledge` owns shared business context and durable
  decisions. Read only the relevant, accessible files; do not claim private
  conversation memory or a provider connection that has not been established.
- After each substantive code change or implementation commit, update the handoff
  and semantic summary **when the meaning changed**, in the same work/commit when
  practical: what changed, what was actually checked, the next bounded action,
  any exact decision needed from Tim, and what is ready for review. Use null or
  `unknown` where evidence is absent. Mark a suggested next action as suggested.
- Keep the stable `projectId` when the repository or project is renamed. Preserve
  other people's notes and existing instructions. Never replace all of AGENTS.md
  just to update this managed section.
- For new semantic claims, record a UTC `updatedAt`, the actual `updatedBy` actor,
  and evidence links with their checked date. Link the task, PR, source document,
  test report or deployed result that supports the scope of the claim. Do not
  invent a future commit SHA: the containing commit is linked by Git/activity.
- Run `python3 .sonder/memory.py validate`. This checks structure and identity,
  not the truth of the claims. Report what remains unverified.
- Do not hand-edit `.sonder/activity.json`. Automation owns that file and records
  literal Git metadata only. It does not update status, priorities, next actions,
  `needsTim`, `readyForReview`, manual facts or personal notes.
- Avoid heartbeat edits: no fresh timestamp, duplicate handoff or no-op commit
  simply because an agent opened the repository or a scheduled review ran. A
  generated activity-only commit is not new work to summarise or follow up.
- Keep credentials, raw private chats, unrelated personal details and duplicated
  business documents out of these records. Link the existing authorised sources.

One job has one accountable owner. Other agents may review a bounded scope; they
must follow this repository's existing branch/worktree rules and preserve
concurrent edits. Synchronisation does not create cross-provider chat memory.
<!-- sonder-project-memory:end -->
