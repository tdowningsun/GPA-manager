"""Graphical user interface for GPA Manager v4.1.

v4.0 changes over v3.2:
    * UI architecture refactor: introduce a fixed left sidebar and a
      right-side workspace that hosts one page at a time.
    * The full v3.2 calculator is moved into :class:`SingleSemesterPage`
      unchanged in behaviour.
    * Sidebar width / padding tuned so all nav labels render fully.

v4.0.1 changes over v4.0:
    * Layout stability: sidebar is locked at ``SIDEBAR_WIDTH`` and a
      20px gap with a 1px divider sits between the sidebar and the
      workspace (see ``MainWindow._build_gap``).
    * :class:`MultiSemesterPage` redesigned to mirror
      :class:`SingleSemesterPage`'s layout - title, form, semester
      list (Semester / Credits / GPA), management row, and Overall
      GPA display.
    * :class:`MultiSemesterPage` basic data management: ``Add
      Semester`` and ``Delete Selected Semester`` mutate
      ``self._semesters`` and refresh the table; ``Overall GPA`` is
      the weighted average of all semester GPAs.

v4.0.2 changes over v4.0.1:
    * :class:`TargetGpaPage` redesigned to mirror the other two pages
      - title, ``Target Inputs`` form (Current GPA, Completed Credits,
      Remaining Credits, Target GPA), ``Calculate`` button, separator,
      ``Required GPA`` result card, and a status line.
    * ``Calculate`` is wired up: validates all four inputs, computes
      the required GPA via
      ``(target*(done+remaining) - current*done) / remaining``, and
      refreshes the result card. Three outcomes are surfaced - target
      already achieved, target reachable, target out of reach (>=
      :data:`~data.MAX_GPA`).
    * :data:`~data.MAX_GPA` exported from :mod:`data` (derived from
      :data:`~data.SCORE_RANGES`) so the validation has a single
      source of truth.

v4.1 changes over v4.0.2 (UI polish):
    * Standardized button widths via :data:`PRIMARY_BUTTON_WIDTH` and
      :data:`MANAGEMENT_BUTTON_WIDTH` so all action buttons across all
      three pages share the same width.
    * Standardized form padding via :data:`FORM_PADX_INNER` /
      :data:`FORM_PADX_RIGHT` so entry columns look the same on every
      page.
    * Unified Treeview column widths via :data:`TABLE_COLUMN_WIDTH`.
    * :class:`SingleSemesterPage` and :class:`MultiSemesterPage` now
      wrap their result area in a ``LabelFrame`` "Overall GPA" card
      so all three pages have the same card-style result section.
    * :class:`TargetGpaPage`'s ``Required GPA`` card uses
      :data:`FONT_DISPLAY` and :data:`RESULT_CARD_PADDING` so the
      answer reads as the page's main result, not just another row.

The window is laid out as:

    +-----------+----+-------------------------------------+
    | Sidebar   |g+dv| Workspace                           |
    |  brand    |    |   active page                       |
    |  nav: ... |    |                                     |
    +-----------+----+-------------------------------------+

All pages share the same grid cell; only the active page is shown via
``tkraise`` so switching is instant and never opens a new window.

Layers (top-down inside :mod:`gui`):

    * Validation helpers (:func:`_validate_course_fields`,
      :func:`_focus_from_error`) - shared between add and edit.
    * DPI plumbing (:func:`_enable_windows_dpi_awareness`,
      :func:`_sync_tk_scaling`, :func:`_configure_styles`).
    * :class:`CourseEditDialog` - the modal edit dialog.
    * :class:`Sidebar` - fixed-width navigation column.
    * Page classes - :class:`SingleSemesterPage`,
      :class:`MultiSemesterPage`, :class:`TargetGpaPage`.
    * :class:`MainWindow` - top-level coordinator that owns the
      sidebar + the workspace and routes navigation events.
"""

import ctypes
import os
import pathlib
import platform
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

from data import Course, Semester
import data  # for data.MAX_GPA / data.get_max_gpa() / data.get_scale_name()
from gpa_calculator import calculate_gpa, convert_score
from i18n import (
    AVAILABLE_LOCALES,
    LOCALE_EN,
    LOCALE_ZH_TW,
    add_listener,
    current_locale,
    current_locale_label,
    remove_listener,
    set_locale,
    t,
    t_values,
)

# ----------------------------------------------------------------------
# Layout constants
# ----------------------------------------------------------------------

APP_TITLE = "GPA Manager"
WINDOW_SIZE = "840x720"
MIN_WIDTH = 1140
MIN_HEIGHT = 880

# Main-window paddings / input widths.
INPUT_PADDING = 12
SECTION_PADDING = 14
NAME_ENTRY_WIDTH = 30
SHORT_ENTRY_WIDTH = 10

# Sidebar.
SIDEBAR_WIDTH = 220
SIDEBAR_GAP = 20
SIDEBAR_BG = "#f0f0f0"
SIDEBAR_SELECTED_BG = "#d0d0d0"
DIVIDER_COLOR = "#d0d0d0"
# Softer text color for the bottom utility actions (GPA Rules...,
# Language..., About) so they read as secondary actions beneath the
# main navigation. Picked for clear contrast on ``SIDEBAR_BG`` while
# feeling lighter than the main-nav ``#202020``.
SIDEBAR_UTILITY_FG = "#5a5a5a"

# Result-card internal padding. Slightly more generous than
# ``INPUT_PADDING`` so the result cards feel like distinct cards rather
# than regular form sections.
RESULT_CARD_PADDING = 16

# Button widths. Both the primary action buttons (Add, Calculate) and
# the management row buttons (Edit / Delete / Clear, Open / Rename /
# Delete) share the same width so visually related controls line up
# across all three pages.
PRIMARY_BUTTON_WIDTH = 16
MANAGEMENT_BUTTON_WIDTH = 16

# Per-column inner padding inside form grids.
FORM_PADX_INNER: tuple[int, int] = (12, 12)   # between label and entry
FORM_PADX_RIGHT: tuple[int, int] = (12, 0)    # rightmost column (button)

# Courses Treeview.
TABLE_COLUMNS: tuple[str, ...] = ("name", "credit", "score", "point")
TABLE_HEADINGS: dict[str, str] = {
    "name": "Course Name",
    "credit": "Credit",
    "score": "Score",
    "point": "Grade Point",
}
TABLE_VISIBLE_ROWS = 10
TREE_ROW_PIXEL_HEIGHT = 30
TABLE_COLUMN_WIDTH = 140   # shared with Multi Semester table

# Edit dialog.
DIALOG_TITLE = "Edit Course"
DIALOG_PADDING = 16

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
#
# The whole application uses a single three-level type system:
#
#   * :data:`FONT_BODY`    - default 10pt regular text. Used for
#     labels, buttons, entries, the Treeview body, sidebar nav items,
#     the language-menu label, dialog text and status lines.
#   * :data:`FONT_HEADING` - 12pt bold. Used for page titles, section
#     titles (the text on every ``LabelFrame``), the sidebar brand,
#     the result-card title, and the Treeview column headings.
#   * :data:`FONT_DISPLAY` - 18pt bold. Reserved for numerical
#     highlights only - the per-semester GPA value, the Single
#     Semester "Overall GPA" value, and the Target Required GPA
#     value. Nothing else uses this size.
#
# Every page (and the sidebar) reads these same three names, so the
# application is visually consistent without per-section font tweaks.
#
# The family fallback chain is shared across all three levels so a
# user without a Traditional-Chinese glyph in Segoe UI still gets
# Microsoft JhengHei (then Microsoft YaHei) for Chinese characters.
_FONT_FAMILY: tuple[str, ...] = (
    "Segoe UI", "Microsoft JhengHei", "Microsoft YaHei",
)
# Module-level font references. Each is set to a real ``tkfont.Font``
# object (with the family fallback chain above) by :func:`_init_fonts`
# right after the Tk root is created, before any page widgets are
# constructed. Widgets that read ``gui.FONT_BODY`` etc. always see
# the current Font object - there is no per-page font definition.
#
# The three "main" levels (BODY / HEADING / DISPLAY) cover every page
# and dialog. A fourth, sidebar-only level -- FONT_UTILITY -- is
# two points smaller than BODY so the bottom-of-sidebar items read as
# secondary actions, without affecting the rest of the typography.
FONT_BODY: Any = None
FONT_HEADING: Any = None
FONT_DISPLAY: Any = None
FONT_UTILITY: Any = None

# Application version. Surfaced by the About dialog. Bump this whenever
# behaviour-visible changes ship.
__version__ = "4.6.0"


def _center_dialog_on_parent(dialog: tk.Toplevel, parent: tk.Misc) -> None:
    """Center ``dialog`` over ``parent``.

    Used by all modal dialogs in the app (CourseEditDialog,
    SemesterEditorDialog, AboutDialog). The caller can pass any
    widget -- including a sub-frame like the sidebar -- and the
    helper will center the dialog relative to that widget's
    bounding box. AboutDialog passes the toplevel explicitly so the
    dialog always centers on the main application window, not on
    a sidebar sub-frame.
    """
    dialog.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() - dialog.winfo_width()) // 2
    y = parent.winfo_y() + (parent.winfo_height() - dialog.winfo_height()) // 2
    dialog.geometry(f"+{x}+{y}")


def _init_fonts() -> None:
    """Create the four centralized fonts with the family-fallback chain.

    Called once from :func:`main` after the Tk root exists, before
    :class:`MainWindow` is constructed so every page widget picks up
    the real Font objects.
    """
    global FONT_BODY, FONT_HEADING, FONT_DISPLAY, FONT_UTILITY
    FONT_BODY = tkfont.Font(family=_FONT_FAMILY, size=10)
    FONT_HEADING = tkfont.Font(family=_FONT_FAMILY, size=12, weight="bold")
    FONT_DISPLAY = tkfont.Font(family=_FONT_FAMILY, size=18, weight="bold")
    # Sidebar-only level: two points smaller than BODY so the bottom
    # utility actions read as secondary actions.
    FONT_UTILITY = tkfont.Font(family=_FONT_FAMILY, size=8)

# Page identifiers used by Sidebar and MainWindow.
PAGE_SINGLE = "single"
PAGE_MULTI = "multi"
PAGE_TARGET = "target"
PAGE_LABELS: dict[str, str] = {
    PAGE_SINGLE: "Single Semester",
    PAGE_MULTI: "Multi-Semester",
    PAGE_TARGET: "Target GPA",
}


# ----------------------------------------------------------------------
# Validation (shared by Add and Edit)
# ----------------------------------------------------------------------


def _validate_course_fields(
    name: str,
    credit_raw: str,
    score: str,
) -> tuple[Optional[Course], Optional[tuple[str, dict]]]:
    """Parse and validate course input fields.

    Returns ``(course, None)`` on success or
    ``(None, (error_key, format_kwargs))`` on failure. The error key
    is one of the ``validation.*`` keys in :mod:`i18n`; callers display
    the message via ``t(error_key, **format_kwargs)`` so it follows the
    active locale. The key also lets :func:`_focus_from_error` move
    keyboard focus to the right field.
    """
    if not name:
        return None, ("validation.name_empty", {})
    try:
        credit = float(credit_raw)
    except ValueError:
        return None, ("validation.credit_invalid", {"value": credit_raw})
    if credit <= 0:
        return None, ("validation.credit_non_positive", {})
    point = convert_score(score)
    if point is None:
        return None, ("validation.score_invalid", {"value": score})
    course: Course = {
        "name": name,
        "credit": credit,
        "score": score,
        "point": point,
    }
    return course, None


