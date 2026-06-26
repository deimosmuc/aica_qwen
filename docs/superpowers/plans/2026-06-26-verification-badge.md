# Verification Badge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the KiCad-verification proof honest and portable — a three-state badge (verified / failed / structural-only) plus the rendered schematic and a `VERIFICATION.md` summary embedded in the downloadable ZIP.

**Architecture:** Extend the existing validation stage. `validate_project` already runs a real KiCad open-check (PDF export) and ERC. We persist that PDF into the project directory (instead of a temp dir), convert it to a PNG with the PyMuPDF dependency already in the project, and render a `VERIFICATION.md` template. A new `KiCadCli.version()` feeds the version string into the `Validation` model, which the existing Alpine.js frontend reads to drive the three-state badge and a verification card. Packaging needs no change — the new files live outside the excluded `preview/` folder.

**Tech Stack:** Python, FastAPI, Pydantic, Jinja2, PyMuPDF (`fitz`), pytest, Alpine.js.

Spec: `docs/superpowers/specs/2026-06-26-verification-badge-design.md`

---

## File structure

- Modify `app/services/kicad_cli.py` — add `version()` (cached).
- Modify `app/models/schemas.py` — add `Validation.kicad_version: str | None`.
- Modify `app/services/validation.py` — persist PDF, render PNG, render `VERIFICATION.md`, set `kicad_version`.
- Create `app/templates/verification.md.j2` — the verification summary template.
- Modify `app/static/index.html` — three-state badge, verification card, `.valbadge.warn` CSS.
- Modify `tests/test_validation.py` — `FakeKiCad.version()`, new assertions.
- Modify `tests/test_packaging.py` — assert `VERIFICATION.md` is packaged.
- Modify `tests/test_kicad_cli.py` — `version()` behaviour.

---

## Task 1: `KiCadCli.version()` + `kicad_version` on the model

**Files:**
- Modify: `app/services/kicad_cli.py`
- Modify: `app/models/schemas.py:119-127`
- Test: `tests/test_kicad_cli.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_kicad_cli.py`:

```python
def test_version_none_when_unavailable():
    cli = KiCadCli(Settings(kicad_enabled=False))
    assert cli.version() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kicad_cli.py::test_version_none_when_unavailable -v`
Expected: FAIL with `AttributeError: 'KiCadCli' object has no attribute 'version'`

- [ ] **Step 3: Add the `version()` method**

In `app/services/kicad_cli.py`, add a sentinel near the top (after the imports/`KiCadCliError`):

```python
_UNSET = object()
```

In `KiCadCli.__init__`, after `self._path = ...`, add:

```python
        self._version_cache = _UNSET  # lazily filled by version()
```

Add the method (after `path` property is fine):

```python
    def version(self) -> str | None:
        """Return the kicad-cli version string, or None if unavailable.

        Cached after the first call. A failed/zero-output query caches as None
        so the badge can still say "Verified in KiCad" without a number.
        """
        if self._version_cache is not _UNSET:
            return self._version_cache
        if not self._path:
            self._version_cache = None
            return None
        try:
            proc = self._run(["version"])
        except KiCadCliError:
            self._version_cache = None
            return None
        out = proc.stdout.strip() if proc.returncode == 0 else ""
        self._version_cache = out or None
        return self._version_cache
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_kicad_cli.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Add the schema field**

In `app/models/schemas.py`, in `class Validation`, add after `kicad_opens`:

```python
    kicad_version: str | None = None
