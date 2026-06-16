# Two-Hermes GitHub Sync Strategy

Purpose: keep Simon's two Hermes instances — Windows 11 server and MacBook — learning from the same Feiyue evolution history without sharing secrets or fragile local state.

## Design choice

Use GitHub as the canonical synchronization layer, with three repositories/scopes:

1. **Project repos** such as `VOYAGERAI` and `LexProof`
   - Store project-specific `.hermes/` evidence when lightweight and non-secret.
   - Store docs, CI, overlays, deployment scripts, and parent-owned integration code.

2. **Feiyue repo** `sinonchum/Feiyue`
   - Store reusable Feiyue doctrine, tools, bridge scripts, and Hermès skills.
   - This repo is the shared “learning kernel” between the Windows and MacBook Hermes instances.

3. **Machine-local Hermes home** `~/.hermes` / `%LOCALAPPDATA%/hermes`
   - Store secrets, auth tokens, gateway state, raw sessions, local cron state, local memory.
   - Do not sync this wholesale through GitHub.

## What should sync

Commit these to GitHub:

- `docs/real-project-learnings-*.md`
- `docs/two-hermes-github-sync.md`
- `tools/hermes-bridge/feiyue-bridge.py`
- `hermes-assets/skills/devops/feiyue-bridge/`
- project `.hermes/` artifacts that are concise, non-secret, and useful as evidence
- reusable scripts and CI patterns

Do not commit:

- API keys, OAuth tokens, `.env`, `auth.json`
- raw Telegram/Discord request dumps
- full Hermes session databases
- heavy screenshots/videos unless explicitly needed as evidence
- machine-specific cron state unless intentionally shared

## Sync workflow before a major task

On either machine:

```bash
cd ~/work/Feiyue  # or wherever the clone lives
git pull --ff-only
python tools/hermes-bridge/install_local_assets.py --install-skill --install-bridge
```

Then work inside the target project:

```bash
cd ~/work/VOYAGERAI
python ~/AppData/Local/hermes/scripts/feiyue-bridge.py --action overview --project-root .
# On macOS, path is usually ~/.hermes/scripts/feiyue-bridge.py
```

After finishing:

```bash
# target project: commit project docs/evidence/code
git status --short
git add <changed-files>
git commit -m "feat: ..."
git push

# Feiyue repo: commit reusable lessons/skills/scripts
git -C ~/work/Feiyue status --short
git -C ~/work/Feiyue add docs hermes-assets tools
git -C ~/work/Feiyue commit -m "docs: capture real-project Feiyue evolution lessons"
git -C ~/work/Feiyue push
```

## Sync workflow after a task

Every completed real project phase should answer two questions:

1. Did the target repo learn something project-specific?  
   If yes, write project `.hermes/` evidence or docs and push the target repo.

2. Did Feiyue/Hermes learn a reusable procedure?  
   If yes, update `sinonchum/Feiyue` under `docs/`, `tools/`, or `hermes-assets/skills/` and push it.

## Conflict policy

When Windows and MacBook both evolve Feiyue:

1. Pull before starting.
2. Prefer additive docs/skills changes over rewriting large files.
3. If both edited the same skill, preserve both lessons and add a “pitfall” section rather than choosing one blindly.
4. Run the verification command before pushing.
5. Push with normal Git history; avoid force-push on `main`.

## Recommended local install script

`tools/hermes-bridge/install_local_assets.py` installs the repo's canonical bridge and skill into the active local Hermes home.

- Windows default Hermes home: `%LOCALAPPDATA%/hermes`
- macOS/Linux default Hermes home: `~/.hermes`
- Override with `HERMES_HOME=/path/to/home`

This gives both Hermes instances the same Feiyue bridge behavior while still letting each machine keep private credentials and memory local.

## Future upgrade

Add a lightweight scheduled job on both machines:

- Pull `sinonchum/Feiyue` every morning.
- Run `install_local_assets.py`.
- Report if local skills differ from the canonical GitHub skill.

This creates a controlled self-evolution channel: Feiyue knowledge moves through reviewed Git commits, not hidden local memory.
