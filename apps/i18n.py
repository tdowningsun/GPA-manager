"""Internationalization (i18n) system for GPA Manager v4.3.

Provides:

  * ``t(key, **kwargs)`` - look up a translation by key for the active
    locale. Falls back to the Traditional-Chinese value when the
    active locale is missing a key, then to the key itself so the UI
    never crashes on an incomplete dictionary.
  * ``set_locale(code)`` - switch the active locale and notify every
    registered listener so widgets can refresh their text without
    restarting the app.
  * ``add_listener(callback)`` / ``remove_listener(callback)`` - subscribe
    to locale-change events. Callbacks receive the new locale code.

This module is intentionally Tk-free - it has no imports from
``gui`` / ``tkinter`` - so any layer of the application can use it.
"""

from typing import Any, Callable

# Locale codes used throughout the app.
LOCALE_ZH_TW = "zh-TW"
LOCALE_EN = "en"

# Ordered tuple - iterated when building the language menu so the menu
# order matches the visual order in the spec.
AVAILABLE_LOCALES: tuple[str, ...] = (LOCALE_ZH_TW, LOCALE_EN)

# Default locale is Traditional Chinese per the product spec.
DEFAULT_LOCALE: str = LOCALE_ZH_TW

# Mutable module-level state.
_CURRENT_LOCALE: str = DEFAULT_LOCALE
_LISTENERS: list[Callable[[str], None]] = []


# ---------------------------------------------------------------------------
# Translation table.
# ---------------------------------------------------------------------------
#
# Each key has a translation for every supported locale. Missing entries
# fall back to the Traditional-Chinese value (and ultimately to the key
# itself) so the UI keeps rendering even with an incomplete dictionary.
# Values that contain ``{name}`` / ``{value}`` / etc. are formatted via
# ``str.format`` when ``t()`` is called with matching kwargs.