# Maps a validation error key to which form field should receive
# keyboard focus. Keys mirror the validation strings in i18n.py.
_FOCUS_FIELD_FOR_KEY: dict[str, str] = {
    "validation.name_empty": "name",
    "validation.credit_invalid": "credit",
    "validation.credit_non_positive": "credit",
    "validation.score_invalid": "score",
}


def _focus_from_error(
    error_key: str,
    name_entry: ttk.Entry,
    credit_entry: ttk.Entry,
    score_entry: ttk.Entry,
) -> None:
    """Move focus to the entry identified by ``error_key``.

    Looks the key up in :data:`_FOCUS_FIELD_FOR_KEY` so the same
    i18n keys drive both the user-visible error message and the
    focus-routing decision - no string matching on the translated
    text.
    """
    field = _FOCUS_FIELD_FOR_KEY.get(error_key)
    if field == "name":
        name_entry.focus_set()
    elif field == "credit":
        credit_entry.focus_set()
    elif field == "score":
        score_entry.focus_set()


# ----------------------------------------------------------------------
# DPI & style configuration
# ----------------------------------------------------------------------


def _enable_windows_dpi_awareness() -> None:
    """Enable Per-Monitor V2 DPI awareness on Windows."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def _sync_tk_scaling(root: tk.Tk) -> None:
    """Force Tk's internal scaling to match the reported screen DPI."""
    try:
        pixels_per_inch = root.winfo_fpixels("1i")
        root.tk.call("tk", "scaling", pixels_per_inch / 72.0)
    except tk.TclError:
        pass


def _configure_styles(root: tk.Tk) -> None:
    """Apply a clean, consistent ttk style across the application."""
    style = ttk.Style(root)

    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure(".", font=FONT_BODY)
    style.configure("TLabel", font=FONT_BODY)
    style.configure("TButton", font=FONT_BODY, padding=(14, 8))
    style.configure("TEntry", padding=(8, 6))
    style.configure("TLabelframe", font=FONT_HEADING, padding=(12, 8))
    style.configure("TLabelframe.Label", font=FONT_HEADING)
    style.configure(
        "Treeview",
        font=FONT_BODY,
        rowheight=TREE_ROW_PIXEL_HEIGHT,
    )
    style.configure("Treeview.Heading", font=FONT_HEADING, padding=(10, 6))


# ----------------------------------------------------------------------
# Edit dialog (unchanged from v3.2)
# ----------------------------------------------------------------------


class CourseEditDialog:
    """Modal dialog for editing a single course record."""

    def __init__(self, parent: tk.Tk, course: Course) -> None:
        self.result: Optional[Course] = None

        self._dialog = tk.Toplevel(parent)
        # Title is set once at construction; this dialog is short-lived
        # so it does not need to subscribe to locale-change events.
        self._dialog.title(t("dialog.edit_course.title"))
        self._dialog.transient(parent)
        self._dialog.resizable(False, False)

        self._name_var = tk.StringVar(value=course["name"])
        self._credit_var = tk.StringVar(value=str(course["credit"]))
        self._score_var = tk.StringVar(value=course["score"])
        self._status_var = tk.StringVar()

        self._build_ui()
        self._center_on(parent)
        self._dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        self._dialog.grab_set()
        self._name_entry.focus_set()
        self._name_entry.select_range(0, tk.END)

    @property
    def window(self) -> tk.Toplevel:
        """The underlying Toplevel widget (for ``wait_window`` etc.)."""
        return self._dialog

    def _build_ui(self) -> None:
        frame = ttk.Frame(self._dialog, padding=DIALOG_PADDING)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=t("form.label.course_name")).grid(
            row=0, column=0, sticky=tk.W, pady=4
        )
        self._name_entry = ttk.Entry(
            frame, textvariable=self._name_var, width=NAME_ENTRY_WIDTH
        )
        self._name_entry.grid(row=0, column=1, sticky=tk.EW, pady=4, padx=(12, 0))

        ttk.Label(frame, text=t("form.label.credit")).grid(
            row=1, column=0, sticky=tk.W, pady=4
        )
        self._credit_entry = ttk.Entry(
            frame, textvariable=self._credit_var, width=SHORT_ENTRY_WIDTH
        )
        self._credit_entry.grid(row=1, column=1, sticky=tk.EW, pady=4, padx=(12, 0))

        ttk.Label(frame, text=t("form.label.score")).grid(
            row=2, column=0, sticky=tk.W, pady=4
        )
        self._score_entry = ttk.Entry(
            frame, textvariable=self._score_var, width=SHORT_ENTRY_WIDTH
        )
        self._score_entry.grid(row=2, column=1, sticky=tk.EW, pady=4, padx=(12, 0))

        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, textvariable=self._status_var).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=(8, 0)
        )

        button_row = ttk.Frame(frame)
        button_row.grid(row=4, column=0, columnspan=2, pady=(8, 0), sticky=tk.EW)

        self._cancel_button = ttk.Button(
            button_row, command=self._cancel, width=12
        )
        self._cancel_button.configure(text=t("button.cancel"))
        self._cancel_button.pack(side=tk.RIGHT)
        self._save_button = ttk.Button(
            button_row, command=self._save, width=12
        )
        self._save_button.configure(text=t("button.save"))
        self._save_button.pack(side=tk.RIGHT, padx=(0, 8))

        self._dialog.bind("<Return>", lambda _e: self._save())
        self._dialog.bind("<Escape>", lambda _e: self._cancel())

    def _center_on(self, parent: tk.Tk) -> None:
        """Center the dialog over the parent window.

        Thin wrapper around the shared :func:`_center_dialog_on_parent`
        helper, kept as a method so dialogs can self-locate without
        having to know the helper's module-level name.
        """
        _center_dialog_on_parent(self._dialog, parent)

    def _save(self) -> None:
        name = self._name_var.get().strip()
        credit_raw = self._credit_var.get().strip()
        score = self._score_var.get().strip()

        course, error = _validate_course_fields(name, credit_raw, score)
        if error:
            error_key, error_args = error
            self._status_var.set(t(error_key, **error_args))
            _focus_from_error(
                error_key, self._name_entry, self._credit_entry, self._score_entry
            )
            return

        self.result = course
        self._dialog.destroy()

    def _cancel(self) -> None:
        self.result = None
        self._dialog.destroy()


