"""Graphical user interface for GPA Manager v3.2.

v3.2 changes over v3.1:
    * Course editing: ``Edit Selected`` button + double-click on a row
      opens a modal dialog pre-filled with the course's current values.
    * The dialog has ``Save`` / ``Cancel``; saving validates inputs
      (same rules as :meth:`GpaManagerApp._add_course`) and writes
      the updated record back into ``self._courses``.
    * Course input validation is now shared between add and edit via
      :func:`_validate_course_fields`, eliminating duplication.

DPI plumbing, the four-step mutation pipeline (mutate list → refresh
table → refresh GPA → status) and table selection plumbing from
v3.0.1 / v3.1 are unchanged.

Architecture:
    * :class:`GpaManagerApp` owns the in-memory course list and all
      main-window widget state.
    * :class:`CourseEditDialog` is a small modal Toplevel that owns
      its own entry widgets and returns the edited record (or ``None``
      if the user cancelled).
    * Mutating actions still all share the same pipeline:

          1. mutate ``self._courses``;
          2. call :meth:`GpaManagerApp._refresh_course_table`;
          3. call :meth:`GpaManagerApp._update_gpa_display`;
          4. update the status line.

      Keeping this single pipeline is what guarantees the table and
      the GPA label never drift from the underlying list.
"""

import ctypes
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from data import Course
from gpa_calculator import calculate_gpa, convert_score

APP_TITLE = "GPA Manager"
WINDOW_SIZE = "600x700"
MIN_WIDTH = 540
MIN_HEIGHT = 640

INPUT_PADDING = 12
SECTION_PADDING = 14
ENTRY_WIDTH = 32

TABLE_COLUMNS: tuple[str, ...] = ("name", "credit", "score", "point")
TABLE_HEADINGS: dict[str, str] = {
    "name": "Course Name",
    "credit": "Credit",
    "score": "Score",
    "point": "Grade Point",
}
TABLE_VISIBLE_ROWS = 10
TREE_ROW_PIXEL_HEIGHT = 30

DIALOG_TITLE = "Edit Course"
DIALOG_PADDING = 16

FONT_FAMILY = "Segoe UI"
FONT_BODY: tuple[str, int] = (FONT_FAMILY, 10)
FONT_HEADING: tuple[str, int, str] = (FONT_FAMILY, 10, "bold")
FONT_LARGE: tuple[str, int, str] = (FONT_FAMILY, 14, "bold")


# ----------------------------------------------------------------------
# Validation (shared between add and edit)
# ----------------------------------------------------------------------


def _validate_course_fields(
    name: str,
    credit_raw: str,
    score: str,
) -> tuple[Optional[Course], Optional[str]]:
    """Parse and validate course input fields.

    Returns ``(course, None)`` on success or ``(None, error)`` on
    failure. Error messages name the offending field so callers can
    move keyboard focus there.
    """
    if not name:
        return None, "Course name cannot be empty."
    try:
        credit = float(credit_raw)
    except ValueError:
        return None, f"Invalid credit '{credit_raw}'. Please enter a number."
    if credit <= 0:
        return None, "Credit must be greater than 0."
    point = convert_score(score)
    if point is None:
        return None, (
            f"Invalid score '{score}'. Use a number or text "
            "(及格/中等/良好/优秀)."
        )
    course: Course = {
        "name": name,
        "credit": credit,
        "score": score,
        "point": point,
    }
    return course, None


def _focus_from_error(
    error: str,
    name_entry: ttk.Entry,
    credit_entry: ttk.Entry,
    score_entry: ttk.Entry,
) -> None:
    """Move focus to whichever entry the error message refers to."""
    lowered = error.lower()
    if "credit" in lowered:
        credit_entry.focus_set()
    elif "score" in lowered:
        score_entry.focus_set()
    elif "name" in lowered or "course" in lowered:
        name_entry.focus_set()


# ----------------------------------------------------------------------
# DPI & style configuration
# ----------------------------------------------------------------------


