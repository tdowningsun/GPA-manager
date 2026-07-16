"""Static configuration and shared domain types for GPA Manager.

This module is the single source of truth for the grading rules and
the shared domain TypedDicts (:class:`Course` and :class:`Semester`).

The numeric score-to-GPA mapping used to be hardcoded as the
:data:`SCORE_RANGES` constant; it is now loaded at startup from
``config/gpa_scale.json`` (auto-generated on first run) so the scale
can be edited per-school without touching code. See
:func:`load_gpa_scale` for the loader contract.
"""

import json
import pathlib
import sys
from typing import Final, Optional, TypedDict


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class Course(TypedDict):
    """A single course record.

    Attributes:
        name: Course name as entered by the user.
        credit: Course credit value (positive number).
        score: Raw score input, either a numeric string or a textual
            descriptor from :data:`TEXT_RULES`.
        point: Resolved GPA grade point.
    """

    name: str
    credit: float
    score: str
    point: float


class Semester(TypedDict):
    """An aggregated multi-semester entry.

    One :class:`Semester` represents the *summary* of a single
    semester - its display name, the totals (credits + GPA) shown in
    the multi-semester table, and the course list used by the
    ``Open Semester`` editor dialog to recompute those totals.

    ``credits`` and ``gpa`` are *derived* from ``courses`` by
    :func:`gpa_calculator.calculate_gpa`; ``Open Semester`` writes them
    back when the user saves the dialog. New semesters start with
    ``credits=0.0``, ``gpa=0.0`` and ``courses=[]`` until the user
    opens the semester and adds courses.

    Attributes:
        name: Display name of the semester (e.g. ``"Fall 2024"``).
        credits: Total credits across the semester's courses.
        gpa: Weighted GPA for the semester.
        courses: Per-semester course list, each entry a :class:`Course`.
    """

    name: str
    credits: float
    gpa: float
    courses: list[Course]


# ---------------------------------------------------------------------------
# GPA scale configuration
# ---------------------------------------------------------------------------
#
# The GPA scale is loaded from ``config/gpa_scale.json`` as a GRS v1
# (GPA Rule Specification v1) document. The on-disk structure is
# data-only - no formulas, no scripts - and is organised as:
#
#   metadata            school, country, version, gpa_scale, ...
#   supported_inputs    which input categories the school uses
#   numeric             numeric-score rules (range / linear / lookup)
#   text                text-grade -> GPA mapping
#   letter              letter-grade -> GPA mapping
#   special             special-mark -> behavior mapping
#
# The loader (see :func:`load_gpa_scale`) reads the GRS v1 JSON and
# projects it into the in-memory ``_loaded_rules`` list that the rest
# of the application already consumes. The raw GRS v1 dict is also
# retained in ``_loaded_grs_data`` so future tasks (range/linear/
# lookup evaluation, special-grade behaviors, ...) can read the full
# structure without re-parsing the file.

# Path resolution: every config lookup (``config/gpa_scale.json``,
# ``config/*.txt`` guide, ...) is anchored to the directory that
# holds the running executable / entry-point script. That directory
# is independent of the current working directory, so the same code
# works whether the user launches the app from the project tree, the
# Start menu, a shortcut, or a terminal at an unrelated path. The
# PyInstaller build is expected to ship the ``config/`` folder as a
# user-visible sibling of ``GPA Manager.exe`` (not bundled into
# ``_internal``); the helpers below resolve to that sibling location
# in both source and packaged runs.
#
# Release packaging requirement: every file listed in
# :data:`EXPECTED_CONFIG_FILES` must be present in the ``config/``
# folder that ships alongside the EXE. The JSON scale can be
# regenerated on first run (see :func:`load_gpa_scale`); the two
# language guide text files cannot, so a missing guide file means
# the release is incomplete and the user must restore the entire
# ``config/`` directory from the original distribution.
#
# Bundled resources (the EXE / window ``GPA_Manager.ico``, anything
# else PyInstaller packs into ``_internal/``) resolve through
# :func:`get_internal_path` instead. That helper targets PyInstaller's
# extraction root (``sys._MEIPASS``) so a frozen build reads the
# icon out of ``_internal/GPA_Manager.ico`` instead of expecting it
# next to the EXE.


