## Documentation

- Persist all prompts in `docs/PROMPTS.md`.
- Persist all plans, in separate session docs sequentially, in `docs/plans/XX_PLAN.md`.
- Persist all decisions, in separate session docs sequentially, in `docs/decisions/XX_DECISIONS.md`.

## Development process

- Interview me in detail using the AskUserQuestion tool for any needed design decisions or
missing information.
- Create a MAKEFILE with the most used and helpful commands.

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