def _enable_windows_dpi_awareness() -> None:
    """Enable Per-Monitor V2 DPI awareness on Windows.

    Must be called **before** creating the Tk root window. Falls back
    to legacy System DPI awareness on older Windows releases. Non-Windows
    platforms are a no-op.
    """
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
# Edit dialog
# ----------------------------------------------------------------------


class CourseEditDialog:
    """Modal dialog that lets the user edit a single course record.

    Usage:
        dialog = CourseEditDialog(parent_window, course_dict)
        parent.wait_window(dialog)
        if dialog.result is not None:
            apply(dialog.result)

    ``dialog.result`` is a :class:`~data.Course` record on Save, or
    ``None`` on Cancel (or when the window is closed via the WM X).
    """

    def __init__(self, parent: tk.Tk, course: Course) -> None:
        self.result: Optional[Course] = None

        self._dialog = tk.Toplevel(parent)
        self._dialog.title(DIALOG_TITLE)
        self._dialog.transient(parent)
        self._dialog.resizable(False, False)

        self._name_var = tk.StringVar(value=course["name"])
        self._credit_var = tk.StringVar(value=str(course["credit"]))
        self._score_var = tk.StringVar(value=course["score"])
        self._status_var = tk.StringVar()

        self._build_ui()
        self._center_on(parent)
        self._dialog.protocol("WM_DELETE_WINDOW", self._cancel)

        # Modal: block input to the parent until this dialog is closed.
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

        ttk.Label(frame, text="Course Name").grid(
            row=0, column=0, sticky=tk.W, pady=4
        )
        self._name_entry = ttk.Entry(
            frame, textvariable=self._name_var, width=ENTRY_WIDTH
        )
        self._name_entry.grid(row=0, column=1, sticky=tk.EW, pady=4, padx=(12, 0))

        ttk.Label(frame, text="Credit").grid(
            row=1, column=0, sticky=tk.W, pady=4
        )
        self._credit_entry = ttk.Entry(
            frame, textvariable=self._credit_var, width=ENTRY_WIDTH
        )
        self._credit_entry.grid(row=1, column=1, sticky=tk.EW, pady=4, padx=(12, 0))

        ttk.Label(frame, text="Score").grid(
            row=2, column=0, sticky=tk.W, pady=4
        )
        self._score_entry = ttk.Entry(
            frame, textvariable=self._score_var, width=ENTRY_WIDTH
        )
        self._score_entry.grid(row=2, column=1, sticky=tk.EW, pady=4, padx=(12, 0))

        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, textvariable=self._status_var).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=(8, 0)
        )

        button_row = ttk.Frame(frame)
        button_row.grid(row=4, column=0, columnspan=2, pady=(8, 0), sticky=tk.EW)

        ttk.Button(
            button_row, text="Cancel", command=self._cancel, width=12
        ).pack(side=tk.RIGHT)
        ttk.Button(
            button_row, text="Save", command=self._save, width=12
        ).pack(side=tk.RIGHT, padx=(0, 8))

        self._dialog.bind("<Return>", lambda _e: self._save())
        self._dialog.bind("<Escape>", lambda _e: self._cancel())

    def _center_on(self, parent: tk.Tk) -> None:
        """Position the dialog over the parent window."""
        self._dialog.update_idletasks()
        x = parent.winfo_x() + (
            parent.winfo_width() - self._dialog.winfo_width()
        ) // 2
        y = parent.winfo_y() + (
            parent.winfo_height() - self._dialog.winfo_height()
        ) // 2
        self._dialog.geometry(f"+{x}+{y}")

    def _save(self) -> None:
        """Validate the inputs and, on success, store the result and close."""
        name = self._name_var.get().strip()
        credit_raw = self._credit_var.get().strip()
        score = self._score_var.get().strip()

        course, error = _validate_course_fields(name, credit_raw, score)
        if error:
            self._status_var.set(error)
            _focus_from_error(
                error, self._name_entry, self._credit_entry, self._score_entry
            )
            return

        self.result = course
        self._dialog.destroy()

    def _cancel(self) -> None:
        """Discard any edits and close the dialog."""
        self.result = None
        self._dialog.destroy()