_STRINGS: dict[str, dict[str, str]] = {
    LOCALE_ZH_TW: {
        # App / sidebar
        "app.title": "GPA Manager",
        "app.brand": "GPA Manager",
        "nav.single": "單一學期",
        "nav.multi": "多學期",
        "nav.target": "目標 GPA",

        # Sidebar utility items
        "sidebar.gpa_rules": "GPA 規則...",
        "sidebar.language": "語言...",
        "sidebar.about": "關於",
        "sidebar.gpa_rules.open_error.title": "無法開啟檔案",
        "sidebar.gpa_rules.open_error.message": "無法開啟 {path}。",

        # About dialog
        "about.title": "關於",
        "about.app_name": "GPA Manager",
        "about.version_label": "版本",
        "about.gpa_scale_label": "目前 GPA 規則",
        "about.language_label": "目前語言",
        "about.python_label": "Python 執行環境",
        "about.copyright": "Copyright © 2026 Sun YiMing",
        "about.tagline": "使用 Python 與 Tkinter 構建",
        "about.ok": "確定",
        "about.info_row": "{label}：{value}",
        "about.url": "https://github.com/tdowningsun",

        # Page titles
        "page.title.single": "單一學期 GPA",
        "page.title.multi": "多學期 GPA",
        "page.title.target": "目標 GPA",

        # Section (LabelFrame) labels
        "page.section.add_course": "新增課程",
        "page.section.add_semester": "新增學期",
        "page.section.target_inputs": "目標輸入",
        "page.section.course_list": "課程清單",
        "page.section.semester_list": "學期清單",
        "page.section.required_gpa": "所需 GPA",
        "page.section.overall_gpa": "整體 GPA",

        # Form-field labels
        "form.label.course_name": "課程名稱",
        "form.label.credit": "學分",
        "form.label.score": "成績",
        "form.label.semester_name": "學期名稱",
        "form.label.current_gpa": "目前 GPA",
        "form.label.completed_credits": "已修學分",
        "form.label.remaining_credits": "剩餘學分",
        "form.label.target_gpa": "目標 GPA",

        # Buttons
        "button.add_course": "新增課程",
        "button.add_semester": "新增學期",
        "button.calculate_gpa": "計算 GPA",
        "button.calculate": "計算",
        "button.edit_selected": "編輯選取",
        "button.delete_selected": "刪除選取",
        "button.clear_all": "全部清除",
        "button.open_semester": "開啟學期",
        "button.rename": "重新命名",
        "button.delete": "刪除",
        "button.save": "儲存",
        "button.cancel": "取消",

        # Treeview column headings
        "tree.header.course_name": "課程名稱",
        "tree.header.credit": "學分",
        "tree.header.score": "成績",
        "tree.header.grade_point": "GPA 點數",
        "tree.header.semester": "學期",
        "tree.header.credits": "學分",
        "tree.header.gpa": "GPA",

        # Result-card label / placeholders
        "result.overall_gpa_label": "整體 GPA：",
        "result.placeholder.helper_required":
            "你需要在剩餘的 {remaining} 學分中達到平均 {required:.2f} GPA，"
            "才能達到目標 GPA {target:.2f}。",
        "result.placeholder.helper_already":
            "你的目標 GPA {target:.2f} 已透過目前 GPA {current:.2f} 達成。",
        "result.placeholder.helper_unreachable":
            "所需 GPA {required:.2f} 高於最高可能 GPA {max:.1f}，"
            "你的目標 GPA {target:.2f} 無法以剩餘學分達成。",
        "result.placeholder.helper_initial":
            "點擊「計算」查看為達成目標 GPA，"
            "在剩餘學分中所需的 GPA。",

        # Status messages
        "status.ready.single": "準備就緒。請輸入課程資料開始計算。",
        "status.ready.multi": "準備就緒。請輸入學期名稱開始計算。",
        "status.ready.target": "請輸入上方資料並點擊「計算」。",
        "status.add_course.begin": "新增一門課程開始。",
        "status.added": "已新增：{name}",
        "status.deleted": "已刪除：{name}",
        "status.renamed": "已重新命名：{old} → {new}",
        "status.opened": "已開啟：{name}",
        "status.calculated": "計算完成：所需 GPA 為 {required:.2f}。",
        "status.cleared": "已清除 {count} 筆課程。",
        "status.no_courses_to_clear": "沒有可清除的課程。",
        "status.no_courses_to_calculate": "尚未新增任何課程。",
        "status.calculated_gpa":
            "已計算 GPA：{gpa}，共 {count} 門課程。",
        "status.updated": "已更新：{name}",
        "status.edit_cancelled": "已取消編輯。",
        "status.clear_cancelled": "已取消清除。",
        "status.no_selection_course":
            "未選取課程。請先點選表格中的一列。",
        "status.no_selection_semester":
            "未選取學期。請先點選表格中的一列。",
        "status.placeholder_open": "佔位功能：將開啟所選的學期。",
        "status.placeholder_rename": "佔位功能：將重新命名所選的學期。",

        # Validation error keys returned by _validate_course_fields
        "validation.name_empty": "課程名稱不可為空。",
        "validation.semester_name_empty": "學期名稱不可為空。",
        "validation.credit_invalid": "無效的學分「{value}」，請輸入數字。",
        "validation.credit_non_positive": "學分必須大於 0。",
        "validation.score_invalid":
            "無效的成績「{value}」，請輸入數字或文字"
            "（及格／中等／良好／優秀）。",

        # Target-GPA validation / status
        "target.invalid_current": "目前 GPA 必須是有效的數字。",
        "target.invalid_completed": "已修學分必須是有效的數字。",
        "target.invalid_remaining": "剩餘學分必須是有效的數字。",
        "target.invalid_target": "目標 GPA 必須是有效的數字。",
        "target.completed_non_positive": "已修學分必須大於 0。",
        "target.remaining_non_positive": "剩餘學分必須大於 0。",
        "target.already_achieved":
            "目標已達成（目前 {current:.2f} ≥ 目標 {target:.2f}）。",
        "target.cannot_reach":
            "目標 GPA {target:.2f} 無法達成"
            "（所需 {required:.2f} > 最高 {max:.1f}）。",

        # Dialogs
        "dialog.edit_course.title": "編輯課程",
        "dialog.edit_semester.title": "編輯學期：{name}",
        "dialog.summary.credits_label": "學分：",
        "dialog.summary.gpa_label": "GPA：",

        # Confirmation dialogs
        "confirm.clear_all.title": "確認清除",
        "confirm.clear_all.message": "確定要清除全部 {count} 筆課程嗎？",

        # Language menu
        "language.menu.label": "語言",
        "locale.zh-TW": "繁體中文",
        "locale.en": "English",
        "language.changed": "語言已切換為 {locale}。",
    },
    LOCALE_EN: {
        # App / sidebar
        "app.title": "GPA Manager",
        "app.brand": "GPA Manager",
        "nav.single": "Single Semester",
        "nav.multi": "Multi-Semester",
        "nav.target": "Target GPA",

        # Sidebar utility items
        "sidebar.gpa_rules": "GPA Rules...",
        "sidebar.language": "Language...",
        "sidebar.about": "About",
        "sidebar.gpa_rules.open_error.title": "Cannot open file",
        "sidebar.gpa_rules.open_error.message": "Failed to open {path}.",

        # About dialog
        "about.title": "About",
        "about.app_name": "GPA Manager",
        "about.version_label": "Version",
        "about.gpa_scale_label": "Current GPA Scale",
        "about.language_label": "Current Language",
        "about.python_label": "Python Runtime",
        "about.copyright": "Copyright © 2026 Sun YiMing",
        "about.tagline": "Built with Python & Tkinter",
        "about.ok": "OK",
        "about.info_row": "{label}: {value}",
        "about.url": "https://github.com/tdowningsun",

        # Page titles
        "page.title.single": "Single Semester GPA",
        "page.title.multi": "Multi-Semester GPA",
        "page.title.target": "Target GPA",

        # Section labels
        "page.section.add_course": "Add Course",
        "page.section.add_semester": "Add Semester",
        "page.section.target_inputs": "Target Inputs",
        "page.section.course_list": "Course List",
        "page.section.semester_list": "Semester List",
        "page.section.required_gpa": "Required GPA",
        "page.section.overall_gpa": "Overall GPA",

        # Form-field labels
        "form.label.course_name": "Course Name",
        "form.label.credit": "Credit",
        "form.label.score": "Score",
        "form.label.semester_name": "Semester Name",
        "form.label.current_gpa": "Current GPA",
        "form.label.completed_credits": "Completed Credits",
        "form.label.remaining_credits": "Remaining Credits",
        "form.label.target_gpa": "Target GPA",

        # Buttons
        "button.add_course": "Add Course",
        "button.add_semester": "Add Semester",
        "button.calculate_gpa": "Calculate GPA",
        "button.calculate": "Calculate",
        "button.edit_selected": "Edit Selected",
        "button.delete_selected": "Delete Selected",
        "button.clear_all": "Clear All",
        "button.open_semester": "Open Semester",
        "button.rename": "Rename",
        "button.delete": "Delete",
        "button.save": "Save",
        "button.cancel": "Cancel",

        # Treeview column headings
        "tree.header.course_name": "Course Name",
        "tree.header.credit": "Credit",
        "tree.header.score": "Score",
        "tree.header.grade_point": "Grade Point",
        "tree.header.semester": "Semester",
        "tree.header.credits": "Credits",
        "tree.header.gpa": "GPA",

        # Result-card label / placeholders
        "result.overall_gpa_label": "Overall GPA:",
        "result.placeholder.helper_required":
            "You need an average GPA of {required:.2f} over your "
            "remaining {remaining} credits to reach your target GPA of "
            "{target:.2f}.",
        "result.placeholder.helper_already":
            "Your target GPA of {target:.2f} has already been achieved "
            "with your current GPA of {current:.2f}.",
        "result.placeholder.helper_unreachable":
            "The required GPA of {required:.2f} is higher than the "
            "maximum possible GPA of {max:.1f}. Your target of "
            "{target:.2f} is unachievable with the remaining credits.",
        "result.placeholder.helper_initial":
            "Click Calculate to see the GPA you need over your "
            "remaining credits to reach your target.",

        # Status messages
        "status.ready.single": "Ready. Enter a course to begin.",
        "status.ready.multi": "Ready. Enter a semester name to begin.",
        "status.ready.target": "Enter your data above and click Calculate.",
        "status.add_course.begin": "Add a course to begin.",
        "status.added": "Added: {name}",
        "status.deleted": "Deleted: {name}",
        "status.renamed": "Renamed: {old} → {new}",
        "status.opened": "Opened: {name}",
        "status.calculated":
            "Calculated: required GPA is {required:.2f}.",
        "status.cleared": "Cleared {count} course(s).",
        "status.no_courses_to_clear": "No courses to clear.",
        "status.no_courses_to_calculate": "No courses added yet.",
        "status.calculated_gpa":
            "Calculated GPA: {gpa} over {count} course(s).",
        "status.updated": "Updated: {name}",
        "status.edit_cancelled": "Edit cancelled.",
        "status.clear_cancelled": "Clear cancelled.",
        "status.no_selection_course":
            "No course selected. Click a row in the table first.",
        "status.no_selection_semester":
            "No semester selected. Click a row in the table first.",
        "status.placeholder_open":
            "Placeholder: would open the selected semester.",
        "status.placeholder_rename":
            "Placeholder: would rename the selected semester.",

        # Validation
        "validation.name_empty": "Course name cannot be empty.",
        "validation.semester_name_empty": "Semester name cannot be empty.",
        "validation.credit_invalid":
            "Invalid credit '{value}'. Please enter a number.",
        "validation.credit_non_positive": "Credit must be greater than 0.",
        "validation.score_invalid":
            "Invalid score '{value}'. Use a number or text "
            "(及格/中等/良好/优秀).",

        # Target-GPA
        "target.invalid_current": "Current GPA must be a valid number.",
        "target.invalid_completed": "Completed Credits must be a valid number.",
        "target.invalid_remaining": "Remaining Credits must be a valid number.",
        "target.invalid_target": "Target GPA must be a valid number.",
        "target.completed_non_positive": "Completed Credits must be greater than 0.",
        "target.remaining_non_positive": "Remaining Credits must be greater than 0.",
        "target.already_achieved":
            "Target already achieved "
            "(current {current:.2f} >= target {target:.2f}).",
        "target.cannot_reach":
            "Target GPA {target:.2f} cannot be reached "
            "(required {required:.2f} > max {max:.1f}).",

        # Dialogs
        "dialog.edit_course.title": "Edit Course",
        "dialog.edit_semester.title": "Edit Semester: {name}",
        "dialog.summary.credits_label": "Credits:",
        "dialog.summary.gpa_label": "GPA:",

        # Confirmation
        "confirm.clear_all.title": "Confirm Clear",
        "confirm.clear_all.message":
            "Are you sure you want to clear all {count} course(s)?",

        # Language menu
        "language.menu.label": "Language",
        "locale.zh-TW": "Traditional Chinese",
        "locale.en": "English",
        "language.changed": "Language changed to {locale}.",
    },
}


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


