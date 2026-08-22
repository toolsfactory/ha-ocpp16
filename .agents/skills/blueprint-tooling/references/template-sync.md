# Template sync: background, recovery, and the exclusion list

Detail behind [`SKILL.md`](../SKILL.md)'s "Template sync" section — read this when a sync PR needs
troubleshooting or recovery, not for the everyday mechanism (that's already in `SKILL.md`).

## How it works

Every Monday at 07:00 UTC, [the workflow](../../../../.github/workflows/template-sync.yml) checks
whether the upstream template ([`jpawlowski/hacs.integration_blueprint`](https://github.com/jpawlowski/hacs.integration_blueprint))
has new commits. If it does, it opens a pull request with the diff against this repository, updating
an existing open sync PR in place (force-push + PR edit) rather than opening a new one each run.

## Prerequisites for workflow-file updates

Updating files under `.github/workflows/` requires extra GitHub permissions (`workflows: write`).
Without that permission, the workflow creates a temporary ignore file for that run and skips only
`.github/workflows/*` updates — everything else still syncs.

To include workflow-file updates, the target repository needs:

- **Settings → Actions → General → Workflow permissions** set to **Read and write permissions**
- **Allow GitHub Actions to create and approve pull requests** enabled
- A repository secret named `TEMPLATE_SYNC_TARGET_PAT`, scoped at least `contents: write`,
  `pull requests: write`, `workflows: write`, `metadata: read`

### Troubleshooting: workflows permission error

```text
refusing to allow a GitHub App to create or update workflow
'.github/workflows/<file>.yml' without 'workflows' permission
```

Means the run tried to update workflow files without a `workflows`-scoped token. Either configure
`TEMPLATE_SYNC_TARGET_PAT` as above, or accept that workflow-file updates keep being skipped — the
run summary notes when that happens, so it's visible why those changes are missing from the PR.

## How conflicts are handled

The workflow uses `-X theirs` when preparing the PR branch — **the template version always wins**
when both sides changed the same file. The PR is always clean and mergeable; there are no conflict
markers.

- File changed both locally and upstream → the PR diff shows your changes being replaced by the
  template version.
- File changed locally but not upstream → the PR contains nothing for that file; local changes are
  unaffected.

Review the diff before merging. If it would overwrite something worth keeping, close the PR and
apply the wanted changes manually instead.

## Modifying synced files locally

A synced file is only touched by the workflow if it changed upstream since the last sync — local-only
changes are never overwritten. When the same file changes on both sides, two strategies:

- **Exclude it permanently:** add it to [`.templatesyncignore`](../../../../.templatesyncignore) —
  the workflow then skips it entirely. Use this for a file fully owned locally (e.g.
  `requirements.txt`).
- **Handle conflicts case by case:** edit the file directly on the PR branch before merging — via the
  GitHub web UI (PR → _Files changed_ → `…` → _Edit file_) or `gh pr checkout <number>` locally.

**After an accidental merge (recovery):** restore a lost local change from the commit before the
merge:

```bash
git show HEAD~1:path/to/your-file.ext > path/to/your-file.ext
git commit -m "chore: restore local changes after template sync"
```

If the same file keeps causing conflicts every sync, add it to `.templatesyncignore` instead of
resolving the conflict repeatedly.

## Excluding files from sync

[`.templatesyncignore`](../../../../.templatesyncignore) uses `.gitignore` glob syntax; files it
lists are never touched by the sync PR, even when they changed upstream. Excluded by default:

| Path                                                                           | Reason                                                    |
| ------------------------------------------------------------------------------ | --------------------------------------------------------- |
| `custom_components/`                                                           | The integration's own code                                |
| `tests/`                                                                       | Test imports are tied to this project's domain            |
| `pyproject.toml`                                                               | Contains this project's domain in package metadata        |
| `.yamllint.yml`                                                                | Contains this project's domain in a configuration comment |
| `.pre-commit-config.yaml`                                                      | Contains this project's domain in file-match patterns     |
| `requirements.txt`                                                             | This integration's own PyPI dependencies                  |
| `.vscode/launch.json`, `.vscode/tasks.json`                                    | Contain this project's domain in debugger/task arguments  |
| `README.md`, `LICENSE`, etc.                                                   | Project-specific content                                  |
| `AGENTS.md`, `CLAUDE.md`                                                       | Domain-specific project instructions                      |
| `AI_POLICY.md`, `.github/pull_request_template.md`                             | Project-specific governance and contribution process      |
| `.github/CODEOWNERS`, `.github/FUNDING.yml`, `.github/COPILOT_CODING_AGENT.md` | Per-project GitHub settings                               |
| `config/`                                                                      | Local HA instance (credentials, test data)                |
| `docs/`                                                                        | This project's own documentation                          |
| `script/hooks/`, `.devcontainer/hooks/`                                        | Local hook scripts                                        |
| `.devcontainer/.env`                                                           | The pinned `HA_VERSION` and DevContainer settings         |
| `release-please-config.json`, `.release-please-manifest.json`                  | Release management                                        |
| `.github/workflows/template-sync.yml`                                          | The sync workflow itself                                  |
| `uv.lock`                                                                      | Pinned dependency lockfile                                |

## Opting out of template sync entirely

```bash
rm .github/workflows/template-sync.yml
rm .templatesyncignore
```

No workflow runs, no PRs, no noise. Upstream changes can still be pulled manually at any time by
comparing this repository against `jpawlowski/hacs.integration_blueprint`.