# ----------------------------------------------------------------------
# Application
# ----------------------------------------------------------------------


class GpaManagerApp:
    """Main application window for the GPA Manager GUI."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._courses: list[Course] = []

        self._name_var = tk.StringVar()
        self._credit_var = tk.StringVar()
        self._score_var = tk.StringVar()
        self._gpa_var = tk.StringVar(value="0.00")
        self._status_var = tk.StringVar(value="Ready. Enter a course to begin.")

        _configure_styles(root)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Configure the root window and assemble the three sections."""
        self._root.title(APP_TITLE)
        self._root.geometry(WINDOW_SIZE)
        self._root.minsize(MIN_WIDTH, MIN_HEIGHT)

        container = ttk.Frame(self._root, padding=SECTION_PADDING)
        container.pack(fill=tk.BOTH, expand=True)

        self._build_input_section(container)

        ttk.Separator(container, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=SECTION_PADDING
        )

        self._build_table_section(container)

        ttk.Separator(container, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=SECTION_PADDING
        )

        self._build_result_section(container)

    def _build_input_section(self, parent: ttk.Frame) -> None:
        """Build the course name / credit / score input fields and Add button."""
        frame = ttk.LabelFrame(parent, text="Add Course", padding=INPUT_PADDING)
        frame.pack(fill=tk.X)

        self._name_entry = ttk.Entry(
            frame, textvariable=self._name_var, width=ENTRY_WIDTH
        )
        self._credit_entry = ttk.Entry(
            frame, textvariable=self._credit_var, width=ENTRY_WIDTH
        )
        self._score_entry = ttk.Entry(
            frame, textvariable=self._score_var, width=ENTRY_WIDTH
        )

        ttk.Label(frame, text="Course Name").grid(
            row=0, column=0, sticky=tk.W, pady=4
        )
        self._name_entry.grid(row=0, column=1, sticky=tk.EW, pady=4, padx=(12, 0))

        ttk.Label(frame, text="Credit").grid(
            row=1, column=0, sticky=tk.W, pady=4
        )
        self._credit_entry.grid(row=1, column=1, sticky=tk.EW, pady=4, padx=(12, 0))

        ttk.Label(frame, text="Score").grid(
            row=2, column=0, sticky=tk.W, pady=4
        )
        self._score_entry.grid(row=2, column=1, sticky=tk.EW, pady=4, padx=(12, 0))

        frame.columnconfigure(1, weight=1)

        ttk.Button(
            frame, text="Add Course", command=self._add_course, width=16
        ).grid(row=3, column=0, columnspan=2, pady=(10, 0))

        self._name_entry.focus_set()

    def _build_table_section(self, parent: ttk.Frame) -> None:
        """Build the courses Treeview, scrollbar, and management buttons."""
        frame = ttk.LabelFrame(parent, text="Courses", padding=INPUT_PADDING)
        frame.pack(fill=tk.BOTH, expand=True)

        tree_container = ttk.Frame(frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self._tree = ttk.Treeview(
            tree_container,
            columns=TABLE_COLUMNS,
            show="headings",
            height=TABLE_VISIBLE_ROWS,
        )
        for column_id, heading in TABLE_HEADINGS.items():
            self._tree.heading(column_id, text=heading)
            anchor = tk.W if column_id == "name" else tk.E
            self._tree.column(
                column_id, width=130, anchor=anchor, stretch=True
            )

        scrollbar = ttk.Scrollbar(
            tree_container, orient=tk.VERTICAL, command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click on a row to edit it (also selects the row).
        self._tree.bind("<Double-1>", self._on_row_double_click)

        button_row = ttk.Frame(frame)
        button_row.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(
            button_row,
            text="Clear All",
            command=self._clear_all_courses,
            width=14,
        ).pack(side=tk.RIGHT)
        ttk.Button(
            button_row,
            text="Delete Selected",
            command=self._delete_selected_course,
            width=16,
        ).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(
            button_row,
            text="Edit Selected",
            command=self._edit_selected_course,
            width=14,
        ).pack(side=tk.RIGHT, padx=(0, 8))

    def _build_result_section(self, parent: ttk.Frame) -> None:
        """Build the GPA display, Calculate button, and status label."""
        row = ttk.Frame(parent)
        row.pack(fill=tk.X)

        ttk.Label(row, text="Overall GPA:").pack(side=tk.LEFT)
        ttk.Label(
            row,
            textvariable=self._gpa_var,
            font=FONT_LARGE,
        ).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Button(
            row, text="Calculate GPA", command=self._calculate_gpa, width=16
        ).pack(side=tk.RIGHT)

        ttk.Label(parent, textvariable=self._status_var).pack(
            anchor=tk.W, pady=(10, 0)
        )

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
            self._set_status(error)
            _focus_from_error(
                error, self._name_entry, self._credit_entry, self._score_entry
            )
            return

        self._courses.append(course)
        self._refresh_course_table()
        self._update_gpa_display()
        self._clear_input_fields()
        self._set_status(f"Added: {course['name']}")

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
            self._set_status(
                "No course selected. Click a row in the table first."
            )
            return
        self._open_edit_dialog(index)

    def _open_edit_dialog(self, index: int) -> None:
        """Show the edit dialog and apply its result back to the list."""
        original_name = self._courses[index]["name"]
        dialog = CourseEditDialog(self._root, self._courses[index])
        self._root.wait_window(dialog.window)

        if dialog.result is None:
            self._set_status("Edit cancelled.")
            return

        self._courses[index] = dialog.result
        self._refresh_course_table()
        self._update_gpa_display()

        new_name = dialog.result["name"]
        if new_name == original_name:
            self._set_status(f"Updated: {new_name}")
        else:
            self._set_status(f"Renamed: {original_name} → {new_name}")

    def _delete_selected_course(self) -> None:
        """Remove the currently selected course from the list."""
        index = self._selected_course_index()
        if index is None:
            self._set_status(
                "No course selected. Click a row in the table first."
            )
            return

        removed = self._courses.pop(index)
        self._refresh_course_table()
        self._update_gpa_display()
        self._set_status(f"Deleted: {removed['name']}")

    def _clear_all_courses(self) -> None:
        """Remove every course after asking the user to confirm."""
        if not self._courses:
            self._set_status("No courses to clear.")
            return

        confirmed = messagebox.askyesno(
            "Confirm Clear",
            f"Are you sure you want to clear all {len(self._courses)} "
            "course(s)?",
        )
        if not confirmed:
            self._set_status("Clear cancelled.")
            return

        count = len(self._courses)
        self._courses.clear()
        self._refresh_course_table()
        self._update_gpa_display()
        self._set_status(f"Cleared {count} course(s).")

    def _calculate_gpa(self) -> None:
        """Explicit recompute action for the GPA label."""
        if not self._courses:
            self._set_status("No courses added yet.")
            return
        self._update_gpa_display()
        self._set_status(
            f"Calculated GPA over {len(self._courses)} course(s)."
        )

    # ------------------------------------------------------------------
    # View sync
    # ------------------------------------------------------------------

    def _refresh_course_table(self) -> None:
        """Re-render the Treeview from ``self._courses``.

        Each row is inserted with ``iid=str(index)`` so that
        :meth:`_selected_course_index` can translate the Treeview's
        selection back to a stable list index without scanning.
        """
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
        """Recompute the weighted GPA from ``self._courses``.

        Resets to ``"0.00"`` when the list is empty so the label never
        displays a stale value.
        """
        if not self._courses:
            self._gpa_var.set("0.00")
            return
        gpa = calculate_gpa(self._courses)
        self._gpa_var.set(f"{gpa:.2f}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _selected_course_index(self) -> Optional[int]:
        """Resolve the currently selected Treeview row to a list index.

        Returns ``None`` if nothing is selected, the iid is not numeric,
        or the row no longer exists in ``self._courses``.
        """
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


def main() -> None:
    """Launch the GPA Manager GUI with high-DPI support."""
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    _sync_tk_scaling(root)
    GpaManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()