def t(key: str, /, **kwargs: Any) -> str:
    """Return the translation of ``key`` for the active locale.

    Falls back to the Traditional-Chinese value if the active locale
    is missing the key, and finally to the key itself so the UI never
    crashes on an incomplete dictionary.

    Format placeholders (``{name}``, ``{value}`` ...) are expanded
    from ``kwargs`` via :py:meth:`str.format`.
    """
    table = _STRINGS.get(_CURRENT_LOCALE) or _STRINGS[DEFAULT_LOCALE]
    value = table.get(key) or _STRINGS[DEFAULT_LOCALE].get(key) or key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            # The translation template expects an arg we didn't pass
            # (or got the format wrong). Return the raw template so the
            # user can still read the structure.
            return value
    return value


def t_values(key: str) -> tuple[str, ...]:
    """Return every supported locale's translation of ``key``.

    Useful for the locale-change checks in :mod:`gui` that need to
    detect "the status is still the initial placeholder" by comparing
    the current widget text against every locale's value of a given
    translation key. Falling back to the default locale's value (and
    finally to the key itself) for any locale that does not define
    the key keeps the comparison stable as translations evolve.
    """
    fallback = _STRINGS[DEFAULT_LOCALE].get(key, key)
    return tuple(
        (_STRINGS.get(locale) or _STRINGS[DEFAULT_LOCALE]).get(
            key, fallback
        )
        for locale in AVAILABLE_LOCALES
    )


