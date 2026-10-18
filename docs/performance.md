# Performance validation - 2026-10-17

Baseline: `f27617a325ecee8ffaf8c9b014b847817cf3f782`. Python 3.13.5, pygame 2.6.1,
SDL dummy, SSE smoothscale. Three independent processes per variant, run serially
in alternating order; 300 frames per metric per process, fixed random seed 42.
The combat sample uses La Guerrera, three enemies and six cards. Total combat
measurements include the hovered card and viewport presentation. `dt` is 1/60 s;
there is no FPS limiter in this CPU benchmark.

## Changes retained

- Hero sheets/clips are shared across scenes through bounded LRU caches. Active
  loaders retain local clip references to avoid eviction stalls and preserve the
  original fast lookup path. Only idle clips at 96/192 px are prewarmed.
- Native-size presentation skips scaling. Other sizes reuse the destination
  surface and retain the original smoothscale filter. Black bars, including
  one-pixel remainders at odd window sizes, retain the original pixels.
- No artwork, animation timing, combat rules, card effects or enemy assets changed.

## CPU measurements

Medians below are the median of the three run medians. The final column is the
median of the three p95 values. Lower is better; values are milliseconds.

| Work | Before median | After median | Reduction | p95 before / after |
|---|---:|---:|---:|---:|
| Presentation 720p | 1.531 | 0.131 | 91.5% | 2.496 / 0.307 |
| Presentation 1080p | 8.169 | 5.937 | 27.3% | 10.326 / 7.443 |
| Presentation 1440p | 14.046 | 8.923 | 36.5% | 16.711 / 10.734 |
| Combat + hover + presentation 720p | 5.250 | 3.978 | 24.2% | 7.551 / 5.805 |
| Combat + hover + presentation 1080p | 11.724 | 9.466 | 19.3% | 14.364 / 11.757 |
| Combat + hover + presentation 1440p | 17.688 | 12.662 | 28.4% | 21.859 / 15.882 |

| One-time work | Before median ms | After median ms |
|---|---:|---:|
| Hero reused by a new scene | 194.436 | 0.013 |
| First menu draw | 708.610 | 56.296 |
| First character selection draw | 124.592 | 10.633 |
| First combat draw | 253.379 | 50.618 |
| Startup prewarm | 288.838 | 1058.818 |

Prewarm plus first menu draw: 997.4 ->
1115.1 ms. Prewarming moves decoding before
the interactive loop; it does not eliminate decoding, and preparing selection
assets adds some launch time. The improvement is fewer stalls after launch.

At 1440p, total combat frames exceeding the 60 FPS CPU budget (16.67 ms) fell
from 701/900 to 46/900. This is not a claim of locked 60 FPS.

## Warm render comparison

Independent runs varied slightly (hover median increased about 4.4%). An
additional 600 paired frames per scenario alternate old/new order within the
same process, with both scenes warmed and all caches populated:

| Scenario | Before median ms | After median ms | p95 before / after |
|---|---:|---:|---:|
| menu | 3.682 | 3.711 | 5.132 / 5.222 |
| combat | 5.156 | 5.331 | 9.699 / 9.146 |
| hover | 4.148 | 4.059 | 5.759 / 5.789 |

Warm rendering is broadly unchanged: median differences are under 0.18 ms in the
paired run. One after-change combat outlier reached 32.53 ms; this benchmark does
not attribute scheduling outliers to code changes. It does not prove that every
individual frame is faster. The measured wins are presentation and asset reuse.

## Functional and visual validation

- Viewport pixels match the original algorithm in seven resolutions, including
  resizing, half-size, full-size, 2x, letterbox and odd dimensions.
- Seeded menu, selection and combat snapshots match byte-for-byte in all three
  before/after runs. The paired warm snapshots match as well.
- Cache tests cover shared frames, cross-size decoding reuse, changed metadata,
  missing assets and an active scene retaining its frames after cache eviction.
- Two pre-existing warrior idle test failures were reproduced with the original
  loader. Their assertions now target fixed soles at both native sizes and a
  time-based maximum hold of 200 ms across the loop seam. The approved native
  assets hold identical pixels up to 167 ms at 96 px / 100 ms at 192 px. The old
  crop also included moving shins/cape. No animation was changed to pass tests.
- Full suite: **4,138 passed**, 0 failures, in 198.99 s. One Windows permission
  warning prevented writing the optional pytest cache; test execution completed.
  Command: `uv run pytest tests/ -v --basetemp=tmp/pytest-full -o cache_dir=tmp/pytest-cache`
  with SDL video/audio dummy drivers. Final log: `tmp/pytest-performance.log`.

## Reproduction

```powershell
uv run python scripts/benchmark_performance.py --baseline-ref f27617a325ecee8ffaf8c9b014b847817cf3f782 --output tmp/before.json
uv run python scripts/benchmark_performance.py --output tmp/after.json
uv run python scripts/benchmark_paired_render.py --baseline-ref f27617a325ecee8ffaf8c9b014b847817cf3f782 --output tmp/paired.json
$env:SDL_VIDEODRIVER='dummy'
$env:SDL_AUDIODRIVER='dummy'
uv run pytest tests/ -v
```

Raw results: `output/performance/before-1.json` through `before-3.json`,
`after-1.json` through `after-3.json`, `paired-warm.json` and `summary.json`.
The baseline mode loads only the original sprite loader, viewport and startup
prewarm function from Git; other game code is the same in both variants.

## Limits and remaining work

SDL dummy excludes the real display, compositor, monitor synchronization,
`display.flip()` and the frame limiter. Validate frame pacing on the target
window/monitor before claiming real FPS. These samples cover idle/hover rendering,
not worst-case boss attacks, massive decks or simultaneous effects. Enemy decoding
and first-time card variants remain synchronous. They were left unchanged because
bulk preloading adds memory/startup cost and no measured improvement was established
for those changes in this pass.

Official references: [pygame Clock](https://www.pygame.org/docs/ref/time.html),
[pygame transforms](https://www.pygame.org/docs/ref/transform.html),
[Python perf_counter](https://docs.python.org/3.13/library/time.html#time.perf_counter),
[Python profiling](https://docs.python.org/3.13/library/profile.html).