def get_app_dir() -> pathlib.Path:
    """Return the absolute path of the running application's directory.

    For a PyInstaller-packaged EXE this is the directory that holds
    ``GPA Manager.exe`` (``sys.executable``'s parent). For a source
    run (``python gui.py``) it is the directory that holds this
    module (the project root). The returned path never depends on
    the current working directory.
    """
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parent


def get_internal_path(relative_path: str | pathlib.Path) -> pathlib.Path:
    """Resolve ``relative_path`` against PyInstaller's ``_internal/``.

    For a frozen EXE, PyInstaller unpacks its data bundle into the
    temp directory exposed by ``sys._MEIPASS`` and conventionally
    surfaces it under ``<app_dir>/_internal/``. For a source run
    (``python gui.py``), this helper falls back to
    :func:`get_app_dir` so the same call site reads the file from
    the project tree.

    Use this for resources that PyInstaller bundles into the EXE
    (icons, default configs that ship read-only, ...) rather than
    for files that ship as external siblings of the EXE - those go
    through :func:`get_resource_path`.
    """
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return pathlib.Path(bundle_root) / relative_path
    return get_app_dir() / relative_path


def get_resource_path(relative_path: str | pathlib.Path) -> pathlib.Path:
    """Resolve ``relative_path`` against :func:`get_app_dir`.

    Single shared entry point used by every config-file lookup so the
    layout (``config/gpa_scale.json``, ``config/*.txt`` guides, ...)
    lives alongside the EXE/script as a user-visible folder, both
    during development and after PyInstaller packaging. The resolved
    path is writable in both modes, so writes (e.g. auto-creating
    the default scale on first run) persist for the user.
    """
    return get_app_dir() / relative_path


_GPA_SCALE_PATH: Final[pathlib.Path] = get_resource_path("config") / "gpa_scale.json"


# Every file the application expects inside the external ``config/``
# directory next to the EXE / entry-point script. Listed explicitly
# so the release requirement is visible in code: when packaging a
# PyInstaller build, the entire ``config/`` folder (this JSON scale
# plus both language guides) must be placed next to ``GPA
# Manager.exe``; the app reads them all through
# :func:`get_resource_path`, so any future "open guide" feature can
# address them by name through this single constant.
EXPECTED_CONFIG_FILES: Final[tuple[str, ...]] = (
    "gpa_scale.json",
    "GPA_Rules_Guide_English.txt",
    "GPA_Rules_Guide_Traditional_Chinese.txt",
)


def _missing_config_files() -> list[pathlib.Path]:
    """Return paths to any expected config files that are absent.

    Used as a release / packaging sanity check. Empty list when
    every file in :data:`EXPECTED_CONFIG_FILES` is present. Every
    returned path is the same absolute path the runtime would use to
    load that file, so callers can hand them straight to
    ``print()`` or to the existing GPA-Rules "open in editor"
    helper when one of the guides needs to be recovered.
    """
    config_dir = get_resource_path("config")
    return [
        config_dir / name
        for name in EXPECTED_CONFIG_FILES
        if not (config_dir / name).exists()
    ]

