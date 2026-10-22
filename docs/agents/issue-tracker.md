# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body-file <path>`. For multi-line bodies, write the exact text to a temporary file and pass it with `--body-file`.
- **Read an issue**: `gh issue view <number> --comments`, also fetching labels; then `gh issue view <number> --json subIssues,subIssuesSummary,blockedBy,parent,assignees,state`. Apply the Task graph rules below.
- **Body vs comments**: when a ticket's body and its comments conflict, the comments take precedence. Follow the comment, and state the discrepancy when it matters.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

### Task graph

- **Source of truth**: use native sub-issues and blocked-by relationships. Use body task lists or `Blocked by:` lines only when native APIs are unavailable, and explicitly label that fallback.
- **Completeness**: require `subIssues.totalCount == len(subIssues.nodes)` and `blockedBy.totalCount == len(blockedBy.nodes)` for each issue read. A count mismatch, unsupported field, or failed command makes the affected relationships **unknown**, never "no children" or "no blockers". Resolve incomplete results with paginated queries before treating them as complete; label any body fallback separately from the unknown native result.
- **Dependencies**: reconstruct the graph from all `blockedBy.nodes`, including closed blockers. REST `issue_dependencies_summary.blocked_by` counts only open blockers; `total_blocked_by` counts all blockers.
- **Current frontier**: consider only open issues with no assignee and all blockers closed, after verifying complete relationships. Closed issues remain historical graph members, not current work; unknown relationships cannot establish that an issue is claimable.
- **Conflicts and cycles**: report contradictions between the body and native relationships, and report dependency cycles; leave relationships unchanged. Reading the graph is read-only; claiming, closing, or assigning issues requires explicit task or workflow authorization.

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either: resolve with `gh pr view 42` and fall back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments` and `gh issue view <number> --json subIssues,subIssuesSummary,blockedBy,parent,assignees,state`; apply the Task graph rules in Conventions.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: apply the Task graph rules in Conventions to the map and its children; select the first issue in map order from the verified current frontier.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
