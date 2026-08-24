# NOW — dikte Windows stability
Branch master -> origin/master. Tree clean except untracked graphify-out/.
.cloud: NOT tracked, NOT present locally -> task = add to .gitignore (currently missing it).

Wave goal (parallel, disjoint files):
  A installer:   install.ps1, uninstall.ps1, docs
  B no-console:  audio.py, filetranscribe.py, cleanup.py, assistant.py, hotkey.py, paste.py
  D download:    ggml.py, hub.py
Then (wave 2, sole owner of dikte.py) C save-crash: settings_ui.py, config.py, dikte.py
Then: fresh verifier -> tests -> commit -> push.

Avoid writing to a file owned by another in-flight agent.