def current_locale() -> str:
    """Return the active locale code (e.g. ``"zh-TW"``)."""
    return _CURRENT_LOCALE


def current_locale_label() -> str:
    """Return the human-readable label of the active locale."""
    return t(f"locale.{_CURRENT_LOCALE}")


def set_locale(locale: str) -> bool:
    """Switch the active locale and notify all registered listeners.

    Returns ``True`` if the locale changed, ``False`` if the locale
    was unknown or already active.
    """
    global _CURRENT_LOCALE
    if locale not in AVAILABLE_LOCALES or locale == _CURRENT_LOCALE:
        return False
    _CURRENT_LOCALE = locale
    for listener in list(_LISTENERS):
        try:
            listener(locale)
        except Exception:
            # A buggy listener must not prevent other listeners from
            # being notified.
            pass
    return True


def add_listener(callback: Callable[[str], None]) -> None:
    """Register ``callback`` to be invoked on every locale change.

    The callback receives the new locale code. Registering the same
    callback twice is a no-op.
    """
    if callback not in _LISTENERS:
        _LISTENERS.append(callback)


def remove_listener(callback: Callable[[str], None]) -> None:
    """Unregister a previously-added locale-change callback."""
    if callback in _LISTENERS:
        _LISTENERS.remove(callback)
