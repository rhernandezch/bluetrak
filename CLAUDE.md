
## General

- Do NOT proceed directly to implement things, especially when planning.
- Ask me what do I want to do:
  - Write a plan to a file?
  - Proceed to implement the changes?
  - Simply discuss and read the plan?

## Version control

### Branch workflow

- NEVER commit directly to `main`.
- Use a simplified version of Gitflow for development:
  - `main` is evergreen and has the latest and greatest.
  - `feat/XX` for features.
  - `fix/XX` for bug fixes.
  - `chore/XX` for chore-like changes, most of these should be dep upgrades or vulnerability patching.
- Verify current branch with `git branch --show-current` before every commit.
- Create a branch for each big change. If in doubt, check with me.
- Always rebase from `main` before creating a branch or opening a PR.
- Create multiple commits instead of a single commit with all changes. Group them based on functional units of work.
- Follow the [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/#specification) spec.

### Code review

- All changes must go through a PR, even small fixes like lint/typecheck corrections.
- Always open PRs as drafts. I will take care of marking the PR as ready for review.
- If a PR is already open, update the PR description every time a commit is pushed.

## Settings File Safety

- Before editing `.claude/settings.local.json` or any config file, ALWAYS read the full existing file first and preserve all existing keys.
- Never blindly overwrite settings files — merge changes into existing content.

## Golang

- Follow the Go Proverbs: https://go-proverbs.github.io/

## Python

- When working with Python repositories check the existence of a `.venv/bin` directory inside the repo.
- If it exists, use `{repo}/.venv/bin/python` as executable instead of the "naked" `python` command.
- Likewise use `{repo}/.venv/bin/pip` instead of `pip`.

## Development process

- Interview me in detail using the AskUserQuestion tool for any needed design decisions or
missing information.
- For a greenfield project, create a Makefile with the most used and helpful commands.
- If there's already a Makefile, add commands when they're helpful.

## PR conventions

- Use a simplified version of Gitflow for development:
  - `main` is evergreen and has the latest and greatest.
  - `feat/XX` for features.
  - `fix/XX` for bug fixes.
  - `chore/XX` for chore-like changes, most of these should be dep upgrades or vulnerability patching.
- Create a branch for each session, no matter how small. Commit after each step instead of one big change.
- Always rebase from `main` before opening a PR.
- Follow the [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/#specification) spec.

## Testing

- Run integration tests before opening a PR.
- Do not open a PR if unit or integration tests are failing.
