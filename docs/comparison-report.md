# Multi-agent vs single-agent comparison

**Request:** A 24V industrial sensor board with an STM32, USB-C for configuration, an RS485 fieldbus interface and status LEDs.

**Mode:** qwen

**Multi-agent: 12/12 concerns surfaced (4 agent calls).**
**Single-agent: 11/12 concerns surfaced (1 call).**
**Difference: +1 concerns (multi-agent ahead).**

_Coverage = the concern was surfaced as engineering work (block / TODO / assumption / review item), not a placed component._

| Engineering concern | Multi-agent | Single-agent |
| --- | :---: | :---: |
| Surge/ESD protection on power input | ✅ | ✅ |
| Reverse-polarity protection | ✅ | ✅ |
| Overcurrent / fuse protection | ✅ | ✅ |
| Defined power rails / domains | ✅ | ✅ |
| Decoupling / filtering | ✅ | ✅ |
| Debug / programming access | ✅ | ✅ |
| Test points / status indication | ✅ | ✅ |
| Reset circuit | ✅ | ✅ |
| Clock source | ✅ | ✅ |
| Interface isolation / termination | ✅ | ✅ |
| External connectors identified | ✅ | ✅ |
| Docs, assumptions, explicit uncertainty | ✅ | — |
