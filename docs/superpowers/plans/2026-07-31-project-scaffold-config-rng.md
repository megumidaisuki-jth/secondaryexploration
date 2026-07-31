# Project Scaffold, Configuration Contract, and Deterministic RNG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**User-directed execution note:** This plan will be executed inline in the current task, with no additional workflow-skill invocation unless a concrete blocker makes one necessary.

**Goal:** Establish a dependency-free, testable Python foundation that rejects malformed experiment configurations and derives reproducible, namespaced random seeds before any simulator or topology code is introduced.

**Architecture:** A small `secondaryexploration` package owns two contracts. `config.py` converts untrusted JSON into an immutable validated `ExperimentConfig`; `randomness.py` maps a base seed plus a semantic namespace and replicate index to a stable 64-bit seed using a versioned SHA-256 framing rule. Standard-library `unittest` tests define both contracts, including a fixed seed vector that detects accidental algorithm changes.

**Tech Stack:** Python 3.10+, standard library (`dataclasses`, `hashlib`, `json`, `pathlib`, `random`, `unittest`), setuptools metadata only; no runtime or test dependencies.

**Research-contract traceability:** This slice implements the design specification's reproducibility requirements for validated configurations, deterministic randomness, replayable replicate identifiers, and fail-fast input checks. It deliberately does not implement hypergraphs, routing, liquidity updates, stopping times, or metrics.

---

## Task 1: Add the Python package and repository hygiene

**Files:**

- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `secondaryexploration/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Declare the package contract**

  Add setuptools metadata for package `secondaryexploration`, version `0.1.0`, Python `>=3.10`, and an empty dependency list. Do not add pytest, NumPy, or a simulator dependency in this slice.

- [ ] **Step 2: Add generated-file exclusions**

  Ignore Python caches, build metadata, virtual environments, coverage output, IDE files, and generated `outputs/`, while keeping `configs/` and test fixtures tracked.

- [ ] **Step 3: Expose only stable public metadata**

  Define `__version__ = "0.1.0"` and export it through `__all__`; do not re-export configuration or RNG symbols until their contracts are tested.

- [ ] **Step 4: Check the scaffold imports on the repository interpreter**

  Run:

  ```powershell
  python -c "import secondaryexploration; print(secondaryexploration.__version__)"
  ```

  Expected: prints `0.1.0` and exits with status 0.

- [ ] **Step 5: Run baseline test discovery**

  Run:

  ```powershell
  python -m unittest discover -s tests -v
  ```

  Expected: exits with status 0 and reports zero tests; later tasks replace this baseline with substantive tests.

## Task 2: Define configuration behavior with failing tests

**Files:**

- Create: `tests/test_config.py`

- [ ] **Step 1: Write the valid-construction tests**

  Test `ExperimentConfig.from_mapping(...)` with exactly these required fields:

  ```python
  {
      "schema_version": 1,
      "experiment_id": "scaffold-smoke",
      "base_seed": 20260731,
      "replicate_count": 4,
      "output_root": "outputs/scaffold-smoke",
  }
  ```

  Assert immutability, typed field values, canonical mapping order/content, and identical fingerprints for logically identical mappings with different input key order.

- [ ] **Step 2: Write strict rejection tests**

  Use subtests to require `ConfigError` for:

  - missing and unknown keys;
  - booleans where integers are required;
  - schema version other than `1`;
  - empty, whitespace-padded, non-portable, or over-64-character experiment IDs;
  - base seeds outside `[0, 2**64 - 1]`;
  - replicate counts outside `[1, 1_000_000]`;
  - empty, absolute, Windows-drive-qualified, backslash-containing, `.`-segment, or `..`-segment output paths.

- [ ] **Step 3: Write strict JSON-loading tests**

  In a temporary directory, assert that `load_experiment_config(path)`:

  - loads the valid object;
  - rejects malformed JSON;
  - rejects a non-object top level;
  - rejects duplicate JSON object keys rather than silently accepting the last value;
  - reports a missing file as `ConfigError` with the path in the message.

- [ ] **Step 4: Run the tests to verify the RED state**

  Run:

  ```powershell
  python -m unittest tests.test_config -v
  ```

  Expected: fails with `ModuleNotFoundError: No module named 'secondaryexploration.config'`.

## Task 3: Implement the immutable configuration contract

**Files:**

- Create: `secondaryexploration/config.py`
- Modify: `secondaryexploration/__init__.py`

- [ ] **Step 1: Add the public types and exact key contract**

  Implement:

  ```python
  class ConfigError(ValueError): ...

  @dataclass(frozen=True, slots=True)
  class ExperimentConfig:
      schema_version: int
      experiment_id: str
      base_seed: int
      replicate_count: int
      output_root: str

      @classmethod
      def from_mapping(cls, raw: Mapping[str, object]) -> "ExperimentConfig": ...
      def to_canonical_mapping(self) -> dict[str, object]: ...
      def fingerprint(self) -> str: ...

  def load_experiment_config(path: str | Path) -> ExperimentConfig: ...
  ```

  Require the exact five-key set. Error messages must identify the offending field or unknown/missing key.

- [ ] **Step 2: Validate values without Python coercion traps**

  Reject `bool` before integer range checks. Validate `experiment_id` against `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` and require `value == value.strip()`. For `output_root`, require portable forward slashes, reject POSIX absolute paths and Windows absolute/drive-qualified paths, and reject segments `""`, `"."`, and `".."`.

- [ ] **Step 3: Make serialization and identity deterministic**

  Serialize `to_canonical_mapping()` with `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=True)` and return the full hexadecimal SHA-256 digest from `fingerprint()`.

- [ ] **Step 4: Reject duplicate JSON keys during parsing**

  Use `json.load(..., object_pairs_hook=...)` with a hook that raises `ConfigError` on the first duplicate. Normalize file, decode, and JSON syntax errors into `ConfigError` while preserving a useful cause via exception chaining.

- [ ] **Step 5: Export the tested contract**

  Add `ConfigError`, `ExperimentConfig`, and `load_experiment_config` to package imports and `__all__`.

- [ ] **Step 6: Run the configuration tests to verify the GREEN state**

  Run:

  ```powershell
  python -m unittest tests.test_config -v
  ```

  Expected: all configuration tests pass.

## Task 4: Define deterministic seed derivation with failing tests

**Files:**

- Create: `tests/test_randomness.py`

- [ ] **Step 1: Write deterministic and separation tests**

  Assert that repeated calls return the same value and that changing any one of `base_seed`, `namespace`, or `index` changes the derived seed for the tested cases.

- [ ] **Step 2: Lock the version-1 seed test vector**

  Require:

  ```python
  derive_seed(20260731, "traffic", 3) == 10157683160262707388
  ```

  This value is the big-endian integer represented by the first eight bytes of SHA-256 over:

  ```text
  b"secondaryexploration.seed.v1\0"
  + base_seed as unsigned 8-byte big-endian
  + UTF-8 namespace length as unsigned 4-byte big-endian
  + UTF-8 namespace bytes
  + index as unsigned 8-byte big-endian
  ```

- [ ] **Step 3: Write input-rejection tests**

  Require `SeedError` for boolean or out-of-range base seeds, empty/non-string namespaces, and boolean/negative/out-of-range indices. Bound `index` to unsigned 64-bit so the byte framing cannot overflow.

- [ ] **Step 4: Write replay tests for `rng_for`**

  Assert that two independent generators created with the same tuple produce the same first ten `random()` values, while a different namespace produces a different tested sequence.

- [ ] **Step 5: Run the tests to verify the RED state**

  Run:

  ```powershell
  python -m unittest tests.test_randomness -v
  ```

  Expected: fails with `ModuleNotFoundError: No module named 'secondaryexploration.randomness'`.

## Task 5: Implement the versioned RNG contract

**Files:**

- Create: `secondaryexploration/randomness.py`
- Modify: `secondaryexploration/__init__.py`

- [ ] **Step 1: Implement validated, framed seed derivation**

  Implement:

  ```python
  class SeedError(ValueError): ...
  def derive_seed(base_seed: int, namespace: str, index: int) -> int: ...
  def rng_for(base_seed: int, namespace: str, index: int) -> random.Random: ...
  ```

  Use the exact version-1 framing and first-eight-byte conversion locked by the test vector. Do not use Python's process-randomized `hash()`.

- [ ] **Step 2: Keep namespaces semantic and exact**

  Accept non-empty UTF-8 strings, reject leading/trailing whitespace and NUL, and do not lowercase or otherwise normalize. This makes namespace changes explicit and auditable.

- [ ] **Step 3: Export the tested RNG API**

  Add `SeedError`, `derive_seed`, and `rng_for` to package imports and `__all__`.

- [ ] **Step 4: Run RNG and full unit suites**

  Run:

  ```powershell
  python -m unittest tests.test_randomness -v
  python -m unittest discover -s tests -v
  ```

  Expected: all RNG tests and then the full suite pass.

## Task 6: Add and test the pilot configuration artifact

**Files:**

- Create: `configs/pilot/scaffold-smoke.json`
- Create: `tests/test_pilot_config.py`
- Modify: `README.md`

- [ ] **Step 1: Write the artifact test before the artifact**

  Load `configs/pilot/scaffold-smoke.json` through the public API and assert its five typed values. Assert that its fingerprint equals the independently precomputed canonical SHA-256 digest `2eae8983105262dd1e3fdc82629bab067c2e1364e171ee3bee3c74b534d3e575`.

- [ ] **Step 2: Run the test to verify the RED state**

  Run:

  ```powershell
  python -m unittest tests.test_pilot_config -v
  ```

  Expected: fails because `configs/pilot/scaffold-smoke.json` does not yet exist.

- [ ] **Step 3: Add the valid pilot JSON**

  Store exactly the valid mapping from Task 2 as pretty-printed UTF-8 JSON with a final newline. Do not include comments or machine-local absolute paths.

- [ ] **Step 4: Verify the independently precomputed fingerprint**

  Run:

  ```powershell
  python -c "from secondaryexploration import load_experiment_config; print(load_experiment_config('configs/pilot/scaffold-smoke.json').fingerprint())"
  ```

  Expected: prints `2eae8983105262dd1e3fdc82629bab067c2e1364e171ee3bee3c74b534d3e575`. Keep that fixed constant in `tests/test_pilot_config.py`, then alter one in-memory field in the test and assert that the fingerprint changes.

- [ ] **Step 5: Document the runnable foundation**

  Add to `README.md`: supported Python version, zero-dependency test command, pilot config path, configuration fingerprint meaning, seed derivation tuple, and the explicit statement that no scientific simulator has been implemented yet.

- [ ] **Step 6: Run the pilot and full suites**

  Run:

  ```powershell
  python -m unittest tests.test_pilot_config -v
  python -m unittest discover -s tests -v
  ```

  Expected: all tests pass.

## Task 7: Self-review, verify, and publish the implementation milestone

**Files:**

- Review: all files created or modified by Tasks 1–6

- [ ] **Step 1: Run static repository checks**

  Run:

  ```powershell
  git diff --check
  git status --short
  rg -n "TODO|TBD|FIXME|NotImplementedError|pass$" secondaryexploration tests configs README.md
  ```

  Expected: `git diff --check` is silent; status lists only intended files; placeholder scan returns no matches in implementation or tests.

- [ ] **Step 2: Run both available Python interpreters**

  Run the full suite with the system Python 3.10 and the Codex bundled Python 3.12:

  ```powershell
  python -m unittest discover -s tests -v
  & 'C:\Users\jiate\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
  ```

  Expected: identical test counts and all tests pass on both versions.

- [ ] **Step 3: Review against the research contract**

  Confirm that this slice supplies only configuration/reproducibility primitives, uses no process-randomized hash, embeds no local absolute path in tracked data, and makes no scientific-performance claim.

- [ ] **Step 4: Commit the verified implementation**

  Run:

  ```powershell
  git add .gitignore pyproject.toml secondaryexploration tests configs README.md
  git diff --cached --check
  git commit -m "feat: add reproducible experiment foundation"
  ```

- [ ] **Step 5: Push the milestone branch and verify the remote**

  Run:

  ```powershell
  git push origin codex/research-contract
  git ls-remote --heads origin codex/research-contract
  ```

  Expected: the remote branch hash matches local `HEAD`.

## Completion criteria

- [ ] The package imports on Python 3.10 and 3.12 without third-party dependencies.
- [ ] Malformed or ambiguous configuration files fail before an experiment can start.
- [ ] A configuration has a deterministic SHA-256 identity.
- [ ] Every stochastic component can request an independent, replayable seed by `(base_seed, namespace, index)`.
- [ ] The fixed seed vector and pilot-config fingerprint prevent silent reproducibility-contract drift.
- [ ] All tests pass on both interpreters and the implementation milestone is present on GitHub.