# Built-in default scale in GRS v1 format. Used as the source of
# truth both for the auto-generated config file (on first run) and
# as the in-memory fallback when the user's config is invalid.
#
# GRS v1 structure (data only - no formulas, no scripts):
#
#   metadata            required - school identity + schema version
#   supported_inputs    required - on/off flags per input category
#   numeric             required - numeric-score rules, mode = range
#                                 | linear | lookup. Only ``range`` is
#                                 normalised into ``_loaded_rules`` at
#                                 this stage; ``linear`` / ``lookup``
#                                 land later.
#   text                optional - {text-grade: gpa}
#   letter              optional - {letter-grade: gpa}
#   special             optional - {mark: behavior} where behavior is
#                                 ``"exclude"`` or ``"zero"``.
#
# The numbers below mirror the previous default: A+ through F on a
# 4.0 scale, with numeric range 0-100, plus the Chinese text grades
# 优秀 / 良好 / 中等 / 及格 that the previous alias lists already
# carried.
_DEFAULT_GPA_SCALE: Final[dict] = {
    "metadata": {
        "school": "GPA Manager Default",
        "country": "Unknown",
        "version": "1.0",
        "gpa_scale": 4.0,
        "description": [
            "==========================================",
            " GPA Manager - Default GRS v1 Configuration",
            "==========================================",
            "",
            "This is the default scale used when no per-school",
            "config/gpa_scale.json is present. Edit metadata,",
            "country, and rules to match your school.",
            "",
            "Numeric scores 0-100 map to letter grades via the",
            "numeric.rules list below. Letter grades A+ through F",
            "and the text grades Excellent/Pass/优秀/良好/中等/及格",
            "are also recognized.",
            "",
            "Save this file and restart GPA Manager to apply.",
            "==========================================",
        ],
    },
    "supported_inputs": {
        "numeric": True,
        "text": True,
        "letter": True,
        "special": False,
    },
    "numeric": {
        "mode": "range",
        "default_min_score": 0,
        "default_max_score": 100,
        "rules": [
            {"name": "A+", "min": 95, "max": 100, "gpa": 4.0},
            {"name": "A-", "min": 90, "max":  94, "gpa": 3.7},
            {"name": "B+", "min": 85, "max":  89, "gpa": 3.3},
            {"name": "B",  "min": 80, "max":  84, "gpa": 3.0},
            {"name": "C+", "min": 75, "max":  79, "gpa": 2.7},
            {"name": "C",  "min": 70, "max":  74, "gpa": 2.3},
            {"name": "C-", "min": 65, "max":  69, "gpa": 2.0},
            {"name": "D",  "min": 60, "max":  64, "gpa": 1.5},
            {"name": "F",  "min":  0, "max":  59, "gpa": 0.0},
        ],
    },
    "text": {
        "Excellent": 4.0,
        "Pass":      2.0,
        "优秀":       4.0,
        "良好":       3.0,
        "中等":       2.3,
        "及格":       1.5,
    },
    "letter": {
        "A+": 4.0,
        "A":  4.0,
        "A-": 3.7,
        "B+": 3.3,
        "B":  3.0,
        "B-": 2.7,
        "C+": 2.7,
        "C":  2.3,
        "C-": 2.0,
        "D":  1.5,
        "F":  0.0,
    },
    "special": {},
}

# Mutable module state populated by :func:`load_gpa_scale`. The
# rest of the app reads ``_loaded_rules`` (the legacy lookup shape
# that ``gpa_calculator.convert_score`` consumes), ``MAX_GPA`` (max
# possible grade point, sourced from ``metadata.gpa_scale``) and
# ``_loaded_name`` (the scale's identifier, sourced from
# ``metadata.school``) on every call so the values stay in sync with
# whatever the loader last produced.
#
# ``_loaded_grs_data`` keeps the raw GRS v1 document the loader last
# accepted so that future tasks (range/linear/lookup evaluation,
# special-grade behaviors, ...) can read the full structure
# without re-parsing the file. It is intentionally private.
#
# ``_loaded_linear`` is populated when ``numeric.mode == "linear"``
# and holds the two anchor points the calculator needs to
# interpolate: ``{min_score, max_score, min_gpa, max_gpa}``. Range /
# lookup / text / letter modes continue to live in ``_loaded_rules``
# - the linear mode is held separately because, unlike a finite
# list of interval rules, a linear mapping is a continuous function
# over ``[min_score, max_score]`` and cannot be flattened into the
# legacy ``{gpa, score_range?}`` shape.
#
# Implementation note: ``_loaded_linear`` is a single dict that the
# loader mutates in place (``clear`` + ``update``) instead of
# reassigning. The dict is bound by reference at import time in
# :mod:`gpa_calculator`, so reassigning the module attribute would
# silently desync the consumer - in-place mutation is the only way
# to guarantee the calculator sees the latest linear-mode params.
# An empty dict means "no linear mode active" (the consumer checks
# truthiness before reading).
_loaded_rules: list[dict] = []
_loaded_name: str = ""  # metadata.school from the loaded config
MAX_GPA: float = 0.0  # Updated at load; 0.0 if no valid scale yet.
_loaded_grs_data: Optional[dict] = None
_loaded_linear: dict = {}


