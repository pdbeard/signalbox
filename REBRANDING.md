# signalbox - Rebranding Complete! 🚦

## Summary

The project has been successfully rebranded from **script-monitor** to **signalbox**!

## What Changed

### Core Branding
- ✅ Project name: `signalbox`
- ✅ CLI description updated with railway signal box metaphor
- ✅ All documentation references updated
- ✅ systemd/cron export files now use `signalbox-` prefix

### Files Updated
- ✅ `main.py` - Module docstring and CLI group description
- ✅ `README.md` - Full rebrand with signal box metaphor explanation
- ✅ `config.yaml` - Header comment
- ✅ `documentation/CONFIG_GUIDE.md` - References
- ✅ `documentation/FILE_STRUCTURE.md` - Directory examples
- ✅ `documentation/WRITING_SCRIPTS.md` - New comprehensive guide (created)
- ✅ `test_all.sh` - Test suite header
- ✅ `setup.py` - Created for future PyPI distribution

### What Stayed the Same
- ✅ All command names unchanged (`list`, `run`, `run-group`, etc.)
- ✅ All arguments unchanged
- ✅ Configuration file structure unchanged
- ✅ All functionality preserved

## The Metaphor

**Railway Signal Box** = Control center that:
- **Controls switches** → Routes scripts to execution paths
- **Manages signals** → Start/stop scripts safely (green/red = success/failure)
- **Prevents conflicts** → Handles dependencies and interlocking
- **Monitors activity** → Centralized logging and status tracking

## Quick Test

```bash
# All commands work exactly as before
python main.py list
python main.py run hello
python main.py validate
```

## Next Steps

1. **Update repository name** (if on GitHub): `script-monitor` → `signalbox`
2. **Update git remote** (if applicable)
3. **Consider publishing** to PyPI as `signalbox`
4. **Add logo/icon** with signal box imagery (optional)

## Installation

With `setup.py` now in place, you can install as a package:

```bash
pip install -e .  # Development install
```

Then use as:
```bash
signalbox list
signalbox run backup
```

---

🚦 **signalbox - Control your scripts with precision and reliability**