```

- [ ] **Step 6: Run the full suite to confirm nothing broke**

Run: `python -m pytest -q`
Expected: PASS (the new field defaults to None; existing tests unaffected)

- [ ] **Step 7: Commit**

```bash
git add app/services/kicad_cli.py app/models/schemas.py tests/test_kicad_cli.py
git commit -m "feat(verify): kicad-cli version() and kicad_version field"
```

---

## Task 2: Persist PDF, render PNG + VERIFICATION.md in validation

**Files:**
- Create: `app/templates/verification.md.j2`
- Modify: `app/services/validation.py`
- Test: `tests/test_validation.py`

- [ ] **Step 1: Update `FakeKiCad` so it supports `version()`**

In `tests/test_validation.py`, add to `class FakeKiCad` (after `__init__`):

```python
    def version(self):
        return "KiCad 9.0.1" if self._available else None
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_validation.py`:

```python
def test_verification_artifacts_written_when_opens(tmp_path):
    out = _scaffold(tmp_path)
    v = validate_project(out, mock_run(REQ_TEXT), FakeKiCad(available=True, opens=True))
    assert v.kicad_version == "KiCad 9.0.1"
    assert (out / "schematic.pdf").is_file()        # the open-check export, persisted
    assert (out / "VERIFICATION.md").is_file()       # summary travels with the artifact
    text = (out / "VERIFICATION.md").read_text(encoding="utf-8")
    assert "KiCad 9.0.1" in text


def test_no_verification_artifacts_when_unavailable(tmp_path):
    out = _scaffold(tmp_path)
    validate_project(out, mock_run(REQ_TEXT), FakeKiCad(available=False))
    assert not (out / "VERIFICATION.md").exists()
    assert not (out / "schematic.pdf").exists()


def test_no_verification_artifacts_when_open_fails(tmp_path):
    out = _scaffold(tmp_path)
    validate_project(out, mock_run(REQ_TEXT), FakeKiCad(available=True, opens=False))
    assert not (out / "VERIFICATION.md").exists()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_validation.py::test_verification_artifacts_written_when_opens -v`
Expected: FAIL — `schematic.pdf`/`VERIFICATION.md` not created, and `kicad_version` is None.

- [ ] **Step 4: Create the template**

Create `app/templates/verification.md.j2`:

```jinja
# Verification

*Machine-checked proof for this generated scaffold. The project below was opened
and exported by KiCad itself — these files are not hallucinated. This verifies
the scaffold **opens and is internally consistent**; it does **not** certify the
design as correct or production-ready. A human engineer remains responsible.*

**Verified by:** {{ validation.kicad_version or "KiCad" }}

## What was checked

- Opens & exports in KiCad: {{ "✅ yes" if validation.kicad_opens else "❌ no" }}
{% if validation.erc_violations is not none %}- ERC ran: ✅ ({{ validation.erc_violations }} violation{{ "" if validation.erc_violations == 1 else "s" }}{% if validation.erc_by_severity %} — {% for sev, n in validation.erc_by_severity.items() %}{{ sev }}: {{ n }}{% if not loop.last %}, {% endif %}{% endfor %}{% endif %})
{% endif %}- Structural checks: {{ "✅ all passed" if validation.ok else "⚠️ see validation_report.md" }}
{% if png_name %}
## Rendered schematic