def _default_gpa_scale_dict() -> dict:
    """Return a fresh deep copy of the built-in default GRS v1 scale.

    Each call returns an independent dict tree so the caller can
    mutate the result without affecting the module-level default
    template.
    """
    metadata = _DEFAULT_GPA_SCALE["metadata"]
    supported = _DEFAULT_GPA_SCALE["supported_inputs"]
    numeric = _DEFAULT_GPA_SCALE["numeric"]
    return {
        "metadata": {
            "school":     metadata["school"],
            "country":    metadata["country"],
            "version":    metadata["version"],
            "gpa_scale":  metadata["gpa_scale"],
            "description": list(metadata["description"]),
        },
        "supported_inputs": {
            "numeric": supported["numeric"],
            "text":    supported["text"],
            "letter":  supported["letter"],
            "special": supported["special"],
        },
        "numeric": {
            "mode":               numeric["mode"],
            "default_min_score":  numeric["default_min_score"],
            "default_max_score":  numeric["default_max_score"],
            "rules": [dict(rule) for rule in numeric["rules"]],
        },
        "text":    dict(_DEFAULT_GPA_SCALE["text"]),
        "letter":  dict(_DEFAULT_GPA_SCALE["letter"]),
        "special": dict(_DEFAULT_GPA_SCALE["special"]),
    }


def _is_rule_valid(rule: dict) -> bool:
    """Return True if a single ``numeric.rules`` entry is well-formed.

    Each numeric rule must carry:

    * ``name`` (str)             human-readable label
    * ``min``  (number)           inclusive lower bound
    * ``max``  (number)           inclusive upper bound (>= ``min``)
    * ``gpa``  (number)           grade point for scores in [min, max]
    """
    if not isinstance(rule, dict):
        return False
    if not isinstance(rule.get("name"), str):
        return False
    for key in ("min", "max", "gpa"):
        if key not in rule:
            return False
        try:
            float(rule[key])
        except (TypeError, ValueError):
            return False
    if float(rule["min"]) > float(rule["max"]):
        return False
    return True


def _rules_have_overlap(rules: list[dict]) -> bool:
    """Return True if any two ``numeric.rules`` ranges overlap.

    Rules whose entry is malformed (per :func:`_is_rule_valid`) are
    ignored here; validation runs first so overlapping checks only
    see well-formed ranges. Gaps (no rule covers a particular score)
    are explicitly NOT a failure.
    """
    parsed: list[tuple[float, float]] = []
    for r in rules:
        try:
            parsed.append((float(r["min"]), float(r["max"])))
        except (KeyError, TypeError, ValueError):
            continue
    parsed.sort()
    for i in range(1, len(parsed)):
        if parsed[i][0] <= parsed[i - 1][1]:
            return True
    return False


