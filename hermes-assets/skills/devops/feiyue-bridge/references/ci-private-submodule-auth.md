# CI Private Submodule Auth — GitHub Actions

## Problem
When a parent repo has private submodules, the default GITHUB_TOKEN can't clone them.
Error: `fatal: repository 'https://github.com/<org>/<repo>.git/' not found`

## Solution: sed PAT into .gitmodules BEFORE init

```yaml
steps:
  - uses: actions/checkout@v4
    with:
      submodules: false          # CRITICAL: don't clone submodules yet
  - name: Init submodules with PAT
    env:
      PAT: ${{ secrets.VOYAGERAI_PAT }}
    run: |
      # 1. Inject PAT into .gitmodules FIRST
      sed -i "s|https://github.com/<org>/<repo>.git|https://x-access-token:${PAT}@github.com/<org>/<repo>.git|g" .gitmodules
      # 2. THEN init (reads modified URLs into .git/config)
      git submodule init
      # 3. THEN update (clones using PAT-injected URLs)
      git submodule update --init --recursive --depth 1
```

## Key Order
```bash
# ❌ WRONG — init caches URL before sed takes effect
git submodule init
sed ... .gitmodules          # too late!
git submodule update         # still uses old URL

# ✅ RIGHT — sed modifies .gitmodules before init reads it
sed ... .gitmodules
git submodule init           # reads modified URL
git submodule update         # clones with PAT
```

## What DOESN'T work
- `token: ${{ secrets.PAT }}` in `actions/checkout@v4` — doesn't propagate to submodule clones
- `git config --global url."https://x-access-token:${PAT}@github.com/".insteadOf "https://github.com/"` — produces `https://-@github.com/` on git 2.54 (URL rewrite bug)
- `credential.helper store` — not picked up by submodule clone process in GHA runner
- `actions/checkout@v4` with `submodules: recursive` and custom token — GITHUB_TOKEN scope doesn't cover private repos in other repos

## Setup
1. Create classic PAT with `repo` scope: https://github.com/settings/tokens/new
2. Add as secret: `gh secret set VOYAGERAI_PAT --repo <org>/<ParentRepo> --body '<pat>'`
3. CI workflow references `${{ secrets.VOYAGERAI_PAT }}` in env block

## Notes
- Each job only needs to sed-rewrite the submodules it uses (saves time)
- The `.gitmodules` file is modified in the working tree only (not committed)
- Works with git 2.54 (GitHub runner default as of 2026)