class SemesterEditorDialog:
    """Modal dialog for editing a single semester's course list.

    Mirrors :class:`CourseEditDialog` (modal Toplevel + grab_set +
    ``<Return>``/``<Escape>`` keybindings + ``protocol`` for window-close
    handling). The dialog maintains its own copy of the course list so
    that cancelling does not mutate the parent's data; on Save the
    dialog writes the local course list together with the
    recomputed ``credits`` and ``gpa`` back into the parent's
    :class:`~data.Semester` dict (passed by reference) and returns
    ``True``.
    """

    def __init__(
        self,
        parent: tk.Tk,
        semester: Semester,
        semester_index: int,
    ) -> None:
        # ``True`` if the user saved, ``None`` if cancelled.
        self.result: Optional[bool] = None

        self._dialog = tk.Toplevel(parent)
        # Title includes the semester name. The dialog is short-lived
        # so we don't subscribe to locale changes for the title.
        self._dialog.title(
            t("dialog.edit_semester.title", name=semester["name"])
        )
        self._dialog.transient(parent)
        self._dialog.resizable(True, True)
        self._dialog.minsize(580, 500)

        # Reference to the parent's Semester dict; we mutate it in
        # place on Save so the parent does not need to re-insert it.
        self._semester = semester
        # Kept for status messages on the parent after Save.
        self._semester_index = semester_index

        # Local course list (a copy so cancelling leaves the parent's
        # data untouched).
        self._courses: list[Course] = list(semester.get("courses", []))

        # Widget state.
        self._course_name_var = tk.StringVar()
        self._credit_var = tk.StringVar()
        self._score_var = tk.StringVar()
        self._status_var = tk.StringVar(value=t("status.add_course.begin"))
        self._credits_var = tk.StringVar(value="0.0")
        self._gpa_var = tk.StringVar(value="0.00")

        self._build_ui()
        self._center_on(parent)
        self._dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        self._dialog.grab_set()
        self._course_name_entry.focus_set()

    @property
    def window(self) -> tk.Toplevel:
        """The underlying Toplevel widget (for ``wait_window`` etc.)."""
        return self._dialog

    def _build_ui(self) -> None:
        """Assemble the dialog: title, add-course form, course table,
        live credits/GPA summary, Save / Cancel buttons."""
        frame = ttk.Frame(self._dialog, padding=DIALOG_PADDING)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title: semester name (read-only - rename is a separate feature).
        ttk.Label(
            frame,
            text=self._semester["name"],
            font=FONT_HEADING,
        ).grid(row=0, column=0, columnspan=5, sticky=tk.W, pady=(0, 12))

        # Row 1: Course Name label + entry (spans cols 1-4).
        ttk.Label(frame, text=t("form.label.course_name")).grid(
            row=1, column=0, sticky=tk.W, pady=4
        )
        self._course_name_entry = ttk.Entry(
            frame, textvariable=self._course_name_var, width=NAME_ENTRY_WIDTH
        )
        self._course_name_entry.grid(
            row=1, column=1, columnspan=4, sticky=tk.EW, pady=4, padx=(12, 0)
        )

        # Row 2: Credit | Score | Add Course button.
        ttk.Label(frame, text=t("form.label.credit")).grid(
            row=2, column=0, sticky=tk.W, pady=4
        )
        self._credit_entry = ttk.Entry(
            frame, textvariable=self._credit_var, width=SHORT_ENTRY_WIDTH
        )
        self._credit_entry.grid(
            row=2, column=1, sticky=tk.EW, pady=4, padx=(12, 12)
        )
        ttk.Label(frame, text=t("form.label.score")).grid(
            row=2, column=2, sticky=tk.W, pady=4
        )
        self._score_entry = ttk.Entry(
            frame, textvariable=self._score_var, width=SHORT_ENTRY_WIDTH
        )
        self._score_entry.grid(
            row=2, column=3, sticky=tk.EW, pady=4, padx=(12, 12)
        )
        self._add_course_button = ttk.Button(
            frame, command=self._on_add_course, width=PRIMARY_BUTTON_WIDTH
        )
        self._add_course_button.configure(text=t("button.add_course"))
        self._add_course_button.grid(
            row=2, column=4, sticky=tk.EW, pady=4, padx=(12, 0)
        )

        # Status line under the form.
        ttk.Label(
            frame, textvariable=self._status_var
        ).grid(row=3, column=0, columnspan=5, sticky=tk.W, pady=(8, 8))

        # Course list table (mirrors Single Semester's Course List).
        tree_container = ttk.Frame(frame)
        tree_container.grid(
            row=4, column=0, columnspan=5, sticky="nsew", pady=(0, 8)
        )

        self._inner_tree = ttk.Treeview(
            tree_container,
            columns=TABLE_COLUMNS,
            show="headings",
            height=8,
        )
        for column_id, heading_key in _COURSE_HEADING_KEYS_FOR_DIALOG.items():
            self._inner_tree.heading(column_id, text=t(heading_key))
            if column_id == "name":
                anchor = tk.W
                stretch = True
            else:
                anchor = tk.E
                stretch = False
            self._inner_tree.column(
                column_id,
                width=TABLE_COLUMN_WIDTH,
                anchor=anchor,
                stretch=stretch,
            )

        scrollbar = ttk.Scrollbar(
            tree_container, orient=tk.VERTICAL, command=self._inner_tree.yview
        )
        self._inner_tree.configure(yscrollcommand=scrollbar.set)

        self._inner_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Live credits + GPA summary, so the user sees what they're
        # about to save.
        summary_frame = ttk.Frame(frame)
        summary_frame.grid(
            row=5, column=0, columnspan=5, sticky=tk.W, pady=(0, 8)
        )
        ttk.Label(
            summary_frame,
            text=t("dialog.summary.credits_label"),
            font=FONT_HEADING,
        ).pack(side=tk.LEFT)
        ttk.Label(
            summary_frame,
            textvariable=self._credits_var,
            font=FONT_HEADING,
            padding=(6, 0, 24, 0),
        ).pack(side=tk.LEFT)
        ttk.Label(
            summary_frame,
            text=t("dialog.summary.gpa_label"),
            font=FONT_HEADING,
        ).pack(side=tk.LEFT)
        ttk.Label(
            summary_frame,
            textvariable=self._gpa_var,
            font=FONT_DISPLAY,
            padding=(6, 0, 0, 0),
        ).pack(side=tk.LEFT)

        # Button row: Cancel | Save.
        button_row = ttk.Frame(frame)
        button_row.grid(row=6, column=0, columnspan=5, sticky=tk.EW)

        self._cancel_button = ttk.Button(
            button_row, command=self._cancel, width=12
        )
        self._cancel_button.configure(text=t("button.cancel"))
        self._cancel_button.pack(side=tk.RIGHT)
        self._save_button = ttk.Button(
            button_row, command=self._save, width=12
        )
        self._save_button.configure(text=t("button.save"))
        self._save_button.pack(side=tk.RIGHT, padx=(0, 8))

        # Column weights and row growth.
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.rowconfigure(4, weight=1)

        # Initial display - reflect the courses that were already on
        # the semester when the dialog opened.
        self._refresh_inner_table()
        self._recalculate()

        # Key bindings (same pattern as CourseEditDialog).
        self._dialog.bind("<Return>", lambda _e: self._on_add_course())
        self._dialog.bind("<Escape>", lambda _e: self._cancel())

    def _center_on(self, parent: tk.Tk) -> None:
        """Center the dialog over the parent window."""
        self._dialog.update_idletasks()
        x = parent.winfo_x() + (
            parent.winfo_width() - self._dialog.winfo_width()
        ) // 2
        y = parent.winfo_y() + (
            parent.winfo_height() - self._dialog.winfo_height()
        ) // 2
        self._dialog.geometry(f"+{x}+{y}")

    def _on_add_course(self) -> None:
        """Validate the three input fields and append a course."""
        name = self._course_name_var.get().strip()
        credit_raw = self._credit_var.get().strip()
        score = self._score_var.get().strip()

        course, error = _validate_course_fields(name, credit_raw, score)
        if error:
            error_key, error_args = error
            self._status_var.set(t(error_key, **error_args))
            _focus_from_error(
                error_key,
                self._course_name_entry,
                self._credit_entry,
                self._score_entry,
            )
            return

        self._courses.append(course)
        self._refresh_inner_table()
        self._recalculate()
        self._clear_input_fields()
        self._set_status(t("status.added", name=course["name"]))

    def _clear_input_fields(self) -> None:
        """Reset the three input fields and refocus the name entry."""
        self._course_name_var.set("")
        self._credit_var.set("")
        self._score_var.set("")
        self._course_name_entry.focus_set()

    def _refresh_inner_table(self) -> None:
        """Re-render the dialog's Treeview from ``self._courses``."""
        for row_id in self._inner_tree.get_children():
            self._inner_tree.delete(row_id)
        for index, course in enumerate(self._courses):
            self._inner_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    course["name"],
                    f"{course['credit']:.1f}",
                    course["score"],
                    f"{course['point']:.1f}",
                ),
            )

    def _recalculate(self) -> None:
        """Recompute the dialog's live credits + GPA from the local
        course list (uses :func:`gpa_calculator.calculate_gpa`).
        """
        gpa = calculate_gpa(self._courses)
        total_credits = sum(course["credit"] for course in self._courses)
        self._credits_var.set(f"{total_credits:.1f}")
        self._gpa_var.set(f"{gpa:.2f}")

    def _save(self) -> None:
        """Write the local course list + recomputed totals into the
        parent's Semester dict, then close the dialog.

        The parent's list reference (``self._semesters[index]``) is
        unchanged - we mutate the Semester dict in place so any other
        reference to the same dict sees the new values immediately.
        """
        gpa = calculate_gpa(self._courses)
        total_credits = sum(course["credit"] for course in self._courses)
        self._semester["credits"] = total_credits
        self._semester["gpa"] = gpa
        self._semester["courses"] = list(self._courses)
        self.result = True
        self._dialog.destroy()

    def _cancel(self) -> None:
        """Discard any unsaved changes and close the dialog."""
        self.result = None
        self._dialog.destroy()

    def _set_status(self, message: str) -> None:
        """Update the dialog's status line under the add-course form."""
        self._status_var.set(message)


# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------


# Mapping from the active UI locale to the matching guide filename
# under ``config/``. Used by ``Sidebar._open_gpa_rules`` so clicking
# the "GPA Rules..." item opens both ``gpa_scale.json`` and the
# guide for the language the user is currently looking at. Unknown
# locales fall back to English; a missing guide file is silently
# skipped so the JSON's "open error" dialog still works on its own.
_GPA_RULES_GUIDE_BY_LOCALE: dict[str, str] = {
    LOCALE_ZH_TW: "GPA_Rules_Guide_Traditional_Chinese.txt",
    LOCALE_EN: "GPA_Rules_Guide_English.txt",
}


class Sidebar(tk.Frame):
    """Fixed-width left navigation column with one item per page.

    Renders (top to bottom):
        1. The brand label "GPA Manager".
        2. A vertical separator.
        3. The three nav items (Single / Multi / Target) - left-aligned
           labels; the active one is bolded and tinted.
        4. A bottom-aligned language selector showing the current
           locale name. Clicking pops up a menu with every supported
           locale; selecting one calls :func:`i18n.set_locale`, which
           in turn notifies every registered listener so every page's
           translatable text updates in place.
    """

    # Map page_id -> i18n key so locale changes can retranslate nav items.
    _NAV_KEYS: dict[str, str] = {
        PAGE_SINGLE: "nav.single",
        PAGE_MULTI: "nav.multi",
        PAGE_TARGET: "nav.target",
    }

    def __init__(
        self,
        parent: tk.Misc,
        on_navigate: Callable[[str], None],
    ) -> None:
        super().__init__(parent, bg=SIDEBAR_BG, width=SIDEBAR_WIDTH)
        # Keep a reference to the toplevel so AboutDialog can center
        # itself over the main application window rather than this
        # sidebar sub-frame.
        self._root = parent
        self._on_navigate = on_navigate
        self._items: dict[str, tk.Label] = {}
        self._item_keys: dict[str, str] = dict(self._NAV_KEYS)
        self._current_id: Optional[str] = None

        # Don't shrink below the configured width.
        self.pack_propagate(False)

        self._build_brand()
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X)
        self._build_items()

        # Utility section (GPA Rules / Language / About) sits at the
        # bottom of the sidebar so it never moves when the page list
        # grows.
        self._build_utility_section()

        # Refresh everything when the locale changes.
        add_listener(self._refresh_locale)

    def _build_brand(self) -> None:
        self._brand_label = tk.Label(
            self,
            text=t("app.brand"),
            font=FONT_HEADING,
            bg=SIDEBAR_BG,
            fg="#202020",
            anchor=tk.W,
            padx=14,
            pady=18,
        )
        self._brand_label.pack(fill=tk.X)

    def _build_items(self) -> None:
        for page_id, text_key in self._item_keys.items():
            item = tk.Label(
                self,
                text=t(text_key),
                anchor=tk.W,
                padx=16,
                pady=12,
                font=FONT_BODY,
                bg=SIDEBAR_BG,
                fg="#202020",
                cursor="hand2",
            )
            item.pack(fill=tk.X)
            item.bind(
                "<Button-1>", lambda _e, pid=page_id: self.select(pid)
            )
            self._items[page_id] = item

    def _build_utility_section(self) -> None:
        """Build the three lightweight utility items at the bottom of
        the sidebar: GPA Rules..., Language..., About.

        Each item is a plain ``tk.Label`` styled like the nav items so
        the utility section visually blends in with the page
        navigation above it. The current language is *not* displayed
        permanently on any item - the locale identifier lives only
        in the Language menu popup (where it is still marked with
        a checkmark on the active entry).

        The three items are packed in REVERSE order (``side=BOTTOM``
        stacks up from the bottom) so the order top-to-bottom matches
        the spec: GPA Rules..., Language..., About.
        """
        # A short visual separator between the nav items and the
        # utility block so the user reads the sidebar as two
        # semantically distinct regions.
        spacer = tk.Frame(self, bg=SIDEBAR_BG, height=12)
        spacer.pack(side=tk.BOTTOM, fill=tk.X)

        # Pack from bottom up: about, then language, then gpa_rules.
        self._about_item = self._create_utility_item(
            t("sidebar.about"), self._show_about
        )
        self._language_item = self._create_utility_item(
            t("sidebar.language"), self._show_language_menu
        )
        self._gpa_rules_item = self._create_utility_item(
            t("sidebar.gpa_rules"), self._open_gpa_rules
        )

    def _create_utility_item(
        self,
        label_text: str,
        command: Callable[[], None],
    ) -> tk.Label:
        """Create one lightweight sidebar utility item (a plain
        ``tk.Label`` with a ``hand2`` cursor and a ``click`` binding).

        Renders in :data:`SIDEBAR_UTILITY_FG` so the utility section
        reads as secondary actions beneath the main navigation. On
        ``<Enter>`` the foreground switches to the main-nav color
        (``#202020``) so the user gets clear hover feedback; on
        ``<Leave>`` it returns to the softer utility color.
        """
        item = tk.Label(
            self,
            text=label_text,
            bg=SIDEBAR_BG,
            fg=SIDEBAR_UTILITY_FG,
            cursor="hand2",
            anchor=tk.W,
            padx=16,
            pady=8,
            font=FONT_BODY,
            justify=tk.LEFT,
        )
        item.pack(side=tk.BOTTOM, fill=tk.X)
        item.bind("<Button-1>", lambda _e: command())
        item.bind(
            "<Enter>",
            lambda _e: item.configure(fg="#202020"),
        )
        item.bind(
            "<Leave>",
            lambda _e: item.configure(fg=SIDEBAR_UTILITY_FG),
        )
        return item

    def _open_gpa_rules(self) -> None:
        """Open ``config/gpa_scale.json`` (and the matching guide).

        The JSON scale is opened first - if the on-disk file was
        deleted (so the loader fell back to the in-memory default),
        re-create it first so the editor opens something tangible.
        If the JSON itself cannot be opened, surface a friendly
        error dialog.

        After the JSON is handled, the language guide that matches
        the active UI locale is also opened through the same
        :func:`_open_with_default_editor` helper. The path is
        resolved through :func:`data.get_resource_path` so both
        ``python gui.py`` and the PyInstaller build find the file
        alongside the EXE. The guide is informational only - a
        missing guide file is silently ignored so it never blocks
        the JSON's own success / error reporting.
        """
        config_path = data._GPA_SCALE_PATH
        if not config_path.exists():
            try:
                data._write_default_scale(config_path)
            except OSError:
                pass
        if not _open_with_default_editor(config_path):
            messagebox.showerror(
                t("sidebar.gpa_rules.open_error.title"),
                t(
                    "sidebar.gpa_rules.open_error.message",
                    path=str(config_path),
                ),
                parent=self,
            )

        guide_name = _GPA_RULES_GUIDE_BY_LOCALE.get(
            current_locale(), _GPA_RULES_GUIDE_BY_LOCALE[LOCALE_EN],
        )
        guide_path = data.get_resource_path("config") / guide_name
        if guide_path.exists():
            _open_with_default_editor(guide_path)

    def _show_about(self) -> None:
        """Open the modal About dialog with metadata read at runtime."""
        AboutDialog(self._root)

    def _show_language_menu(self, event: Optional[tk.Event] = None) -> None:
        """Pop up the locale-selection menu at the click position.

        Accepts an ``event`` so it can be wired to a ``<Button-1>``
        binding, but also works when called directly (event=None)
        by falling back to the current pointer position.
        """
        menu = tk.Menu(self, tearoff=0)
        for code in AVAILABLE_LOCALES:
            prefix = "✓ " if code == current_locale() else "  "
            menu.add_command(
                label=prefix + t(f"locale.{code}"),
                command=lambda c=code: self._on_language_select(c),
            )
        try:
            if event is not None:
                menu.tk_popup(event.x_root, event.y_root)
            else:
                x = self.winfo_pointerx()
                y = self.winfo_pointery()
                menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _on_language_select(self, locale: str) -> None:
        """Switch the active locale.

        The actual UI refresh is driven by ``i18n.set_locale`` which
        notifies every page's locale listener. We additionally
        re-render the utility items so the displayed labels update
        immediately, even though the i18n listener would also do so.
        """
        if set_locale(locale):
            self._refresh_utility_items()

    def _refresh_utility_items(
        self, _locale: Optional[str] = None
    ) -> None:
        """Re-render the three utility items after a locale change."""
        self._gpa_rules_item.configure(
            text=t("sidebar.gpa_rules")
        )
        self._language_item.configure(
            text=t("sidebar.language")
        )
        self._about_item.configure(
            text=t("sidebar.about")
        )

    def _refresh_locale(self, _locale: Optional[str] = None) -> None:
        """Refresh every translatable element after a locale change."""
        self._brand_label.configure(text=t("app.brand"))
        for page_id, text_key in self._item_keys.items():
            self._items[page_id].configure(text=t(text_key))
        # The three utility items also carry translated text.
        self._refresh_utility_items()

    def select(self, page_id: str) -> None:
        """Mark ``page_id`` as the active sidebar item and notify caller."""
        if page_id not in self._items:
            return
        if self._current_id == page_id:
            # Still notify so the caller can re-show the page (e.g. on
            # startup when nothing is yet raised).
            self._on_navigate(page_id)
            return
        if self._current_id is not None:
            self._items[self._current_id].configure(
                font=FONT_BODY, bg=SIDEBAR_BG
            )
        self._items[page_id].configure(
            font=FONT_HEADING, bg=SIDEBAR_SELECTED_BG
        )
        self._current_id = page_id
        self._on_navigate(page_id)


