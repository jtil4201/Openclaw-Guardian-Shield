# Guardian Shield — Build Spec
*Created: 2026-03-03*

## What Is It
A free ClawhHub skill that protects OpenClaw agents from prompt injection attacks. Runs entirely local — no API calls, no cloud dependency. Upgradeable to Home tier ($10/mo or $99/yr) via license key.

## Product Tiers

| Tier | Price | Patterns | Model | Document Scan | Updates |
|------|-------|----------|-------|---------------|---------|
| Free (ClawhHub) | $0 | 80 regex | Ward (ONNX) | Text only | Manual (new skill version) |
| Home Monthly | $10/mo | 258 regex | Ward (ONNX) | PDF/HTML/docs | Auto via license |
| Home Yearly | $99/yr | 258 regex | Ward (ONNX) | PDF/HTML/docs | Auto via license |
| Basic API | $19.99/mo | Full V1 | Lieutenant | Via API | Always current |
| Pro API | $49.99/mo | Full V1+V2 | Spectre + Arc | Via API | Always current |
| Enterprise | Custom | Everything | Everything | Everything | Custom training |

## Architecture

```
User message / document / web fetch
        ↓
  [Text Extraction] (PDF, HTML, plain text)
        ↓
  [Chunking] (~500-1000 chars per chunk)
        ↓
  [V1 Regex Scan] → 80 patterns (free) or 258 (Home)
        ↓ (if regex flags something OR always in thorough mode)
  [Ward ML Scan] → ONNX model, TF-IDF + logistic regression
        ↓
  [Score + Classify]
        ↓
  Results: threat (bool), score (0-100), category, details
```

## Model: Ward

### Training Approach
- **Architecture:** TF-IDF vectorizer + Logistic Regression (or small neural net)
- **Export:** ONNX format (~2-10MB)
- **Training data:** Same dataset used for Spectre (attacks + benign)
- **Target:** >95% accuracy, <5ms inference on CPU
- **Runtime:** `onnxruntime` (CPU default), `onnxruntime-gpu` optional
- **GPU support:** Auto-detect CUDA → DirectML → CPU fallback

### GPU Detection (scan.py)
```python
import onnxruntime as ort

def get_providers():
    available = ort.get_available_providers()
    # Prefer CUDA > DirectML > CPU
    preferred = []
    if 'CUDAExecutionProvider' in available:
        preferred.append('CUDAExecutionProvider')
    if 'DmlExecutionProvider' in available:
        preferred.append('DmlExecutionProvider')
    preferred.append('CPUExecutionProvider')
    return preferred
```

## Pattern Selection (80 from 258)

Curate from Lieutenant's pattern library (`/home/guardian/app/v2/lieutenant.py` on VPS):
- 15 direct override / instruction injection
- 10 system prompt extraction
- 10 role manipulation / jailbreak
- 10 data exfiltration
- 10 encoding bypass (base64, unicode)
- 10 authority claims / social engineering
- 10 context confusion / indirect injection
- 5 multilingual basics (DE/FR/ES)

Selection criteria: highest hit rate in Volt red team tests + production near-miss logs.

## File Structure

```
guardian-shield/
├── SKILL.md              ← ClawhHub skill description + agent instructions
├── README.md             ← Full docs, setup, usage
├── scripts/
│   ├── scan.py           ← Main scanner (CLI + importable by agent)
│   ├── patterns.py       ← Regex patterns (80 free, 258 unlocked with key)
│   ├── ward.py           ← ONNX model inference wrapper
│   ├── extract.py        ← Text extraction (PDF, HTML, plain text)
│   └── license.py        ← License key validation
├── models/
│   └── ward.onnx         ← Tiny ML model
├── config.json           ← Settings + license key slot
├── LICENSE               ← Source-available / BSL
└── .gitignore
```

## SKILL.md Behavior

The SKILL.md tells the OpenClaw agent to:
1. Auto-scan incoming messages from untrusted sources (group chats, web fetches, file reads)
2. On threat detection: warn the user, log the attempt, optionally block
3. Show scan results in a compact format:
```
🛡️ Guardian Shield — 1 threat detected
   Source: web_fetch (example.com)
   Category: instruction_override
   Score: 87/100
   Action: blocked

   ⚠️ Want ML-powered scanning? Upgrade to Home ($10/mo)
   → https://fallenangelsystems.com/shield
```
4. The upsell message only shows when the free tier finds something ambiguous (score 40-70 range)
5. Clear threats (score >70) just get blocked, no upsell nag

## Config File (config.json)

```json
{
    "license_key": "",
    "scan_mode": "auto",
    "action_on_threat": "warn",
    "log_file": "shield-log.json",
    "min_score_to_block": 70,
    "min_score_to_warn": 40,
    "scan_web_fetches": true,
    "scan_file_reads": true,
    "scan_group_messages": true,
    "gpu_enabled": "auto"
}
```

## License Key System

1. User buys Home tier → Stripe payment
2. Webhook fires → generates license key (format: `fsg_home_<uuid>`)
3. Key emailed to user
4. User adds to config.json
5. On next scan, `license.py` validates key:
   - POST to `https://api.fallenangelsystems.com/v2/license/validate`
   - Sends: key + machine hash (privacy-safe, no PII)
   - Receives: valid (bool) + tier + expiry
   - Caches result locally for 30 days
6. If valid: unlocks full 258 patterns + document extraction features
7. If expired/invalid: falls back to free tier gracefully

## Dependencies

### Required (Free Tier)
- `onnxruntime` — ML inference (CPU)
- Python 3.10+ (stdlib only for everything else)

### Optional
- `onnxruntime-gpu` — GPU acceleration (CUDA)
- `onnxruntime-directml` — Windows iGPU support
- `PyPDF2` — PDF text extraction (Home tier)
- `beautifulsoup4` — HTML extraction (Home tier)

## Training Ward (Steps)

1. SSH to Josh's PC (WSL): `ssh joshpc-wsl`
2. Use existing Spectre training data: `/mnt/josh/fas-guardian-v2/data/`
3. Train TF-IDF + LogReg pipeline in sklearn
4. Export to ONNX using `skl2onnx`
5. Test accuracy against Volt attack suite
6. If >95% accuracy → ship it
7. Copy ward.onnx to guardian-shield/models/

## Upsell Strategy

- Free tier works well → builds trust
- Upsell only appears on ambiguous detections (score 40-70)
- Never nags on clear threats or clear safe messages
- Monthly upsell shown max 3x per day (tracked in config)
- Message: factual, not pushy — "Free tier uses 80 patterns. Home unlocks 258 + document scanning."
- Link to pricing page, not direct Stripe (let them compare)

## Build Order

1. [ ] Curate 80 patterns from Lieutenant
2. [ ] Train Ward model (Josh's PC GPU)
3. [ ] Build scan.py (regex + ONNX inference)
4. [ ] Build extract.py (text, PDF, HTML)
5. [ ] Build license.py (key validation + caching)
6. [ ] Build patterns.py (free + gated patterns)
7. [ ] Write SKILL.md (agent behavior instructions)
8. [ ] Write README.md (user docs)
9. [ ] Test with Volt attacks
10. [ ] Publish to ClawhHub
11. [ ] Create Stripe products for Home tier
12. [ ] Build license validation endpoint on VPS

## Content to Create After Launch
- Blog post: "Protect Your OpenClaw Agent from Prompt Injection — Free"
- Red team results: "We attacked our own agent. Here's what happened."
- Demo video showing Shield catching an attack in real-time
