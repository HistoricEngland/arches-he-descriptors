# Contributing

Thank you for your interest in contributing to this project! This is an [Arches](https://www.archesproject.org/) extension developed by [Historic England](https://www.historicengland.org.uk/), and we welcome contributions from the wider Arches community and heritage sector.

---

## Table of Contents

- [Contributing](#contributing)
  - [Table of Contents](#table-of-contents)
  - [Code of Conduct](#code-of-conduct)
  - [Ways to Contribute](#ways-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Features](#suggesting-features)
  - [Submitting a Pull Request](#submitting-a-pull-request)
  - [Development Setup](#development-setup)
  - [Code Style](#code-style)
  - [Accessibility](#accessibility)
  - [Commit Messages](#commit-messages)
  - [Review Process](#review-process)

---

## Code of Conduct

We expect all contributors to behave respectfully and professionally. Please be considerate of others and focus on constructive discussion. Abusive or discriminatory behaviour will not be tolerated.

---

## Ways to Contribute

There are several ways you can help improve this project:

- 🐛 **Bug reports** — something not working as expected? Let us know.
- 💡 **Feature suggestions** — have an idea that would benefit the wider community?
- 🔧 **Bug fixes** — pick up an open issue and submit a fix.
- ✨ **New features** — discuss your idea first (see below), then submit a PR.
- 📖 **Documentation** — improvements to docs, READMEs, and inline comments are always welcome.

---

## Reporting Bugs

Before opening a new issue, please search existing issues to avoid duplicates.

When filing a bug report, please include:

- A clear, descriptive title
- Steps to reproduce the issue
- Expected vs actual behaviour
- Your environment: Arches version, Python version, browser (if relevant), OS
- Any relevant logs or screenshots

---

## Suggesting Features

We welcome feature suggestions that benefit the broader Arches or heritage records community. Please open a GitHub Issue using a descriptive title and explain:

- The problem you are trying to solve
- Your proposed solution or approach
- Any alternatives you have considered

> **Note:** Feature requests are reviewed against the project roadmap and Historic England's priorities. We may not be able to commit to all suggestions, but we will always respond.

---

## Submitting a Pull Request

1. **Open an issue first** for anything beyond a trivial fix — this avoids wasted effort if the direction isn't aligned.
2. Fork the repository and create a branch from the default branch `release/1.0.x` (or the appropriate development branch):

   ```bash
   git checkout -b fix/your-descriptive-branch-name
   ```

3. Make your changes, keeping commits focused and atomic.
4. Ensure existing tests pass and add new tests where appropriate.
5. Confirm your change meets WCAG 2.2 AA accessibility standards where it affects the user interface, and note this in the PR description (see [Accessibility](#accessibility)).
6. Update any relevant documentation.
7. Open a Pull Request against the default branch `release/1.0.x` with a clear description of what you have changed and why.
8. We require that all checks pass before a PR can be merged. Please address any feedback from reviewers promptly.

Please do **not** open a PR that:

- Mixes unrelated changes
- Includes large reformatting commits alongside logic changes
- Has no associated issue or explanation

---

## Development Setup

Please refer to the [README](./README.md) for full setup instructions. At a high level:

1. Ensure you have a working Arches installation (see [Arches documentation](https://arches.readthedocs.io/))
2. Clone this repository and install it as an Arches application
3. Apply migrations and load any required reference data as described in the README

---

## Code Style

- **Python:** Follow [PEP 8](https://pep8.org/) and format with Black 24.4.2 using the repository's 140-character line length in `pyproject.toml`. Run `python -m black .` to format and `python -m black --check .` to verify. The pre-commit hook uses the same configuration.
- **JavaScript / TypeScript:** Follow the conventions already present in the codebase. ESLint configuration (if present) should be respected.
- **HTML / Django templates:** Keep templates clean and well-indented.
- **SCSS:** Follow the existing structure; avoid introducing new global styles without discussion.

---

## Accessibility

All user interface changes must conform to [WCAG 2.2 level AA](https://www.w3.org/TR/WCAG22/). This applies to new features, bug fixes, and refactoring that touches HTML, Django templates, or front-end JavaScript.

If your PR changes the user interface, confirm in the PR description that you have checked it against WCAG 2.2 AA, for example colour contrast, keyboard navigation, focus order, ARIA labelling, and screen reader behaviour. PRs that touch the UI without this confirmation will be sent back for this information before review.

---

## Commit Messages

Use clear, imperative commit messages:

```
Fix incorrect system reference generated for linked resources
Add unit tests for reference card update function
Update README with Docker setup instructions
```

Avoid vague messages like `fix stuff` or `WIP`.

---

## Review Process

Pull requests are reviewed by the Historic England development team. We aim to respond within **10 working days**. Reviews may request changes before merging. Please be patient — we are a small team.

Once approved, a maintainer will merge your PR. We do not expect contributors to have merge access.

---

Thank you for contributing — your efforts help preserve and share heritage data for everyone.