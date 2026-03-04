# Generate a Demo App

Generate a working FastAPI + browser demo for a domain's policy module. Reads the CIVIL spec and test manifest to produce four tailored files in `domains/<domain>/output/demo-<module>/`.

## Input

```
/create-demo                        # auto-detect domain/module or prompt if ambiguous
/create-demo <domain>               # use that domain; auto-detect module
/create-demo <domain> <module>      # skip scanning entirely
```

If no args are provided, list all `domains/*/specs/*.civil.yaml` files and prompt the user to choose.

## Pre-flight

1. **Domain folder exists?** — NO → Print: `"Domain '<domain>' not found. Run /new-domain <domain> first."` Stop.
2. **CIVIL file exists?**
   - `domains/<domain>/specs/<module>.civil.yaml` missing → Print: `"No CIVIL file found. Run /extract-ruleset <domain> first."` Stop.
3. **Rego file exists?**
   - `domains/<domain>/output/<module>.rego` missing → Print: `"No Rego found. Run /transpile-and-test <domain> <module> first."` Stop.
4. **Test manifest present?**
   - `domains/<domain>/specs/tests/<module>_tests.yaml` missing → note: proceed with placeholder examples; print warning at the end.

## Mode Detection

```bash
ls domains/<domain>/output/demo-<module>/ 2>/dev/null
```

| Result | Mode |
|--------|------|
| Directory absent | **CREATE mode** |
| Directory present | **UPDATE mode** — prompt: `"Demo already exists at domains/<domain>/output/demo-<module>/. Regenerate and overwrite? [y/N]"` — abort on N |

---

## Process — CREATE Mode

### Step 1: Read Inputs

- Load `domains/<domain>/specs/<module>.civil.yaml` — extract:
  - `facts.<Entity>.fields` — input field names, types, optionality, descriptions
  - `computed:` — output computed field names (keys only; ignore `expr:`/`conditional:` values)
  - `decisions:` — decision field names and types
  - `metadata` — domain name, description, any policy citation
- Load `domains/<domain>/specs/tests/<module>_tests.yaml` if present — pick up to 3 test cases with distinct outcomes (prefer one `allow_*`, one `deny_*`, one edge case).

### Step 2: Create Output Directory

```bash
mkdir -p domains/<domain>/output/demo-<module>/static
```

### Step 3: Write `requirements.txt`

Static content — no domain-specific substitutions:

```
fastapi
uvicorn[standard]
httpx
pydantic
```

### Step 4: Write `start.sh`

Model exactly on `domains/snap/output/demo-eligibility/start.sh`. Key substitutions:

```bash
#!/usr/bin/env bash
# Start the Xlator <Domain> <Module> Demo
# ...

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"       # always 4 levels up
REGO_FILE="$REPO_ROOT/domains/<domain>/output/<module>.rego"
OPA_PORT=8181
FASTAPI_PORT=8000
```

The Rego prerequisite error message must use the correct domain/module:
```bash
  echo "  ./x transpile <domain> <module>"
```

Keep all other logic verbatim: OPA health-check loop, cleanup trap, uvicorn launch.

### Step 5: Write `main.py`

Model on `domains/snap/output/demo-eligibility/main.py`. Key substitutions:

**Constants:**
```python
OPA_URL = "http://localhost:8181"
OPA_DECISION_PATH = "/v1/data/<domain>/<module>/decision"
```

**App title** (use human-readable domain/module names from CIVIL `metadata:`):
```python
app = FastAPI(
    title="Xlator <Domain> <Module> Demo",
    description="Evaluates <module> using OPA-compiled CIVIL rules",
    ...
)
```

**`InputFacts` Pydantic model** — one field per `facts.<Entity>.fields` entry:

| CIVIL type | Python type | Field default |
|-----------|-------------|---------------|
| `int` | `int` | `Field(..., ...)` if required; `Field(0, ...)` if optional |
| `money` | `float` | `Field(..., ge=0, ...)` if required; `Field(0.0, ge=0, ...)` if optional |
| `bool` | `bool` | `Field(False, ...)` (always optional) |
| `string` | `str` | `Field(..., ...)` if required; `Field("", ...)` if optional |

Use the CIVIL `description:` as the Pydantic `description=` string.

**`ComputedBreakdown` Pydantic model** — one field per `computed:` key:
- Keys ending in `_deduction`, `_income`, `_limit`, `_excess`, `_costs` → `float`
- Keys starting with `passes_` or `is_` → `bool`
- Default to `float` when unsure

**`DenialReason` model** (standard, copy verbatim):
```python
class DenialReason(BaseModel):
    code: str
    message: str
    citation: str = ""
```

**Response model** — derive from `decisions:`:
- `eligible: bool` field → `eligible: bool`
- `list` type field (e.g., `denial_reasons`) → `list[DenialReason]`
- Always include `computed: ComputedBreakdown`

**API route:**
```python
@app.post("/api/<domain>/<module>", response_model=<ResponseModel>)
async def check_eligibility(facts: InputFacts):
    payload = {"input": facts.model_dump()}
    ...
    return <ResponseModel>(
        eligible=result["eligible"],
        denial_reasons=[DenialReason(**r) for r in result.get("denial_reasons", [])],
        computed=ComputedBreakdown(**result["computed"]),
    )
```

