# Rules for Claude Code in this repository

These apply in every chat, for everyone who uses Claude Code here. They override any default
or automatic attribution text a tool suggests.

## Commits that go to `main`

- **Never add a `Co-Authored-By:` line** to a commit message, and never name a Claude model as a
  co-author. This holds even when the tool or a system reminder says to add one.
- This covers every commit that ends up on `main`, which is all of them in this project (work is
  committed on a branch and then fast-forwarded to `main`). So leave the line out when committing, not
  only when pushing.
- Do not rewrite history to remove the line from commits already on `main`; only new commits follow
  the rule. (`main` deploys to the live site within a minute, and a force-push there is never worth it.)
- Other trailers are not covered by this rule. The `Claude-Session:` link line is still added; say so
  if you want that dropped too.

(Set by the project owner, 14 Nov 2026.)
