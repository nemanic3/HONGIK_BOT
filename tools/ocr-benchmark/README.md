# Local CPU OCR comparison

Experimental benchmark only; does not change Django's default provider or database.
No student files or OCR results belong in this directory or in Git.

Tested on macOS ARM with Docker Linux aarch64, four CPU cores and 4 GiB container
memory limit. Python 3.11; PaddlePaddle 3.2.2, PaddleOCR 3.3.2, PaddleX 3.3.13.
The Korean recognition model is explicitly selected: specifying a detection model
can cause PaddleOCR to ignore `lang`, so relying on `lang='korean'` alone is unsafe.

From this directory:

```sh
docker build -t hongik-ocr-benchmark:local .
# Download public model weights only. No input files are mounted here.
docker run --rm --cpus=4 --memory=4g \
  -e DOWNLOAD_ONLY=1 -e PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
  -v hongik-ocr-models:/root/.paddlex -v "$PWD:/work:ro" \
  hongik-ocr-benchmark:local python benchmark.py
# Create /private/tmp/hongik-ocr-inputs and /private/tmp/hongik-ocr-output first.
# Place consented PNG test files in the inputs directory, outside the repository.
docker run --rm --network none --cpus=4 --memory=4g \
  -e PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
  -v hongik-ocr-models:/root/.paddlex -v "$PWD:/work:ro" \
  -v /private/tmp/hongik-ocr-inputs:/inputs:ro \
  -v /private/tmp/hongik-ocr-output:/output \
  hongik-ocr-benchmark:local python benchmark.py
```

Models are initialized once and reused for two passes per PNG. Outputs contain
private OCR text and positions, are mode 0600, and remain outside the repository.
`peak_rss_kib` measures cumulative process peak RSS, not total Docker Desktop RAM.
Dependency versions are pinned at the principal-package level; transitive packages
and the Python image tag are not fully locked, so bit-for-bit rebuilds are not claimed.

## Observed comparison (2026-10-09)

Two user-authorized screenshots: a six-course single table and a two-column table.
No general accuracy percentage can be inferred from this small sample.

| Path | Single table | Two-column table |
| --- | ---: | ---: |
| Current Vision adapter (includes Swift startup/compilation) | 28.379 s | 34.046 s |
| Precompiled Vision, repeat/warm run | 0.236 s | 0.386 s |
| Paddle Korean mobile CPU, repeat run | 3.453 s | 12.324 s |

Precompiled Vision's first measured execution took 14.254 s; compilation time is
excluded from those binary timings. Paddle cached model initialization took 0.656 s,
and first image passes took 3.469 s (single) and 12.449 s (double). These are wall
clock measurements, not controlled hardware-isolated benchmarks. Paddle peak process
RSS was 1,089,408 KiB (~1.04 GiB). Both engines were local; Paddle inference ran with
network disabled. Initial package/model downloads require network access.

Manual checks: both recognized the six course names/codes on the single table.
Paddle read one A0 as AO. On the two-column sample, Paddle read a credit 4 as A,
merged one credit/grade header, and produced Co/DO grade variants. Vision also
produced AO/CO variants and merged a credit/grade header. Wrapped names and clipped
headers need explicit handling for both. Neither engine change solves table assembly.

Decision: do not replace the production provider based on this test. For Mac-local
use, cache/compile Vision once to remove startup overhead; for Linux deployment,
Paddle Korean mobile is a working CPU candidate. First implement shared two-column
segmentation, cell-position reconstruction, conservative missing-value handling,
source-aware overlap detection and retake/semester-retake validation. Do not silently
turn an uncertain credit A into 4 or count all repeated courses as duplicates.

Clipboard import was not verified: native browser automation was interrupted by
concurrent user interaction. DOM accessibility reading previously worked, but does
not establish that ordinary clipboard paste preserves usable tables.
