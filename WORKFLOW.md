# Recommended Workflow

1. `main` is the core product.
   This should always be the closest thing to “stable and releasable”.

2. Build features on short-lived branches.
   Use names like `feature/logging-fixes`, `feature/web-polish`, `feature/exe-packaging`.

3. Merge into `main` often.
   Commit regularly for backup/source control. Don’t wait for huge milestones to commit.

4. Start `.exe` builds before MVP is “finished”.
   Don’t wait until the very end. Packaging problems are easier to solve early.

5. When MVP is good enough, tag a release from `main`.
   Example: `v0.1.0-mvp`

6. Test from built `.exe` artifacts, not from the repo.
   That gives you real distribution-style testing.

7. Keep refining on feature branches, merge back to `main`, and build new `.exe` versions.
   Example tags: `v0.1.1`, `v0.1.2`

8. When client-specific work starts, branch from a stable tag or stable `main`.
   Example: `client/acme`

That gives you:
- one core product line
- one or more client variants
- separate `.exe` outputs per branch/tag

**Branch Strategy**

Use this structure:

- `main`
- `feature/*`
- `hotfix/*`
- `client/<client-name>` only when needed

That is simpler than forks and much easier to maintain.

My recommendation:
- Use `main` for shared product work
- Use `client/<name>` only for true client-specific behavior
- Keep branding/config differences out of core code as much as possible

Examples:
- Logo, app name, colors, default command sets: config/assets
- Security levels, restricted workflows, client-only logic: client module or feature flags
- Optional integrations like Gurux later: plugin or separate extension repo

**How The `.exe` Fits In**

The normal technical path is:

1. Keep developing in `.venv` editable mode.
2. Add a Windows build script and CI workflow.
3. Build `.exe` from a branch or tag.
4. Upload the binary as a GitHub Actions artifact or GitHub Release asset.
5. Test that binary.
6. Never commit built `.exe` files into git.

For packaging, I’d use:
- `PyInstaller` first
- Later, optionally an installer like Inno Setup

Practical recommendation:
- Start with a working one-folder build first
- Then move to one-file if you specifically want a single executable

One-file is possible, but one-folder is often easier while stabilizing packaging.

**Best Long-Term Setup**

For client variants, don’t make each branch a random pile of edits. Isolate them.

A good shape is:

- `src/serialhub/`
- `src/serialhub/assets/`
- `src/serialhub/client_profiles/default/`
- `src/serialhub/client_profiles/acme/`
- `src/serialhub/plugins/`

Then the build can choose a profile:
- default build -> `SerialHub.exe`
- acme build -> `SerialHub-Acme.exe`

That can be driven by:
- branch name
- env var
- build argument
- config file

So yes, different branches can produce different `.exe` files.

**What I Recommend For You Specifically**

1. Keep using the repo as the single source of truth.
2. Use `main` plus short-lived feature branches now.
3. Add `.exe` building soon, not only after MVP.
4. Tag releases for testing milestones.
5. Use `client/<name>` branches later instead of forks.
6. Move client branding/default commands into isolated config/assets early.
7. Only use a fork later if a client version becomes a permanently separate product.

The next concrete step is:
- add a Windows build script for `PyInstaller`
- add a GitHub Actions workflow that builds a downloadable `.exe` from `main` and `client/*` branches