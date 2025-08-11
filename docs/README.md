# Project Docs (Mirror)
This folder mirrors your authoritative project docs that you manage in ChatGPT. Keep these in sync manually or on a cadence.

## Recommended files to mirror here
- `CALIBRATION_GUIDE.md`
- `HARDWARE_MAP.md`
- `TROUBLESHOOTING.md`
- `SERVICE_SETUP.md`
- `CHANGELOG.md`
- `DESIGN_DECISIONS.md`

> Tip: When you update any doc in ChatGPT, export the updated `.md` and overwrite the matching file here in `docs/`, then commit and push.

## Sync Checklist
- [ ] After code changes, update `CHANGELOG.md` in ChatGPT (and mirror here).  
- [ ] Re‑run quick post‑change tests on the Pi.  
- [ ] Verify GPIO pins and sensor IDs in `HARDWARE_MAP.md` are still correct.  
- [ ] Confirm calibration window (120 minutes) noted in `CALIBRATION_GUIDE.md`.
