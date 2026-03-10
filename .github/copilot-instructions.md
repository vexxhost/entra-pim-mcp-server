# Agent Instructions

## Git Commits

- Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification for all commit messages.
- Use the format: `<type>(<scope>): <description>` (e.g., `feat(auth): add token refresh`, `fix(activate): resolve accessId lookup`).
- Common types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`, `style`.
- Breaking changes must include `!` after the type/scope (e.g., `feat!: drop Node 16 support`) or a `BREAKING CHANGE:` footer.
- This is required for release-please to correctly determine version bumps.
