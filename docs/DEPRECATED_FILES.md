# Deprecated Files - Safe to Remove

**Date:** January 27, 2026  
**Version:** 1.1.0

This document lists files that are no longer needed and can be safely deleted.

---

## Files to Remove

### 1. `scripts/cleanup.sh` (OLD)

**Reason:** Replaced by `scripts/cleanup-all.sh`

**Differences:**
| Feature | cleanup.sh (OLD) | cleanup-all.sh (NEW) |
|---------|------------------|----------------------|
| Dry-run mode | ❌ | ✅ `--dry-run` |
| Force mode | ❌ | ✅ `--force` |
| Keep options | ❌ | ✅ `--keep-cluster`, `--keep-image` |
| Progress display | Basic | Detailed with colors |
| Docker cleanup | Minimal | Comprehensive |
| Labels used | Old (`app=ttg`) | New (`app.kubernetes.io/*`) |

**Safe to delete:** ✅ Yes

```bash
rm scripts/cleanup.sh
```

---

### 2. `src/utils.py` (UNUSED)

**Reason:** Functions are not imported by `worker.py`

The worker.py file has its own inline implementations of:

- `get_worker_config()` - now in `DistributedWorker.__init__()`
- `calculate_worker_range()` - now in `DistributedWorker.calculate_range()`

The utils.py file was created as a utility module but never integrated.

**Safe to delete:** ✅ Yes

```bash
rm src/utils.py
```

---

## Files to Keep (Despite Appearing Similar)

### `k8s/manifests/worker-job.yaml`

**Why keep:** Single-worker testing manifest

This is useful for debugging a single worker before running parallel jobs. Different from `parallel-jobs.yaml`:

- `completions: 1` (single worker)
- `parallelism: 1` (sequential)
- Useful for testing algorithm changes

**Recommendation:** Update labels to match new standard, but keep the file.

### `scripts/deploy.sh`

**Why keep:** Has useful features not in kubectl apply

- `--single` flag for single-worker testing
- `--workers N` flag for dynamic scaling
- `--params N` flag for parameter count
- Automatic cleanup of old jobs

**Recommendation:** Keep, optionally update to use new labels.

---

## Cleanup Command

To remove all deprecated files:

```bash
cd /home/xavierand_/Desktop/TTG

# Remove deprecated files
rm -f scripts/cleanup.sh
rm -f src/utils.py

# Verify removal
ls scripts/
ls src/
```

---

## Post-Cleanup Project Structure

After removing deprecated files:

```
TTG/
├── src/
│   ├── worker.py             # Main worker ✅
│   └── logging_config.py     # Logging ✅
│
├── docker/
│   └── Dockerfile            # Build ✅
│
├── k8s/
│   ├── manifests/
│   │   ├── parallel-jobs.yaml    # Main deployment ✅
│   │   └── worker-job.yaml       # Single-worker testing ✅
│   ├── local/
│   │   ├── kind-config.yaml      # Kind config ✅
│   │   └── setup-local.sh        # Setup ✅
│   └── azure/
│       └── setup-aks.sh          # Azure (future) ✅
│
├── scripts/
│   ├── build.sh              # Build ✅
│   ├── cleanup-all.sh        # Cleanup ✅
│   ├── list-resources.sh     # List resources ✅
│   ├── deploy.sh             # Deploy helper ✅
│   ├── run-local.sh          # Local testing ✅
│   └── setup-venv.sh         # Python venv ✅
│
├── docs/                     # All documentation ✅
├── SUPERVISOR_REPORT.md      # Supervisor report ✅
├── README.md                 # Main readme ✅
├── requirements.txt          # Dependencies ✅
├── .dockerignore             # Docker ignore ✅
└── .gitignore                # Git ignore ✅
```

Files removed: 2  
Total files remaining: Well-organized and documented ✅
