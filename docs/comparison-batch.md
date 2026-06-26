# Multi-agent vs single-agent — batch over hard designs

_5/5 designs measured live (qwen); coverage = concern surfaced as engineering work, scored by the deterministic 12-point rubric._

| Design | Multi-agent | Single-agent | Δ | Mode |
| --- | :---: | :---: | :---: | :---: |
| Motor+safety | 11/12 | 9/12 | +2 | qwen |
| Precision analog | 11/12 | 9/12 | +2 | qwen |
| Battery IoT | 12/12 | 8/12 | +4 | qwen |
| Medical wearable | 12/12 | 7/12 | +5 | qwen |
| Industrial gateway | 12/12 | 9/12 | +3 | qwen |
| **Average (live)** | **11.6/12** | **8.4/12** | **+3.2** | |

## What the single agent most often missed (live runs)

- **5×** Reverse-polarity protection
- **4×** Overcurrent / fuse protection
- **3×** Docs, assumptions, explicit uncertainty
- **2×** Surge/ESD protection on power input
- **2×** Clock source
- **1×** Decoupling / filtering
- **1×** Test points / status indication
