# DECISIONS

- Parallel wave1 with disjoint file ownership to avoid write collisions.
- .cloud untouched in tree; only ensure gitignore. No index removal needed.
- Save crash root cause: unguarded conf.save() OSError escaping a PyQt slot -> process termination. Guarded with try/except OSError -> QMessageBox + early return.
- No-console: per-module _subprocess_kwargs() (small reuse over central helper) applied on Windows via CREATE_NO_WINDOW.
- Installer: per-user HKCU Apps&Features registration; interpreter resolution fixed to keep py/-3 as separate tokens.