# ----------------------------------------------------------------------
# Re-used by both SingleSemesterPage and the SemesterEditorDialog
# Treeview. Maps column_id -> i18n key for the heading text.
_COURSE_HEADING_KEYS_FOR_DIALOG: dict[str, str] = {
    "name": "tree.header.course_name",
    "credit": "tree.header.credit",
    "score": "tree.header.score",
    "point": "tree.header.grade_point",
}


# Pages
# ----------------------------------------------------------------------


class MultiSemesterPage(ttk.Frame):
    """The multi-semester GPA page.

    Mirrors :class:`SingleSemesterPage`'s layout and follows the same
    mutate -> refresh table -> refresh overall GPA -> status pipeline.

    All user-visible text comes from :mod:`i18n`. When the active
    locale changes, :meth:`_refresh_locale` re-renders every
    translatable element (title, section labels, form labels, button
    text, treeview headings, status initial value) so the user sees
    the new language immediately without restarting the app.
    """

    # Table column layout for the Semester List. The headings dict
    # stores i18n keys (resolved via :func:`i18n.t`) instead of
    # raw strings so a locale change can re-render them.
    SEMESTER_COLUMNS: tuple[str, ...] = ("name", "credits", "gpa")
    SEMESTER_HEADING_KEYS: dict[str, str] = {
        "name": "tree.header.semester",
        "credits": "tree.header.credits",
        "gpa": "tree.header.gpa",
    }

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=SECTION_PADDING)

        # In-memory data store.
        self._semesters: list[Semester] = []

        # Widget-bound state.
        self._semester_name_var = tk.StringVar()
        self._gpa_var = tk.StringVar(value="0.00")
        self._status_var = tk.StringVar(value=t("status.ready.multi"))

        self._build_ui()
        self._semester_name_entry.focus_set()

        add_listener(self._refresh_locale)

    # ------------------------------------------------------------------
    # UI construction (mirrors SingleSemesterPage for visual consistency)
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble the sections in the same vertical order as
        :meth:`SingleSemesterPage._build_ui`: title -> form -> list ->
        management -> result, separated by horizontal rules.
        """
        self._title_label = ttk.Label(
            self, font=FONT_HEADING
        )
        self._title_label.configure(text=t("page.title.multi"))
        self._title_label.pack(anchor=tk.W, pady=(0, SECTION_PADDING))

        self._build_form(self)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=SECTION_PADDING
        )

        self._build_semester_list(self)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=SECTION_PADDING
        )

        self._build_management_buttons(self)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=SECTION_PADDING
        )

        self._build_result(self)

    def _build_form(self, parent: ttk.Frame) -> None:
        """Build the Add Semester form.

        Mirrors :meth:`SingleSemesterPage._build_form`: ``Semester Name``
        spans the full width on the first row; the ``Add Semester``
        button sits alone on the second row, right-aligned.
        """
        self._form_frame = ttk.LabelFrame(parent, padding=INPUT_PADDING)
        self._form_frame.configure(text=t("page.section.add_semester"))
        self._form_frame.pack(fill=tk.X)

        self._semester_name_label = ttk.Label(
            self._form_frame, text=t("form.label.semester_name")
        )
        self._semester_name_entry = ttk.Entry(
            self._form_frame,
            textvariable=self._semester_name_var,
            width=NAME_ENTRY_WIDTH,
        )

        # Row 0: Semester Name (entry spans columns 1-4).
        self._semester_name_label.grid(
            row=0, column=0, sticky=tk.W, pady=4
        )
        self._semester_name_entry.grid(
            row=0, column=1, columnspan=4, sticky=tk.EW,
            pady=4, padx=FORM_PADX_RIGHT,
        )

        # Row 1: Add Semester button at the right edge.
        self._add_semester_button = ttk.Button(
            self._form_frame,
            command=self._add_semester,
            width=PRIMARY_BUTTON_WIDTH,
        )
        self._add_semester_button.configure(text=t("button.add_semester"))
        self._add_semester_button.grid(
            row=1, column=4, sticky=tk.EW, pady=(4, 0), padx=FORM_PADX_RIGHT
        )

        # Entry column gets the extra space; rightmost column is the button.
        self._form_frame.columnconfigure(1, weight=1)

    def _build_semester_list(self, parent: ttk.Frame) -> None:
        """Build the Semester List LabelFrame containing only the table.

        Mirrors :meth:`SingleSemesterPage._build_course_list`. Columns
        are ``Semester`` (left-aligned), ``Credits`` and ``GPA`` (both
        right-aligned so numeric values line up).
        """
        self._list_frame = ttk.LabelFrame(parent, padding=INPUT_PADDING)
        self._list_frame.configure(text=t("page.section.semester_list"))
        self._list_frame.pack(fill=tk.BOTH, expand=True)

        tree_container = ttk.Frame(self._list_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self._tree = ttk.Treeview(
            tree_container,
            columns=self.SEMESTER_COLUMNS,
            show="headings",
            height=TABLE_VISIBLE_ROWS,
        )
        for column_id, heading_key in self.SEMESTER_HEADING_KEYS.items():
            self._tree.heading(column_id, text=t(heading_key))
            # Semester name (text) absorbs leftover width on resize;
            # numeric columns (Credits, GPA) keep their natural width so
            # the grid manager does less work per resize event.
            if column_id == "name":
                anchor = tk.W
                stretch = True
            else:
                anchor = tk.E
                stretch = False
            self._tree.column(
                column_id,
                width=TABLE_COLUMN_WIDTH,
                anchor=anchor,
                stretch=stretch,
            )

        scrollbar = ttk.Scrollbar(
            tree_container, orient=tk.VERTICAL, command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_management_buttons(self, parent: ttk.Frame) -> None:
        """Row of Open / Rename / Delete buttons, left-aligned.

        All three buttons share :data:`MANAGEMENT_BUTTON_WIDTH` so the
        row reads as one aligned toolbar.
        """
        button_row = ttk.Frame(parent)
        button_row.pack(fill=tk.X)

        self._open_semester_button = ttk.Button(
            button_row, command=self._open_semester,
            width=MANAGEMENT_BUTTON_WIDTH,
        )
        self._open_semester_button.configure(text=t("button.open_semester"))
        self._open_semester_button.pack(side=tk.LEFT, padx=(0, 8))

        self._rename_semester_button = ttk.Button(
            button_row, command=self._rename_semester,
            width=MANAGEMENT_BUTTON_WIDTH,
        )
        self._rename_semester_button.configure(text=t("button.rename"))
        self._rename_semester_button.pack(side=tk.LEFT, padx=(0, 8))

        self._delete_semester_button = ttk.Button(
            button_row, command=self._delete_semester,
            width=MANAGEMENT_BUTTON_WIDTH,
        )
        self._delete_semester_button.configure(text=t("button.delete"))
        self._delete_semester_button.pack(side=tk.LEFT)

    def _build_result(self, parent: ttk.Frame) -> None:
        """Build the Overall GPA result card and the status label.

        The result area is a ``LabelFrame`` card so this page matches
        :class:`SingleSemesterPage`'s and :class:`TargetGpaPage`'s card
        treatment. Multi-semester has no recalculate button - the GPA
        updates on every add / delete - so only the value sits in the
        card.

        Implementation note: the LabelFrame is created with an empty
        ``text`` and the "Overall GPA" title is added as a regular
        ``ttk.Label`` inside the card. The themed ``ttk.LabelFrame``
        title (the little label that sits inside a gap cut into the
        top border) costs noticeably more to relayout on every resize
        event than an equivalent plain Label; using an internal label
        restores v4.0 resize performance while keeping the same card
        look.
        """
        self._result_card = ttk.LabelFrame(
            parent, text="", padding=RESULT_CARD_PADDING
        )
        self._result_card.pack(fill=tk.X)

        self._result_title = ttk.Label(
            self._result_card, font=FONT_HEADING
        )
        self._result_title.configure(text=t("page.section.overall_gpa"))
        self._result_title.pack(anchor=tk.W, pady=(0, 8))

        self._result_value = ttk.Label(
            self._result_card, font=FONT_DISPLAY,
            textvariable=self._gpa_var,
        )
        self._result_value.pack(side=tk.LEFT)

        self._status_label = ttk.Label(parent, textvariable=self._status_var)
        self._status_label.pack(anchor=tk.W, pady=(10, 0))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _add_semester(self) -> None:
        """Append a new semester to ``self._semesters`` and refresh.

        Newly added semesters start with ``credits=0.0`` and
        ``gpa=0.0`` - these will be filled in by a future
        "open semester" view that lets users enter the semester's
        course list. Until then the row still appears in the table
        with zeros so the add/delete flow is testable end to end.
        """
        name = self._semester_name_var.get().strip()
        if not name:
            self._set_status(t("validation.semester_name_empty"))
            self._semester_name_entry.focus_set()
            return

        semester: Semester = {
            "name": name,
            "credits": 0.0,
            "gpa": 0.0,
            "courses": [],
        }
        self._semesters.append(semester)
        self._refresh_semester_table()
        self._update_overall_gpa_display()
        self._set_status(t("status.added", name=name))
        self._semester_name_var.set("")
        self._semester_name_entry.focus_set()

    def _delete_selected_semester(self) -> None:
        """Remove the currently selected semester from the list.

        The Treeview's ``iid`` is set to the row's index at insertion
        time (see :meth:`_refresh_semester_table`), so capturing it via
        ``selection()`` and converting back to ``int`` yields a stable
        index - even after multiple add / delete cycles.
        """
        index = self._selected_semester_index()
        if index is None:
            self._set_status(t("status.no_selection_semester"))
            return

        removed = self._semesters.pop(index)
        self._refresh_semester_table()
        self._update_overall_gpa_display()
        self._set_status(t("status.deleted", name=removed["name"]))

    def _open_semester(self) -> None:
        """Open a modal editor for the selected semester.

        The editor (see :class:`SemesterEditorDialog`) maintains its own
        course list and live-computes the semester's credits + GPA.
        On Save, the dialog mutates the parent's Semester dict in
        place and returns ``True``; on Cancel the parent's data is
        untouched. After Save, the Semester List table and the
        Overall GPA label are refreshed to reflect the new totals.
        """
        index = self._selected_semester_index()
        if index is None:
            self._set_status(t("status.no_selection_semester"))
            return

        semester = self._semesters[index]
        dialog = SemesterEditorDialog(self, semester, index)
        self.wait_window(dialog.window)

        if dialog.result is True:
            self._refresh_semester_table()
            self._update_overall_gpa_display()
            self._set_status(t("status.opened", name=semester["name"]))

    def _rename_semester(self) -> None:
        """Placeholder for "rename the selected semester"."""
        if self._selected_semester_index() is None:
            self._set_status(t("status.no_selection_semester"))
            return
        self._set_status(t("status.placeholder_rename"))

    # Kept as the public alias called by the Delete button so external
    # callers (and the GUI button command) keep a stable name.
    _delete_semester = _delete_selected_semester

    def _selected_semester_index(self) -> Optional[int]:
        """Resolve the currently selected Treeview row to a list index."""
        selected = self._tree.selection()
        if not selected:
            return None
        try:
            index = int(selected[0])
        except ValueError:
            return None
        if not (0 <= index < len(self._semesters)):
            return None
        return index

    # ------------------------------------------------------------------
    # View sync
    # ------------------------------------------------------------------

    def _refresh_semester_table(self) -> None:
        """Re-render the Treeview from ``self._semesters``.

        Each row is inserted with ``iid=str(index)`` so that
        :meth:`_selected_semester_index` can translate the Treeview's
        selection back to a stable list index without scanning.
        """
        for row_id in self._tree.get_children():
            self._tree.delete(row_id)
        for index, semester in enumerate(self._semesters):
            self._tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    semester["name"],
                    f"{semester['credits']:.1f}",
                    f"{semester['gpa']:.2f}",
                ),
            )

    def _update_overall_gpa_display(self) -> None:
        """Recompute the weighted Overall GPA from ``self._semesters``.

        Formula: ``sum(gpa * credits) / sum(credits)``. Resets to
        ``"0.00"`` when no credits exist so the label never
        divides by zero or displays a stale value.
        """
        total_credits = sum(s["credits"] for s in self._semesters)
        if total_credits == 0:
            self._gpa_var.set("0.00")
            return
        weighted_sum = sum(
            s["gpa"] * s["credits"] for s in self._semesters
        )
        self._gpa_var.set(f"{weighted_sum / total_credits:.2f}")

    # ------------------------------------------------------------------
    # Locale refresh
    # ------------------------------------------------------------------

    def _refresh_locale(self, _locale: Optional[str] = None) -> None:
        """Refresh every translatable element on this page.

        Called by :func:`i18n.set_locale` whenever the active locale
        changes. Re-sets text on the title, the form's LabelFrame and
        its labels/button, the table's LabelFrame and headings, the
        management buttons, and the result card.
        """
        self._title_label.configure(text=t("page.title.multi"))
        self._form_frame.configure(text=t("page.section.add_semester"))
        self._semester_name_label.configure(text=t("form.label.semester_name"))
        self._add_semester_button.configure(text=t("button.add_semester"))
        self._list_frame.configure(text=t("page.section.semester_list"))
        for column_id, heading_key in self.SEMESTER_HEADING_KEYS.items():
            self._tree.heading(column_id, text=t(heading_key))
        self._open_semester_button.configure(text=t("button.open_semester"))
        self._rename_semester_button.configure(text=t("button.rename"))
        self._delete_semester_button.configure(text=t("button.delete"))
        self._result_title.configure(text=t("page.section.overall_gpa"))
        # Status initial value (only if the user has not typed anything
        # custom since startup).
        if self._status_var.get() in t_values("status.ready.multi"):
            self._status_var.set(t("status.ready.multi"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        """Update the status line shown below the Overall GPA label."""
        self._status_var.set(message)


class TargetGpaPage(ttk.Frame):
    """The target-GPA planner page.

    Mirrors the visual rhythm of :class:`SingleSemesterPage` and
    :class:`MultiSemesterPage`. The ``Calculate`` button validates
    the four inputs (Current GPA, Completed Credits, Remaining
    Credits, Target GPA) and updates the ``Required GPA`` result card
    with one of three outcomes:

        * **Reachable** - required GPA in ``[0, MAX_GPA]``; result card
          shows the value plus a one-line explanation.
        * **Already achieved** - current GPA already >= target GPA;
          result card shows the target value plus a friendly note.
        * **Out of reach** - required GPA above :data:`MAX_GPA`;
          result card shows the unattainable value plus an explanation.

    The status line always reflects the latest action so the user
    sees the validation result even when the result card itself is
    not updated (e.g. invalid input).

    All user-visible text comes from :mod:`i18n`. :meth:`_refresh_locale`
    re-renders every translatable element on a locale change.
    """

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=SECTION_PADDING)

        # Form input state.
        self._current_gpa_var = tk.StringVar()
        self._completed_credits_var = tk.StringVar()
        self._remaining_credits_var = tk.StringVar()
        self._target_gpa_input_var = tk.StringVar()

        # Result card state. Initial values are placeholders so the
        # page renders correctly before any Calculate click.
        # The numeric value starts at "0.00" rather than the older
        # 3.84 demo placeholder so the card honestly shows "no result
        # yet" until the user runs Calculate. The helper text below
        # already explains the action to take.
        self._required_gpa_var = tk.StringVar(value="0.00")
        self._required_gpa_helper_var = tk.StringVar(
            value=t("result.placeholder.helper_initial")
        )
        self._status_var = tk.StringVar(value=t("status.ready.target"))

        self._build_ui()
        self._current_gpa_entry.focus_set()

        add_listener(self._refresh_locale)

    # ------------------------------------------------------------------
    # UI construction (mirrors SingleSemesterPage and MultiSemesterPage)
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble the sections in the same vertical order as the
        other pages: title -> form -> separator -> result -> status.
        """
        self._title_label = ttk.Label(self, font=FONT_HEADING)
        self._title_label.configure(text=t("page.title.target"))
        self._title_label.pack(anchor=tk.W, pady=(0, SECTION_PADDING))

        self._build_form(self)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=SECTION_PADDING
        )

        self._build_result_card(self)

        self._status_label = ttk.Label(self, textvariable=self._status_var)
        self._status_label.pack(anchor=tk.W, pady=(10, 0))

    def _build_form(self, parent: ttk.Frame) -> None:
        """Build the Target Inputs form.

        Mirrors :meth:`SingleSemesterPage._build_form`: four input
        fields in a 2x2 grid with the ``Calculate`` button at the
        right of a third row.
        """
        self._form_frame = ttk.LabelFrame(parent, padding=INPUT_PADDING)
        self._form_frame.configure(text=t("page.section.target_inputs"))
        self._form_frame.pack(fill=tk.X)

        # Four entries, each bound to its own StringVar.
        self._current_gpa_entry = ttk.Entry(
            self._form_frame,
            textvariable=self._current_gpa_var, width=SHORT_ENTRY_WIDTH,
        )
        self._completed_credits_entry = ttk.Entry(
            self._form_frame,
            textvariable=self._completed_credits_var, width=SHORT_ENTRY_WIDTH,
        )
        self._remaining_credits_entry = ttk.Entry(
            self._form_frame,
            textvariable=self._remaining_credits_var, width=SHORT_ENTRY_WIDTH,
        )
        self._target_gpa_entry = ttk.Entry(
            self._form_frame,
            textvariable=self._target_gpa_input_var, width=SHORT_ENTRY_WIDTH,
        )

        # Row 0: Current GPA | Completed Credits.
        self._current_gpa_label = ttk.Label(self._form_frame)
        self._current_gpa_label.configure(text=t("form.label.current_gpa"))
        self._current_gpa_label.grid(row=0, column=0, sticky=tk.W, pady=4)
        self._current_gpa_entry.grid(
            row=0, column=1, sticky=tk.EW, pady=4, padx=FORM_PADX_INNER
        )
        self._completed_credits_label = ttk.Label(self._form_frame)
        self._completed_credits_label.configure(
            text=t("form.label.completed_credits")
        )
        self._completed_credits_label.grid(
            row=0, column=2, sticky=tk.W, pady=4
        )
        self._completed_credits_entry.grid(
            row=0, column=3, sticky=tk.EW, pady=4, padx=FORM_PADX_RIGHT
        )

        # Row 1: Remaining Credits | Target GPA.
        self._remaining_credits_label = ttk.Label(self._form_frame)
        self._remaining_credits_label.configure(
            text=t("form.label.remaining_credits")
        )
        self._remaining_credits_label.grid(
            row=1, column=0, sticky=tk.W, pady=4
        )
        self._remaining_credits_entry.grid(
            row=1, column=1, sticky=tk.EW, pady=4, padx=FORM_PADX_INNER
        )
        self._target_gpa_label = ttk.Label(self._form_frame)
        self._target_gpa_label.configure(text=t("form.label.target_gpa"))
        self._target_gpa_label.grid(row=1, column=2, sticky=tk.W, pady=4)
        self._target_gpa_entry.grid(
            row=1, column=3, sticky=tk.EW, pady=4, padx=FORM_PADX_RIGHT
        )

        # Row 2: Calculate button at the right edge.
        self._calculate_button = ttk.Button(
            self._form_frame,
            command=self._on_calculate,
            width=PRIMARY_BUTTON_WIDTH,
        )
        self._calculate_button.configure(text=t("button.calculate"))
        self._calculate_button.grid(
            row=2, column=3, sticky=tk.EW, pady=(8, 0), padx=FORM_PADX_RIGHT
        )

        # Both entry columns expand equally so the four fields share
        # the form's width the way Credit / Score do on the
        # SingleSemesterPage form.
        self._form_frame.columnconfigure(1, weight=1)
        self._form_frame.columnconfigure(3, weight=1)

    def _build_result_card(self, parent: ttk.Frame) -> None:
        """Build the Required GPA result card.

        The card is a :class:`ttk.LabelFrame` styled as a result card
        with clear visual hierarchy:

            1. The "Required GPA" header (a regular ``ttk.Label`` with
               :data:`FONT_HEADING`).
            2. The big numeric value (linked to ``_required_gpa_var``)
               uses :data:`FONT_DISPLAY` so it dominates the card - the
               user came here for *this number*.
            3. The helper sentence (linked to ``_required_gpa_helper_var``)
               sits below in :data:`FONT_BODY` to explain the value.

        Both labels use ``textvariable`` so :meth:`_on_calculate` can
        refresh the card after every Calculate click. The card uses
        :data:`RESULT_CARD_PADDING` (slightly more generous than the
        form padding) so it reads as a distinct result card rather than
        another form section.

        Implementation note: the LabelFrame is created with an empty
        ``text`` and the "Required GPA" title is added as a regular
        ``ttk.Label`` inside the card. The themed ``ttk.LabelFrame``
        title (the little label that sits inside a gap cut into the
        top border) costs noticeably more to relayout on every resize
        event than an equivalent plain Label; using an internal label
        restores v4.0 resize performance while keeping the same card
        look.
        """
        self._result_card = ttk.LabelFrame(
            parent, text="", padding=RESULT_CARD_PADDING
        )
        self._result_card.pack(fill=tk.X)

        # Card header.
        self._result_title = ttk.Label(
            self._result_card, font=FONT_HEADING
        )
        self._result_title.configure(text=t("page.section.required_gpa"))
        self._result_title.pack(anchor=tk.W, pady=(0, 8))

        # Big numeric value - the page's headline result.
        ttk.Label(
            self._result_card,
            textvariable=self._required_gpa_var,
            font=FONT_DISPLAY,
        ).pack(anchor=tk.W, pady=(0, 12))

        # Helper sentence explaining the value.
        ttk.Label(
            self._result_card,
            textvariable=self._required_gpa_helper_var,
            wraplength=480,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_calculate(self) -> None:
        """Compute the required GPA from the four inputs and update the result card.

        Validation is performed in this order, each step updating the
        status line and returning early so the previous (or initial)
        result card stays put:

            1. Each field parses as ``float``.
            2. ``Completed Credits > 0`` and ``Remaining Credits > 0``.
            3. ``Current GPA >= Target GPA`` -> target already achieved.
            4. Otherwise compute ``required = (target*(done+remaining)
               - current*done) / remaining``; if ``required > MAX_GPA``
               the target is unreachable.

        On the success path the result card and the status line are
        both refreshed.
        """
        # 1. Parse inputs.
        try:
            current_gpa = float(self._current_gpa_var.get().strip())
        except ValueError:
            self._set_status(t("target.invalid_current"))
            return
        try:
            completed_credits = float(self._completed_credits_var.get().strip())
        except ValueError:
            self._set_status(t("target.invalid_completed"))
            return
        try:
            remaining_credits = float(self._remaining_credits_var.get().strip())
        except ValueError:
            self._set_status(t("target.invalid_remaining"))
            return
        try:
            target_gpa = float(self._target_gpa_input_var.get().strip())
        except ValueError:
            self._set_status(t("target.invalid_target"))
            return

        # 2. Credit ranges.
        if completed_credits <= 0:
            self._set_status(t("target.completed_non_positive"))
            return
        if remaining_credits <= 0:
            self._set_status(t("target.remaining_non_positive"))
            return

        # 3. Target already achieved.
        if current_gpa >= target_gpa:
            self._required_gpa_var.set(f"{target_gpa:.2f}")
            self._required_gpa_helper_var.set(
                t("result.placeholder.helper_already",
                  target=target_gpa, current=current_gpa)
            )
            self._set_status(
                t("target.already_achieved",
                  current=current_gpa, target=target_gpa)
            )
            return

        # 4. Compute required GPA and check feasibility.
        required_gpa = (
            (target_gpa * (completed_credits + remaining_credits)
             - current_gpa * completed_credits)
            / remaining_credits
        )

        if required_gpa > data.get_max_gpa():
            self._required_gpa_var.set(f"{required_gpa:.2f}")
            self._required_gpa_helper_var.set(
                t("result.placeholder.helper_unreachable",
                  required=required_gpa, max=data.get_max_gpa(), target=target_gpa)
            )
            self._set_status(
                t("target.cannot_reach",
                  target=target_gpa, required=required_gpa, max=data.get_max_gpa())
            )
            return

        # 5. Success - reachable target.
        self._required_gpa_var.set(f"{required_gpa:.2f}")
        remaining_str = (
            f"{remaining_credits:g}"
            if remaining_credits != int(remaining_credits)
            else f"{int(remaining_credits)}"
        )
        self._required_gpa_helper_var.set(
            t("result.placeholder.helper_required",
              required=required_gpa, remaining=remaining_str,
              target=target_gpa)
        )
        self._set_status(
            t("status.calculated", required=required_gpa)
        )

    # ------------------------------------------------------------------
    # Locale refresh
    # ------------------------------------------------------------------

    def _refresh_locale(self, _locale: Optional[str] = None) -> None:
        """Re-render every translatable element after a locale change.

        Re-sets the page title, the form's LabelFrame and its four
        field labels, the Calculate button, the result card's title
        and helper text placeholder, and the "ready" status if the
        user has not typed anything custom.
        """
        self._title_label.configure(text=t("page.title.target"))
        self._form_frame.configure(text=t("page.section.target_inputs"))
        self._current_gpa_label.configure(text=t("form.label.current_gpa"))
        self._completed_credits_label.configure(
            text=t("form.label.completed_credits")
        )
        self._remaining_credits_label.configure(
            text=t("form.label.remaining_credits")
        )
        self._target_gpa_label.configure(text=t("form.label.target_gpa"))
        self._calculate_button.configure(text=t("button.calculate"))
        self._result_title.configure(text=t("page.section.required_gpa"))
        # The helper text under the Required GPA value is only re-translated
        # when it is still the initial placeholder (i.e. the user has not
        # run Calculate yet). Once a calculation has run, the helper text
        # embeds locale-specific numbers (required, target, ...) and must
        # not be silently overwritten.
        if self._required_gpa_helper_var.get() in t_values(
            "result.placeholder.helper_initial"
        ):
            self._required_gpa_helper_var.set(
                t("result.placeholder.helper_initial")
            )
        if self._status_var.get() in t_values("status.ready.target"):
            self._status_var.set(t("status.ready.target"))

    def _set_status(self, message: str) -> None:
        """Update the status line shown below the result card."""
        self._status_var.set(message)


class SingleSemesterPage(ttk.Frame):
    """The single-semester GPA calculator.

    All logic from v3.2's :class:`GpaManagerApp` lives here now. The
    class owns the in-memory course list and the widget state for the
    form / table / GPA label / status line.

    All user-visible text comes from :mod:`i18n`. When the active
    locale changes, :meth:`_refresh_locale` re-renders every
    translatable element (title, form's "Add Course" header, form
    labels, button text, table LabelFrame, treeview headings,
    management buttons, result card) so the user sees the new
    language immediately without restarting the app.
    """

    # Map column_id -> i18n key (used both at build time and on
    # locale refresh, so a locale change can re-render headings).
    _COURSE_HEADING_KEYS: dict[str, str] = {
        "name": "tree.header.course_name",
        "credit": "tree.header.credit",
        "score": "tree.header.score",
        "point": "tree.header.grade_point",
    }

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=SECTION_PADDING)
        self._courses: list[Course] = []

        self._name_var = tk.StringVar()
        self._credit_var = tk.StringVar()
        self._score_var = tk.StringVar()
        self._gpa_var = tk.StringVar(value="0.00")
        self._status_var = tk.StringVar(value=t("status.ready.single"))

        self._build_ui()
        self._name_entry.focus_set()

        add_listener(self._refresh_locale)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble the four sections: title, form, list, management,
        result. Vertical pack order: top → bottom."""
        self._title_label = ttk.Label(self, font=FONT_HEADING)
        self._title_label.configure(text=t("page.title.single"))
        self._title_label.pack(anchor=tk.W, pady=(0, SECTION_PADDING))

        self._build_form(self)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=SECTION_PADDING
        )

        self._build_course_list(self)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=SECTION_PADDING
        )

        self._build_management_buttons(self)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=SECTION_PADDING
        )

        self._build_result(self)

    def _build_form(self, parent: ttk.Frame) -> None:
        """Build the Add Course form.

        Two-row layout: ``Course Name`` spans the full width on the
        first row; ``Credit``, ``Score`` and the ``Add Course`` button
        share the second row.

        Implementation note: the outer widget is a plain ``ttk.Frame``
        with an internal ``Add Course`` title label, mirroring the
        result card pattern from :meth:`_build_result`. The themed
        ``ttk.LabelFrame`` title cut into a border costs noticeably more
        to relayout on every resize event than an equivalent plain
        Label. An inner ``ttk.Frame`` with ``padding=INPUT_PADDING``
        keeps the original 12px inset around the form contents so the
        spacing and alignment of the form itself are unchanged.
        """
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.X)

        # Internal title label (matches the result card approach).
        self._form_title = ttk.Label(outer, font=FONT_HEADING)
        self._form_title.configure(text=t("button.add_course"))  # header text
        self._form_title.pack(anchor=tk.W, pady=(0, 8))

        # Inner frame keeps the form's original 12px padding so the
        # spacing of the form contents is unchanged.
        inner = ttk.Frame(outer, padding=INPUT_PADDING)
        inner.pack(fill=tk.X)

        self._name_entry = ttk.Entry(
            inner, textvariable=self._name_var, width=NAME_ENTRY_WIDTH
        )
        self._credit_entry = ttk.Entry(
            inner, textvariable=self._credit_var, width=SHORT_ENTRY_WIDTH
        )
        self._score_entry = ttk.Entry(
            inner, textvariable=self._score_var, width=SHORT_ENTRY_WIDTH
        )

        # Row 0: Course Name (entry spans columns 1–4).
        self._name_label = ttk.Label(inner)
        self._name_label.configure(text=t("form.label.course_name"))
        self._name_label.grid(row=0, column=0, sticky=tk.W, pady=4)
        self._name_entry.grid(
            row=0, column=1, columnspan=4, sticky=tk.EW, pady=4, padx=FORM_PADX_RIGHT
        )

        # Row 1: Credit | Score | Add Course.
        self._credit_label = ttk.Label(inner)
        self._credit_label.configure(text=t("form.label.credit"))
        self._credit_label.grid(row=1, column=0, sticky=tk.W, pady=4)
        self._credit_entry.grid(
            row=1, column=1, sticky=tk.EW, pady=4, padx=FORM_PADX_INNER
        )
        self._score_label = ttk.Label(inner)
        self._score_label.configure(text=t("form.label.score"))
        self._score_label.grid(row=1, column=2, sticky=tk.W, pady=4)
        self._score_entry.grid(
            row=1, column=3, sticky=tk.EW, pady=4, padx=FORM_PADX_INNER
        )
        self._add_course_button = ttk.Button(
            inner, command=self._add_course,
            width=PRIMARY_BUTTON_WIDTH,
        )
        self._add_course_button.configure(text=t("button.add_course"))
        self._add_course_button.grid(
            row=1, column=4, sticky=tk.EW, pady=4, padx=FORM_PADX_RIGHT
        )

        # Entry columns get the extra space; label / button columns keep
        # their natural width.
        inner.columnconfigure(1, weight=1)
        inner.columnconfigure(3, weight=1)

    def _build_course_list(self, parent: ttk.Frame) -> None:
        """Build the Course List LabelFrame containing only the table."""
        self._list_frame = ttk.LabelFrame(parent, padding=INPUT_PADDING)
        self._list_frame.configure(text=t("page.section.course_list"))
        self._list_frame.pack(fill=tk.BOTH, expand=True)

        tree_container = ttk.Frame(self._list_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self._tree = ttk.Treeview(
            tree_container,
            columns=TABLE_COLUMNS,
            show="headings",
            height=TABLE_VISIBLE_ROWS,
        )
        for column_id, heading_key in self._COURSE_HEADING_KEYS.items():
            self._tree.heading(column_id, text=t(heading_key))
            # Course Name (text) is flexible - it absorbs the leftover
            # width when the table is resized. Numeric columns (credit,
            # score, grade point) keep their natural width so the grid
            # manager does less work per resize event.
            if column_id == "name":
                anchor = tk.W
                stretch = True
            else:
                anchor = tk.E
                stretch = False
            self._tree.column(
                column_id,
                width=TABLE_COLUMN_WIDTH,
                anchor=anchor,
                stretch=stretch,
            )

        scrollbar = ttk.Scrollbar(
            tree_container, orient=tk.VERTICAL, command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<Double-1>", self._on_row_double_click)

    def _build_management_buttons(self, parent: ttk.Frame) -> None:
        """Row of Edit / Delete / Clear buttons, left-aligned.

        All three buttons share :data:`MANAGEMENT_BUTTON_WIDTH` so the
        row reads as one aligned toolbar.
        """
        button_row = ttk.Frame(parent)
        button_row.pack(fill=tk.X)

        self._edit_button = ttk.Button(
            button_row, command=self._edit_selected_course,
            width=MANAGEMENT_BUTTON_WIDTH,
        )
        self._edit_button.configure(text=t("button.edit_selected"))
        self._edit_button.pack(side=tk.LEFT, padx=(0, 8))

        self._delete_button = ttk.Button(
            button_row, command=self._delete_selected_course,
            width=MANAGEMENT_BUTTON_WIDTH,
        )
        self._delete_button.configure(text=t("button.delete_selected"))
        self._delete_button.pack(side=tk.LEFT, padx=(0, 8))

        self._clear_button = ttk.Button(
            button_row, command=self._clear_all_courses,
            width=MANAGEMENT_BUTTON_WIDTH,
        )
        self._clear_button.configure(text=t("button.clear_all"))
        self._clear_button.pack(side=tk.LEFT)

    def _build_result(self, parent: ttk.Frame) -> None:
        """Build the Overall GPA result card and the status label.

        The result area is a ``LabelFrame`` card so this page matches
        :class:`MultiSemesterPage` and :class:`TargetGpaPage`'s card
        treatment. The big value sits on the left, the ``Calculate``
        button on the right.

        Implementation note: the LabelFrame is created with an empty
        ``text`` and the "Overall GPA" title is added as a regular
        ``ttk.Label`` inside the card. The themed ``ttk.LabelFrame``
        title (the little label that sits inside a gap cut into the
        top border) costs noticeably more to relayout on every resize
        event than an equivalent plain Label; using an internal label
        restores v4.0 resize performance while keeping the same card
        look.
        """
        self._result_card = ttk.LabelFrame(
            parent, text="", padding=RESULT_CARD_PADDING
        )
        self._result_card.pack(fill=tk.X)

        self._result_title = ttk.Label(self._result_card, font=FONT_HEADING)
        self._result_title.configure(text=t("page.section.overall_gpa"))
        self._result_title.pack(anchor=tk.W, pady=(0, 8))

        self._result_value = ttk.Label(
            self._result_card, font=FONT_DISPLAY,
            textvariable=self._gpa_var,
        )
        self._result_value.pack(side=tk.LEFT)

        self._calculate_button = ttk.Button(
            self._result_card, command=self._calculate_gpa,
            width=PRIMARY_BUTTON_WIDTH,
        )
        self._calculate_button.configure(text=t("button.calculate_gpa"))
        self._calculate_button.pack(side=tk.RIGHT)

        self._status_label = ttk.Label(parent, textvariable=self._status_var)
        self._status_label.pack(anchor=tk.W, pady=(10, 0))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _add_course(self) -> None:
        """Validate input, append a course, then sync the views."""
        name = self._name_var.get().strip()
        credit_raw = self._credit_var.get().strip()
        score = self._score_var.get().strip()

        course, error = _validate_course_fields(name, credit_raw, score)
        if error:
            error_key, error_args = error
            self._set_status(t(error_key, **error_args))
            _focus_from_error(
                error_key, self._name_entry, self._credit_entry, self._score_entry
            )
            return

        self._courses.append(course)
        self._refresh_course_table()
        self._update_gpa_display()
        self._clear_input_fields()
        self._set_status(t("status.added", name=course["name"]))

    def _on_row_double_click(self, event: tk.Event) -> None:
        """Open the edit dialog when the user double-clicks a table row."""
        row_id = self._tree.identify_row(event.y)
        if row_id:
            self._tree.selection_set(row_id)
            self._edit_selected_course()

    def _edit_selected_course(self) -> None:
        """Open the edit dialog for the currently selected course."""
        index = self._selected_course_index()
        if index is None:
            self._set_status(t("status.no_selection_course"))
            return
        self._open_edit_dialog(index)

    def _open_edit_dialog(self, index: int) -> None:
        """Show the edit dialog and apply its result back to the list."""
        original_name = self._courses[index]["name"]
        dialog = CourseEditDialog(self, self._courses[index])
        self.wait_window(dialog.window)

        if dialog.result is None:
            self._set_status(t("status.edit_cancelled"))
            return

        self._courses[index] = dialog.result
        self._refresh_course_table()
        self._update_gpa_display()

        new_name = dialog.result["name"]
        if new_name == original_name:
            self._set_status(t("status.updated", name=new_name))
        else:
            self._set_status(t("status.renamed",
                               old=original_name, new=new_name))

    def _delete_selected_course(self) -> None:
        """Remove the currently selected course from the list."""
        index = self._selected_course_index()
        if index is None:
            self._set_status(t("status.no_selection_course"))
            return

        removed = self._courses.pop(index)
        self._refresh_course_table()
        self._update_gpa_display()
        self._set_status(t("status.deleted", name=removed["name"]))

    def _clear_all_courses(self) -> None:
        """Remove every course after asking the user to confirm."""
        if not self._courses:
            self._set_status(t("status.no_courses_to_clear"))
            return

        confirmed = messagebox.askyesno(
            t("confirm.clear_all.title"),
            t("confirm.clear_all.message", count=len(self._courses)),
        )
        if not confirmed:
            self._set_status(t("status.clear_cancelled"))
            return

        count = len(self._courses)
        self._courses.clear()
        self._refresh_course_table()
        self._update_gpa_display()
        self._set_status(t("status.cleared", count=count))

    def _calculate_gpa(self) -> None:
        """Explicit recompute action for the GPA label."""
        if not self._courses:
            self._set_status(t("status.no_courses_to_calculate"))
            return
        self._update_gpa_display()
        # Use the already-formatted gpa value in the status message so
        # the user sees the same number that's on the result card.
        self._set_status(
            t(
                "status.calculated_gpa",
                gpa=self._gpa_var.get(),
                count=len(self._courses),
            )
        )

    # ------------------------------------------------------------------
    # View sync
    # ------------------------------------------------------------------

    def _refresh_course_table(self) -> None:
        """Re-render the Treeview from ``self._courses``."""
        for row_id in self._tree.get_children():
            self._tree.delete(row_id)
        for index, course in enumerate(self._courses):
            self._tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    course["name"],
                    f"{course['credit']:.1f}",
                    course["score"],
                    f"{course['point']:.1f}",
                ),
            )

    def _update_gpa_display(self) -> None:
        """Recompute the weighted GPA from ``self._courses``."""
        if not self._courses:
            self._gpa_var.set("0.00")
            return
        gpa = calculate_gpa(self._courses)
        self._gpa_var.set(f"{gpa:.2f}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _selected_course_index(self) -> Optional[int]:
        """Resolve the currently selected Treeview row to a list index."""
        selected = self._tree.selection()
        if not selected:
            return None
        try:
            index = int(selected[0])
        except ValueError:
            return None
        if not (0 <= index < len(self._courses)):
            return None
        return index

    def _clear_input_fields(self) -> None:
        """Reset the three input fields and return focus to the name field."""
        self._name_var.set("")
        self._credit_var.set("")
        self._score_var.set("")
        self._name_entry.focus_set()

    def _set_status(self, message: str) -> None:
        """Update the status line shown below the result row."""
        self._status_var.set(message)

    # ------------------------------------------------------------------
    # Locale refresh
    # ------------------------------------------------------------------

    def _refresh_locale(self, _locale: Optional[str] = None) -> None:
        """Re-render every translatable element after a locale change.

        Re-sets the page title, the form's "Add Course" header and
        its labels, the table's LabelFrame and headings, the
        management buttons, the result card title and button, and the
        "ready" status if the user has not typed anything custom.
        """
        self._title_label.configure(text=t("page.title.single"))
        self._form_title.configure(text=t("button.add_course"))
        self._name_label.configure(text=t("form.label.course_name"))
        self._credit_label.configure(text=t("form.label.credit"))
        self._score_label.configure(text=t("form.label.score"))
        self._add_course_button.configure(text=t("button.add_course"))
        self._list_frame.configure(text=t("page.section.course_list"))
        for column_id, heading_key in self._COURSE_HEADING_KEYS.items():
            self._tree.heading(column_id, text=t(heading_key))
        self._edit_button.configure(text=t("button.edit_selected"))
        self._delete_button.configure(text=t("button.delete_selected"))
        self._clear_button.configure(text=t("button.clear_all"))
        self._result_title.configure(text=t("page.section.overall_gpa"))
        self._calculate_button.configure(text=t("button.calculate_gpa"))
        # If the user has not typed a custom status yet, the ready
        # message should follow the active locale.
        if self._status_var.get() in t_values("status.ready.single"):
            self._status_var.set(t("status.ready.single"))


# ----------------------------------------------------------------------
# About dialog
# ----------------------------------------------------------------------


def _open_with_default_editor(path: pathlib.Path) -> bool:
    """Open ``path`` in the OS-default editor.

    Returns ``True`` on success. The caller is expected to fall back
    to a friendly error dialog on ``False`` (e.g. when the file
    cannot be reached by the shell).
    """
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", str(path)], close_fds=True)
    except (OSError, FileNotFoundError, AttributeError):
        return False
    return True


class AboutDialog:
    """Modal About dialog.

    Reads metadata at construction time so the displayed values always
    match the current application state:

    * Version comes from :data:`__version__`.
    * GPA Scale name comes from :func:`data.get_scale_name`, which in
      turn reflects whatever ``config/gpa_scale.json`` declares (or the
      built-in default if the loader fell back to it).
    * Current language comes from :func:`i18n.current_locale_label`.
    * Python runtime comes from :func:`platform.python_version`.

    No icons, no oversized buttons, no large empty areas. Centred
    layout using the same font family as the rest of the app.
    """

    def __init__(self, parent: tk.Misc) -> None:
        self._dialog = tk.Toplevel(parent)
        self._dialog.title(t("about.title"))
        self._dialog.transient(parent)
        self._dialog.resizable(False, False)
        self._dialog.protocol("WM_DELETE_WINDOW", self._close)

        body = ttk.Frame(self._dialog, padding=24)
        body.pack(fill=tk.BOTH, expand=True)

        # App name (title row).
        ttk.Label(
            body, text=t("about.app_name"),
            font=FONT_HEADING,
        ).pack(anchor=tk.CENTER, pady=(0, 14))

        # Detail rows: Version, GPA Scale, Language, Python.
        info_lines = [
            (t("about.version_label"), __version__),
            (t("about.gpa_scale_label"), data.get_scale_name()),
            (t("about.language_label"), current_locale_label()),
            (
                t("about.python_label"),
                platform.python_version(),
            ),
        ]
        info = ttk.Frame(body)
        info.pack(anchor=tk.CENTER, pady=(0, 12))
        for label, value in info_lines:
            row = ttk.Frame(info)
            row.pack(anchor=tk.CENTER, pady=2)
            ttk.Label(
                row,
                text=t("about.info_row", label=label, value=value),
            ).pack(side=tk.LEFT)

        # Separator before the copyright.
        ttk.Separator(body, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=(4, 12)
        )

        # Copyright + tagline.
        ttk.Label(
            body, text=t("about.copyright"),
        ).pack(anchor=tk.CENTER)
        ttk.Label(
            body, text=t("about.url"),
        ).pack(anchor=tk.CENTER)
        ttk.Label(
            body, text=t("about.tagline"),
        ).pack(anchor=tk.CENTER, pady=(0, 12))

        # OK button (narrow, so the dialog stays compact).
        ttk.Button(
            body, text=t("about.ok"),
            command=self._close,
            width=10,
        ).pack(anchor=tk.CENTER, pady=(4, 0))

        # Center over the parent (main application window) using the
        # shared helper so the dialog always sits over the toplevel,
        # not over a sidebar sub-frame.
        _center_dialog_on_parent(self._dialog, parent)

        self._dialog.grab_set()
        self._dialog.focus_set()

    @property
    def window(self) -> tk.Toplevel:
        """The underlying Toplevel (for tests or waiters)."""
        return self._dialog

    def _close(self) -> None:
        self._dialog.destroy()


# ----------------------------------------------------------------------
# Main window (sidebar + workspace)
# ----------------------------------------------------------------------


class MainWindow:
    """Top-level coordinator: owns the sidebar and the workspace.

    All three page instances are kept alive for the lifetime of the
    application (so their state survives navigation), but **only the
    currently visible page is gridded** into the workspace. Hidden
    pages stay alive but are removed from the geometry manager, so the
    grid manager does not reflow them during window resize. See
    :meth:`_show_page` for the grid_remove / grid cycle used on
    navigation.
    """

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        # Set the main-window + taskbar icon from the bundled .ico.
        # Resolved through :func:`data.get_internal_path` so the file
        # is read from ``_internal/GPA_Manager.ico`` in a frozen build
        # and from the project root in ``python gui.py`` development.
        # A missing or non-ICO file raises ``TclError`` on some
        # platforms; the GUI still opens without a custom icon in
        # that case, so we just swallow the error.
        try:
            self._root.iconbitmap(
                str(data.get_internal_path("GPA_Manager.ico"))
            )
        except tk.TclError:
            pass
        self._pages: dict[str, ttk.Frame] = {}
        # ``None`` until the default page is selected during _build_ui.
        self._active_page_id: Optional[str] = None
        self._build_ui()
        # Re-render the window title (and any other root-level text)
        # when the locale changes.
        add_listener(self._refresh_locale)

    def _refresh_locale(self, _locale: Optional[str] = None) -> None:
        """Refresh locale-dependent text owned by MainWindow itself.

        Per-page text is refreshed by each page's own listener; this
        method only updates the root window title and (if any other
        root-level text is added later) similar top-level strings.
        """
        self._root.title(t("app.title"))

    def _build_ui(self) -> None:
        """Set up the title, the three-column layout, the pages, and the
        default selection.

        Invariant: after this method returns, the workspace is **never
        empty** - exactly one page is gridded at any time. The default
        selection (``Sidebar.select``) triggers :meth:`_show_page`,
        which grids the default page; the other two pages remain
        ungridded until first navigated to.
        """
        self._root.title(t("app.title"))
        self._root.geometry(WINDOW_SIZE)
        self._root.minsize(MIN_WIDTH, MIN_HEIGHT)

        # Three-column layout:
        #   col 0 = fixed-width sidebar (always ``SIDEBAR_WIDTH``);
        #   col 1 = visual gap with a 1px divider (fixed at ``SIDEBAR_GAP``);
        #   col 2 = workspace (takes the remaining width).
        self._root.columnconfigure(0, minsize=SIDEBAR_WIDTH)
        self._root.columnconfigure(1, minsize=SIDEBAR_GAP)
        self._root.columnconfigure(2, weight=1)
        self._root.rowconfigure(0, weight=1)

        self._sidebar = Sidebar(self._root, on_navigate=self._navigate_to)
        self._sidebar.grid(row=0, column=0, sticky="nsw")

        self._build_gap()

        self._workspace = ttk.Frame(self._root)
        self._workspace.grid(row=0, column=2, sticky="nsew")
        self._workspace.columnconfigure(0, weight=1)
        self._workspace.rowconfigure(0, weight=1)

        # Instantiate every page so its state survives navigation, but
        # DO NOT grid them all here. ``Sidebar.select`` below triggers
        # ``_show_page`` which grids only the default page.
        self._pages[PAGE_SINGLE] = SingleSemesterPage(self._workspace)
        self._pages[PAGE_MULTI] = MultiSemesterPage(self._workspace)
        self._pages[PAGE_TARGET] = TargetGpaPage(self._workspace)

        # Default selection - triggers navigation which grids the page.
        self._sidebar.select(PAGE_SINGLE)

    def _build_gap(self) -> None:
        """Build the 20px gap column between sidebar and workspace.

        The gap is a plain ``ttk.Frame`` that owns two fixed-width
        children: a transparent filler on the left, and a 1px vertical
        line at the right edge. The filler + divider combination makes
        the divider sit flush against the workspace no matter how the
        window is resized.

        Why the filler is *fixed-width*: Tk's ``columnconfigure(...,
        minsize=...)`` only takes effect when the gridded widget's
        natural requested width is above zero. An empty ``ttk.Frame``
        requests ~1px, so ``minsize`` is silently ignored. Putting a
        fixed-width child (19px) + a 1px divider inside makes the gap
        request 20px wide, which is then enforced by the column.
        """
        gap = ttk.Frame(self._root)
        gap.grid(row=0, column=1, sticky="ns")

        filler_width = SIDEBAR_GAP - 1
        filler = tk.Frame(gap, bg=SIDEBAR_BG, width=filler_width)
        filler.pack(side=tk.LEFT, fill=tk.Y)
        filler.pack_propagate(False)

        divider = tk.Frame(gap, bg=DIVIDER_COLOR, width=1)
        divider.pack(side=tk.LEFT, fill=tk.Y)

    def _show_page(self, page_id: str) -> None:
        """Make ``page_id`` the visible page in the workspace.

        Uses ``grid_remove`` on the currently active page and ``grid``
        on the new one so only the visible page participates in the
        geometry manager (and therefore in the per-event resize
        reflow). Pages stay instantiated in both states - widget
        values, StringVars, Treeview selection and the in-memory
        course / semester lists all survive navigation unchanged.

        ``grid_remove`` (vs ``grid_forget``) is intentional: it unmaps
        the widget but **remembers** its previous grid options, so a
        later ``grid()`` call without arguments restores them
        automatically.
        """
        if page_id not in self._pages:
            return
        if self._active_page_id == page_id:
            return
        if self._active_page_id is not None:
            self._pages[self._active_page_id].grid_remove()
        self._pages[page_id].grid(row=0, column=0, sticky="nsew")
        self._active_page_id = page_id

    def _navigate_to(self, page_id: str) -> None:
        """Bring the requested page to the top of the workspace."""
        self._show_page(page_id)


def main() -> None:
    """Launch the GPA Manager GUI with high-DPI support."""
    # Load the GPA scale from disk before any widget is created.
    # ``data.load_gpa_scale`` is safe to call before Tk exists - it only
    # touches the filesystem and the module's own state. Doing it here
    # means the loaded rules are ready by the time the user enters the
    # first score, and ``data.MAX_GPA`` / ``data.get_max_gpa()`` return
    # their real values.
    data.load_gpa_scale()
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    _sync_tk_scaling(root)
    _init_fonts()  # Font objects must exist before any widget is built.
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()