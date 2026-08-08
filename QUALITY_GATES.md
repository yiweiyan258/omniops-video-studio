# Video Studio Quality Gate

The public repository is self-contained. Run the complete release gate with:

```bash
python3 tools/run_quality_gate.py
```

The command performs the same checks locally and in GitHub Actions:

1. public repository boundary and high-confidence secret scan;
2. Python syntax validation for the product backend, tests, and tools;
3. clean npm dependency installation;
4. TypeScript type checking and Vite production build;
5. Rust/Tauri Cargo workspace metadata validation;
6. all 27 local-only Video Studio service, CLI, desktop, packaging, duration,
   paid-authorization, and external-write policy regression tests.

The quality gate does not call a paid image/video model and does not publish,
upload, or write to any external merchant platform.

Enable the versioned pre-push hook after cloning:

```bash
python3 tools/install_git_hooks.py
```