def _validate_gpa_scale(data: dict) -> bool:
    """Return True if ``data`` conforms to GRS v1.

    Required top-level keys (per the GRS v1 spec): ``metadata`` and
    ``supported_inputs``. The ``numeric``, ``text``, ``letter`` and
    ``special`` sections are tolerated as optional - if present
    they must be well-formed, if absent they are simply skipped.
    """
    if not isinstance(data, dict):
        return False

    # metadata: school, country, version (strings) + gpa_scale (number).
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return False
    for key in ("school", "country", "version"):
        if not isinstance(metadata.get(key), str):
            return False
    try:
        float(metadata.get("gpa_scale"))
    except (TypeError, ValueError):
        return False

    # supported_inputs: dict with bool flags for each input category.
    supported = data.get("supported_inputs")
    if not isinstance(supported, dict):
        return False
    for key in ("numeric", "text", "letter", "special"):
        if not isinstance(supported.get(key), bool):
            return False

    # numeric: must carry ``mode``; ``range`` is the only mode that is
    # fully validated today. ``linear`` and ``lookup`` are accepted but
    # not yet interpreted (per the GRS v1 rollout plan).
    numeric = data.get("numeric")
    if not isinstance(numeric, dict):
        return False
    mode = numeric.get("mode")
    if not isinstance(mode, str):
        return False
    if mode == "range":
        rules = numeric.get("rules")
        if not isinstance(rules, list) or not rules:
            return False
        for r in rules:
            if not _is_rule_valid(r):
                return False
        if _rules_have_overlap(rules):
            return False
    elif mode == "linear":
        # Linear mode requires four numeric anchor fields. The
        # calculator interpolates linearly between ``(min_score,
        # min_gpa)`` and ``(max_score, max_gpa)``, so ``min_score``
        # must not exceed ``max_score``.
        for key in ("min_score", "max_score", "min_gpa", "max_gpa"):
            try:
                float(numeric[key])
            except (KeyError, TypeError, ValueError):
                return False
        if float(numeric["min_score"]) > float(numeric["max_score"]):
            return False
    elif mode == "lookup":
        # Lookup rules are accepted but not yet deeply validated
        # (per the GRS v1 rollout plan).
        pass
    else:
        return False

    # text: {grade_string: gpa_number}; both keys and values are
    # required to be the right type when the section is present.
    text = data.get("text")
    if text is not None:
        if not isinstance(text, dict):
            return False
        for k, v in text.items():
            if not isinstance(k, str):
                return False
            try:
                float(v)
            except (TypeError, ValueError):
                return False

    # letter: same shape as ``text``.
    letter = data.get("letter")
    if letter is not None:
        if not isinstance(letter, dict):
            return False
        for k, v in letter.items():
            if not isinstance(k, str):
                return False
            try:
                float(v)
            except (TypeError, ValueError):
                return False

    # special: {mark: behavior_string}; only ``"exclude"`` and
    # ``"zero"`` are recognised behaviors in GRS v1.
    special = data.get("special")
    if special is not None:
        if not isinstance(special, dict):
            return False
        for k, v in special.items():
            if not isinstance(k, str) or not isinstance(v, str):
                return False
            if v not in ("exclude", "zero"):
                return False

    return True


def _write_default_scale(path: pathlib.Path) -> None:
    """Create ``path``'s parent directory if needed and write the
    built-in default scale JSON. The output is human-readable so the
    user can edit it without fighting the on-disk format.

    Probes the parent path first: ``mkdir(parents=True,
    exist_ok=True)`` raises FileExistsError on Python 3.12+ when the
    parent already exists as a *file* (not a directory). The probe lets
    the loader surface a clean OSError to its caller.
    """
    parent = path.parent
    if parent.exists() and not parent.is_dir():
        raise FileExistsError(
            f"cannot create config directory under {parent}: "
            f"a file already exists at that path"
        )
    parent.mkdir(parents=True, exist_ok=True)
    data = _default_gpa_scale_dict()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")


