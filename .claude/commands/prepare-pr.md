Prepare, commit, and open a pull request for the current branch. Do the following in order:

1. Run `git status`, `git diff --cached`, `git log main..HEAD --oneline`, and `git diff main..HEAD` to understand what is staged and what the full branch diff looks like.

2. Craft a conventional commit message for the staged changes:
   - Format: `<type>(<scope>): <short description>` (under 72 chars)
   - Types: feat, fix, chore, refactor, docs, style, test
   - Focus on WHY and WHAT changed logically, not which files were touched

3. Commit the staged changes with that message.

4. Write the PR description — short, human-readable prose (2–4 sentences max). Explain what the change does and why, as if telling a teammate. No bullet lists of files. Capture intent and logic, not implementation details.

5. Push the branch and create the PR using `gh pr create` with the prose description.