Keep lifespan OPA health-check, error handling (ConnectError, HTTPStatusError, TimeoutException), and `/health` endpoint verbatim.

### Step 6: Write `static/index.html`

Model on `domains/snap/output/demo-eligibility/static/index.html`. Copy the CSS verbatim (it is generic). Substitute domain-specific content:

**Header:**
```html
<title><Module> Check — Xlator Demo</title>
<h1><Module> Check</h1>
<p class="subtitle">
  Powered by the Xlator pipeline —
  <module> rules compiled to OPA/Rego via CIVIL DSL.
  <!-- Add policy citation from CIVIL metadata: if present -->
</p>
```

**Example buttons** — one button per test case selected in Step 1 (up to 3). Use a short human-readable label derived from the test `description:` or `tags:`:
```html
<button class="example-btn" onclick="loadExample('<key>')"><Label></button>
```

**Form fields** — one `<div class="field">` per `facts.<Entity>.fields` entry:
- `bool` fields → `<input type="checkbox" id="<name>" name="<name>">` with label
- `int` fields → `<input type="number" id="<name>" name="<name>" min="0" step="1">`
- `money` fields → `<input type="number" id="<name>" name="<name>" min="0" step="1">`
- Group related fields with `<div class="field-group">` (2-column grid)
- Use the CIVIL `description:` as a `<span class="hint">` after the label

**JS `EXAMPLES` dict** — one entry per selected test case:
```javascript
const EXAMPLES = {
  <key>: {
    <field_name>: <value>,   // from test inputs:
    // ... all fact fields (omitted optional ones default to 0/false)
  },
  ...
};
```

If no test manifest exists, use `TODO` placeholders:
```javascript
const EXAMPLES = {
  example_1: { /* TODO: fill in after running /create-tests <domain> */ },
};
```

**`loadExample()` function** — one `document.getElementById('<name>').value = ex.<name>` line per fact field; use `.checked` for `bool` fields.

**Form submit handler** — build `payload` object with correct JS type coercions:
- `bool` → `.checked` (boolean)
- `int` → `parseInt(...)`
- `money` → `parseFloat(...) || 0`
- `fetch('/api/<domain>/<module>', ...)` — endpoint must match `main.py`

**`renderResults()` function:**
- Show eligible/ineligible badge
- Show breakdown table for numeric `computed:` fields (deductions, limits, income values)
- Show pass/fail `<div class="test-result">` for boolean `computed:` fields starting with `passes_`
- Show denial reasons list if `!eligible && data.denial_reasons.length > 0`
- Adapt column labels and row descriptions to the domain (use snake_case → human label)

### Step 7: Print Summary

```
Demo created at domains/<domain>/output/demo-<module>/
  requirements.txt
  start.sh
  main.py
  static/index.html
```

If no test manifest was found, print:
```
⚠  No test manifest found — EXAMPLES in index.html contain TODO placeholders.
   Run /create-tests <domain> <module> for realistic example scenarios.
```

```
Next steps:
  1. Install deps:   pip install -r domains/<domain>/output/demo-<module>/requirements.txt
  2. Run the demo:   ./x demo <domain> <module>
  3. Open browser:   http://localhost:8000/static/index.html
  4. API docs:       http://localhost:8000/docs
```

---

## Process — UPDATE Mode

After confirming overwrite, execute CREATE mode in full. Overwrite all 4 files.

---

## CIVIL Type → Generated Artifact Summary

| CIVIL field | Generated artifact |
|-------------|-------------------|
| `facts.<Entity>.fields` | `InputFacts` Pydantic fields in `main.py`; `<input>` elements in `index.html`; `payload` fields in submit handler |
| `computed:` keys | `ComputedBreakdown` Pydantic fields in `main.py`; breakdown table rows + test-result divs in `renderResults()` |
| `decisions:` keys | Response model fields in `main.py`; badge + denial list in `renderResults()` |
| `metadata.domain` + module name | `OPA_DECISION_PATH`, FastAPI route, app title, page title |
| Test cases (up to 3) | `EXAMPLES` dict + button labels in `index.html` |

---

## Common Mistakes to Avoid

- **Do NOT hardcode `snap` or `eligibility`** — derive all names from `<domain>` and `<module>` args
- **Do NOT copy SNAP-specific field names** — read the CIVIL spec and derive field names from it
- **Do NOT include Rego generation logic** — Rego is a pre-existing prerequisite
- **Use `facts.<Entity>.fields` keys verbatim** as Python attribute names and HTML `id`/`name` values — they are already snake_case
- **The `computed:` block may have `conditional:` entries** — extract the key name only; ignore the expression
- **The `decisions:` block may have a `list` type field** (e.g., `denial_reasons`) — map to `list[DenialReason]` in Python
- **`start.sh` REPO_ROOT is always 4 levels up** from the script — `$(cd "$SCRIPT_DIR/../../../.." && pwd)` — do not change this

**Reference files (read these before generating):**
- `domains/snap/output/demo-eligibility/main.py` — canonical FastAPI pattern
- `domains/snap/output/demo-eligibility/static/index.html` — canonical HTML/JS pattern
- `domains/snap/output/demo-eligibility/start.sh` — canonical launcher pattern
