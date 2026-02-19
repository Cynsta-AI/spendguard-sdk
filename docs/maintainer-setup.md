# Maintainer Setup

## Required Repository Secret

- `PYPI_API_TOKEN`

Set with GitHub CLI:

```bash
gh secret set PYPI_API_TOKEN --repo cynsta/spendguard-sdk
```

## Release Flow

1. Ensure `main` is green.
2. Push a tag matching `spendguard-cli-v*`:

```bash
git tag spendguard-cli-v0.1.0
git push origin spendguard-cli-v0.1.0
```

3. Verify workflow `publish-spendguard-cli` succeeds.

## Required Branch Policy

`main` should require:

- Pull request review (1 approval)
- Passing status check: `tests`