def load_gpa_scale(config_path: Optional[pathlib.Path] = None) -> bool:
    """Load the GRS v1 GPA scale from disk into module state.

    Behaviour:
        * If the file does not exist, it is auto-generated with the
          built-in default (in GRS v1 format) and then loaded.
        * If the file is invalid (bad JSON, missing required GRS v1
          sections, malformed rules, or overlapping ranges) the
          built-in default scale is used **in memory** and a warning
          is printed to the console. The on-disk file is left
          untouched so the user can fix it.
        * The function never raises - the application is guaranteed
          to have a usable GPA scale after this call returns.

    After a successful load the module exposes:

        * ``_loaded_rules``     legacy ``{gpa, score_range?, aliases?}``
                                list that ``gpa_calculator.convert_score``
                                already consumes. Numeric range rules
                                become ``{gpa, score_range}`` entries;
                                each ``text`` and ``letter`` mapping
                                becomes ``{gpa, aliases: (key,)}``.
        * ``_loaded_grs_data``  the raw GRS v1 dict - metadata,
                                supported_inputs, numeric, text,
                                letter, special - so future tasks can
                                implement range / linear / lookup and
                                special-grade behaviors without
                                re-parsing the file.
        * ``MAX_GPA``           sourced from ``metadata.gpa_scale``.
        * ``_loaded_name``      sourced from ``metadata.school``.

    Args:
        config_path: Optional override for the config file path. When
            omitted, the default ``<project>/config/gpa_scale.json``
            is used.

    Returns:
        ``True`` if a config file was loaded from disk; ``False`` if
        the in-memory default was used as a fallback.
    """
    global _loaded_rules, MAX_GPA, _loaded_name, _loaded_grs_data, _loaded_linear
    path = config_path or _GPA_SCALE_PATH

    if not path.exists():
        # First run: emit the default file and load it. A write
        # failure here still leaves us with a usable in-memory default
        # below, so the app keeps working.
        try:
            _write_default_scale(path)
        except OSError as e:
            print(f"Warning: could not write default GPA scale file at "
                  f"{path}: {e}")
            print("Using built-in default GPA scale in memory.")

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: could not read GPA scale config at {path}: {e}")
            print("Using built-in default GPA scale in memory.")
            data = _default_gpa_scale_dict()
        else:
            if not _validate_gpa_scale(data):
                print(f"Warning: GPA scale config at {path} is invalid "
                      "(missing required GRS v1 sections, malformed "
                      "rules, or overlapping ranges).")
                print("Using built-in default GPA scale in memory.")
                data = _default_gpa_scale_dict()
    else:
        # Disk write failed and the file does not exist; fall back
        # entirely to the in-memory default.
        data = _default_gpa_scale_dict()

    # Keep the raw GRS v1 document so future tasks can consume the
    # full structure (range / linear / lookup parameters, special
    # behaviors, ...) without re-reading the file.
    _loaded_grs_data = data

    # Project the GRS v1 structure into the legacy ``_loaded_rules``
    # shape so :func:`gpa_calculator.convert_score` and any other
    # consumer keeps working unchanged. Linear mode lives in
    # ``_loaded_linear`` (a separate, parallel field) because it is
    # a continuous function, not a finite list of interval rules.
    _loaded_rules.clear()
    _loaded_linear.clear()  # mutate in place; see module-state comment.
    if isinstance(data, dict):
        numeric = data.get("numeric")
        if isinstance(numeric, dict):
            mode = numeric.get("mode")
            if mode == "range":
                rules = numeric.get("rules")
                if isinstance(rules, list):
                    for rule in rules:
                        if not _is_rule_valid(rule):
                            continue
                        _loaded_rules.append({
                            "gpa": float(rule["gpa"]),
                            "score_range": (
                                float(rule["min"]), float(rule["max"]),
                            ),
                        })
            elif mode == "linear":
                try:
                    _loaded_linear.update({
                        "min_score": float(numeric["min_score"]),
                        "max_score": float(numeric["max_score"]),
                        "min_gpa":   float(numeric["min_gpa"]),
                        "max_gpa":   float(numeric["max_gpa"]),
                    })
                except (KeyError, TypeError, ValueError):
                    # Validator should have rejected this, but stay
                    # defensive in case the validator is bypassed.
                    _loaded_linear.clear()
        text = data.get("text")
        if isinstance(text, dict):
            for key, value in text.items():
                try:
                    _loaded_rules.append({
                        "gpa": float(value),
                        "aliases": (str(key),),
                    })
                except (TypeError, ValueError):
                    continue
        letter = data.get("letter")
        if isinstance(letter, dict):
            for key, value in letter.items():
                try:
                    _loaded_rules.append({
                        "gpa": float(value),
                        "aliases": (str(key),),
                    })
                except (TypeError, ValueError):
                    continue

    # MAX_GPA from metadata.gpa_scale.
    metadata = data.get("metadata") if isinstance(data, dict) else None
    if not isinstance(metadata, dict):
        metadata = {}
    try:
        MAX_GPA = float(metadata.get("gpa_scale", 0.0))
    except (TypeError, ValueError):
        MAX_GPA = 0.0

    # _loaded_name from metadata.school so the About dialog can
    # surface whatever the user (or the default) configured.
    _loaded_name = str(metadata.get("school", "") or "")
    return True


def get_max_gpa() -> float:
    """Return the loaded max_gpa value (0.0 if not yet loaded)."""
    return MAX_GPA


def get_scale_name() -> str:
    """Return the loaded GPA scale's ``name`` field.

    This is whatever the on-disk ``config/gpa_scale.json`` declared
    (or the built-in default if the loader fell back to it). The
    About dialog uses this so the displayed name always reflects the
    file the user is actually editing.
    """
    return _loaded_name


def get_loaded_rules() -> list[dict]:
    """Return a snapshot of the currently-loaded numeric rules.

    Each rule is a fresh dict ``{"min": float, "max": float, "gpa":
    float}``. The list is a copy; mutating it does not affect the
    loader state.
    """
    return list(_loaded_rules)
