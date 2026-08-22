# Aegis Workstation Tuning — Summary

**Date:** 2026-08-21 (host knobs); default model as of 2026-08-22 is Qwen2.5-Coder-7B-Instruct Q4_K_M.
**Machine:** Intel i5-9400F (6c/6t), 16GB RAM, NVIDIA GTX 1660 Ti, Kali Linux
**Context:** This machine runs a local LLM (llama.cpp / LM Studio) as part of the Aegis
AI workflow (100monkeys.ai). The snapshots below were taken while **Bonsai 27B** was loaded
(~5.8GB of 6GB VRAM). The deploy default is now **Qwen 7B Q4_K_M** (`lms load … --gpu max -c 4096`).
That GPU/RAM usage is expected — this round of tuning targeted system-level overhead *around*
the model, not the model itself.

## Changes made

| Change | Before | After | Why |
|---|---|---|---|
| SATA SSD (`sda`) I/O scheduler | `mq-deadline` | `none` | `mq-deadline` reorders/merges requests to reduce seek time on spinning disks; on an SSD there's no seek penalty, so it's pure CPU overhead with no benefit. `none` passes I/O straight to the device queue. |
| `vm.swappiness` | 60 (default) | 10 | With RAM under sustained pressure from the LLM workload, the default aggressively swaps out inactive pages. Lowering this makes the kernel favor keeping active processes (browser, terminal, aegis workflow) in RAM and reclaim page cache first, reducing swap-induced latency for foreground work. |

Both changes are persisted (sysctl config + udev rule) and survive reboot.

## Before / after snapshot

| Metric | Before | After |
|---|---|---|
| RAM used / free | 11Gi used, 498Mi free | 12Gi used, 503Mi free |
| Swap used | 6.6GB / 12GB | 5.9GB / 12GB |
| `vm.swappiness` | 60 | 10 |
| `sda` scheduler | `mq-deadline` | `none` |
| GPU util / VRAM | 47% / 5843MiB | 47% / 5856MiB |
| GPU temp | 68°C | 66°C |
| CPU governor | performance (all cores) | performance (all cores) |
| Load average (1m) | 2.40 | 2.80 |

## Notes for the record

- GPU/VRAM usage (~5.8GB of 6GB) and RAM usage from the local model are expected — this is the
  Aegis test workload doing its job, not a problem to fix.
- Swap was already at 6.6GB before this change; lowering swappiness prevents new aggressive
  swapping going forward but doesn't instantly reclaim what's already swapped out — that clears
  as memory pressure eases or on next reboot.
- Raw command output for both snapshots is saved alongside this file: `baseline_before.txt`,
  `baseline_after.txt`.