![Rendered schematic]({{ png_name }})
{% endif %}
```

- [ ] **Step 5: Add a PDF→PNG helper to `validation.py`**

In `app/services/validation.py`, after the imports, add:

```python
def _pdf_to_png(pdf_path: Path, png_path: Path, dpi: int = 150) -> bool:
    """Render the first page of a PDF to PNG. Best-effort: returns False on any
    failure (mirrors how the SVG preview is best-effort). Uses PyMuPDF, already a
    project dependency (see tools/pdf2png.py)."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        try:
            page = doc[0]
            page.get_pixmap(dpi=dpi).save(png_path)
        finally:
            doc.close()
        return png_path.is_file()
    except Exception:
        return False
```

- [ ] **Step 6: Persist the open-check PDF to the project directory**

In `validate_project`, the real-KiCad block currently exports into a
`TemporaryDirectory`. Replace the open-check so the PDF lands in `project_dir`.

Find:

```python
    if kicad.available:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            try:
                kicad.export_pdf(root_sch, tmp_dir / "open_check.pdf")
                kicad_opens = True
            except KiCadCliError as e:
```

Replace with:

```python
    pdf_path = project_dir / "schematic.pdf"
    if kicad.available:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            try:
                kicad.export_pdf(root_sch, pdf_path)
                kicad_opens = True
            except KiCadCliError as e:
```

(The `tmp_dir` is still used for the ERC report a few lines below — leave that line as `tmp_dir / "erc.json"`.)

- [ ] **Step 7: Capture the version inside the available branch**

Still inside `if kicad.available:`, immediately after `tmp_dir = Path(tmp)`, add:

```python
            kicad_version = kicad.version()
```

And declare it with the other optionals near the top of the real-KiCad section, next to `kicad_opens: bool | None = None`:

```python
    kicad_version: str | None = None
```

- [ ] **Step 8: Pass `kicad_version` into the `Validation(...)` constructor**

In the `validation = Validation(...)` call, add the field:

```python
        kicad_version=kicad_version,
```

- [ ] **Step 9: Render PNG + VERIFICATION.md after the Validation object exists**

Just before the existing `# --- Report ---` block that writes `validation_report.md`, add:

```python
    # --- Verification artifacts (only when KiCad actually opened it) ----------
    if kicad_opens and pdf_path.is_file():
        png_name = "schematic_preview.png"
        png_ok = _pdf_to_png(pdf_path, project_dir / png_name)
        (project_dir / "VERIFICATION.md").write_text(
            _env().get_template("verification.md.j2").render(
                validation=validation,
                png_name=png_name if png_ok else None,
            ),
            encoding="utf-8",
        )
        if not png_ok:
            notes.append("Schematic PNG could not be rendered; VERIFICATION.md is text-only.")
```

Note: `notes` is already attached to `validation` by reference, so appending here keeps the in-memory object consistent even though the report files are already being written.

- [ ] **Step 10: Run the tests to verify they pass**

Run: `python -m pytest tests/test_validation.py -v`
Expected: PASS. (`schematic.pdf` is the fake `%PDF-1.5` string from `FakeKiCad`, so `_pdf_to_png` returns False — VERIFICATION.md is still written, text-only. That is the intended best-effort behaviour.)

- [ ] **Step 11: Commit**

```bash
git add app/services/validation.py app/templates/verification.md.j2 tests/test_validation.py
git commit -m "feat(verify): persist schematic PDF/PNG and write VERIFICATION.md"
```

---

## Task 3: Verify the artifacts are packaged into the ZIP

**Files:**
- Test: `tests/test_packaging.py`

No production code changes — the new files live at the project root (outside the
excluded `preview/` folder), so `create_project_zip` already includes them. This
task locks that behaviour with a test.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_packaging.py`:

```python
def test_zip_includes_verification_artifacts(tmp_path):
    out = generate_scaffold(mock_run(REQ_TEXT), REQ_TEXT, tmp_path / "proj")
    # Simulate verification artifacts produced when KiCad verified the project.
    (out / "VERIFICATION.md").write_text("# Verification\n", encoding="utf-8")
    (out / "schematic_preview.png").write_bytes(b"\x89PNG\r\n")
    (out / "schematic.pdf").write_text("%PDF-1.5", encoding="utf-8")

    zip_path = create_project_zip(out)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "VERIFICATION.md" in names
    assert "schematic_preview.png" in names
    assert "schematic.pdf" in names
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/test_packaging.py -v`
Expected: PASS (confirms no exclusion rule blocks the new files).

- [ ] **Step 3: Commit**

```bash
git add tests/test_packaging.py
git commit -m "test(verify): assert verification artifacts are packaged in the ZIP"
```

---

## Task 4: Three-state badge + verification card in the UI

**Files:**
- Modify: `app/static/index.html` (CSS block near line 70-73; markup near line 445-465)

This is a frontend change verified visually (no JS unit test in this project).

- [ ] **Step 1: Add the warning badge CSS**

In `app/static/index.html`, find:

```css
    .valbadge.fail { background: rgba(210,153,34,.15); color: var(--warn); border-color: var(--warn); }
```

Add directly after it:

```css
    .valbadge.warn { background: rgba(210,153,34,.15); color: var(--warn); border-color: var(--warn); }
    .valbadge.verified { background: rgba(63,185,80,.15); color: var(--ok); border-color: var(--ok); }
    .verifycard { margin-top: 8px; font-size: 13px; color: var(--muted); }
    .verifycard b { color: var(--ok); }
```

- [ ] **Step 2: Replace the badge markup with the three-state badge**

Find:

```html
              <span class="valbadge" :class="gen.validation.ok ? 'ok' : 'fail'"
                x-text="gen.validation.ok ? '✓ Validation passed' : '✗ Validation failed'"></span>
```

Replace with:

```html
              <span class="valbadge"
                :class="!gen.validation.kicad_cli_available ? 'warn' : (gen.validation.kicad_opens ? 'verified' : 'fail')"
                x-text="!gen.validation.kicad_cli_available
                  ? '⚠ Structural checks only — KiCad not available'
                  : (gen.validation.kicad_opens
                      ? ('✅ Verified in ' + (gen.validation.kicad_version || 'KiCad'))
                      : '❌ KiCad verification failed')"></span>
```

- [ ] **Step 3: Add the separate structural line + verification card**

Find the ERC paragraph block:

```html
                <p class="muted" x-show="gen.validation.kicad_cli_available" style="margin-top:8px"
                  x-text="'ERC violations: ' + (gen.validation.erc_violations === null ? 'n/a' : gen.validation.erc_violations)"></p>
                <p class="muted" x-show="!gen.validation.kicad_cli_available" style="margin-top:8px">
                  kicad-cli not available here — structural checks only; preview disabled.
                </p>
```

Replace with:

```html
                <p class="muted" style="margin-top:8px"
                  x-text="'Structural checks: ' + (gen.validation.ok ? '✅ all passed' : '⚠️ see report')"></p>
                <div class="verifycard" x-show="gen.validation.kicad_cli_available">
                  <span x-text="'KiCad: ' + (gen.validation.kicad_version || 'available')"></span>
                  · <span x-text="gen.validation.kicad_opens ? 'opens & exports ✓' : 'open/export ✗'"></span>
                  · <span x-text="'ERC ran — ' + (gen.validation.erc_violations === null ? 'n/a' : gen.validation.erc_violations) + ' violations'"></span>
                </div>
                <p class="muted" x-show="!gen.validation.kicad_cli_available" style="margin-top:8px">
                  kicad-cli not available here — structural checks only; preview disabled.
                </p>
```

- [ ] **Step 4: Verify in the preview**

Start the app and generate a scaffold. With kicad-cli installed locally the badge
should read green "✅ Verified in KiCad 9.x" with the verification card beneath it;
without it, yellow "⚠ Structural checks only". Confirm the schematic preview still
renders and the ZIP downloads.

Run: `python -m pytest -q` (full suite still green)
Then load the app and visually confirm the badge states.

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html
git commit -m "feat(verify): three-state KiCad badge and verification card in UI"
```

---

## Task 5: Real end-to-end packaging proof (kicad-cli gated)

**Files:**
- Test: `tests/test_validation.py`

- [ ] **Step 1: Write the gated end-to-end test**

Add to `tests/test_validation.py` (it already imports `Settings`, `KiCadCli`, `pytest`):

```python
@pytest.mark.skipif(
    not KiCadCli(Settings()).available, reason="kicad-cli not installed in this environment"
)
def test_real_kicad_produces_png_and_verification(tmp_path):
    out = _scaffold(tmp_path)
    validate_project(out, mock_run(REQ_TEXT), KiCadCli(Settings()))
    assert (out / "schematic.pdf").is_file()
    assert (out / "schematic_preview.png").is_file()   # real PDF renders to PNG
    text = (out / "VERIFICATION.md").read_text(encoding="utf-8")
    assert "schematic_preview.png" in text             # PNG is embedded in the summary
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_validation.py -v`
Expected: PASS where kicad-cli is installed; SKIPPED otherwise. Both outcomes are green.

- [ ] **Step 3: Commit**

```bash
git add tests/test_validation.py
git commit -m "test(verify): end-to-end PNG + VERIFICATION.md with real kicad-cli"
```

---

## Final verification

- [ ] Run the full suite: `python -m pytest -q` — all pass (gated test skipped if no kicad-cli).
- [ ] Manually generate a scaffold in the UI and confirm: correct badge state, verification card, schematic preview, and that the downloaded ZIP contains `VERIFICATION.md`, `schematic_preview.png`, and `schematic.pdf` (when kicad-cli is present).
- [ ] Confirm no "production-ready" claim was introduced (the existing validation check guards this; `VERIFICATION.md` wording is deliberately qualified).
