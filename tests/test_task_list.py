"""TaskListView: scrolling, grouping, the row cap and the 'Show N more' link."""

import random
import tkinter as tk

import pytest

from fly_notes.config import _CONTRAST_PAIRS
from fly_notes.model.store import TaskManager
from fly_notes.ui.task_item import TaskItem
from fly_notes.ui.task_list import TaskListView

# ── max_visible_tasks ─────────────────────────


def test_repack_caps_rendered_rows_to_max_visible_tasks(root, cfg):
    """With max_visible_tasks=3 and 5 tasks loaded, at most 3 task rows
    are actually packed (rendered) — the rest stay unpacked, with a
    '+N more' indicator instead."""
    cfg = cfg.with_settings(max_visible_tasks=3)
    task_list = TaskListView(root, cfg)
    widgets = []
    for i in range(5):
        w = TaskItem(task_list.inner_frame, cfg, task_id=str(i), text=f"Task {i}")
        task_list.add_widget(w)
        widgets.append(w)

    try:
        task_list.repack()
        packed = [w for w in widgets if w.winfo_manager()]
        assert len(packed) == 3
        assert packed == widgets[:3]

        indicator_texts = [
            w.cget("text") for w in task_list.inner_frame.pack_slaves() if isinstance(w, tk.Label)
        ]
        assert cfg.string("more_hidden", count=2) in indicator_texts
    finally:
        for w in widgets:
            w.destroy()
        task_list.destroy()


# ── Scroll affordance ─────────────────────────


def test_scrollbar_activates_when_content_exceeds_visible_height(root, cfg):
    """With enough tasks to overflow a short window, the scrollbar must
    become visible (packed): with 11+ tasks the scrollbar used to be
    barely perceptible."""
    win = tk.Toplevel(root)
    try:
        win.geometry("320x150+0+0")
        task_list = TaskListView(win, cfg)
        task_list.pack(fill="both", expand=True)
        win.update_idletasks()

        widgets = []
        for i in range(20):
            w = TaskItem(task_list.inner_frame, cfg, task_id=str(i), text=f"Task {i}")
            task_list.add_widget(w)
            widgets.append(w)
        task_list.repack()
        win.update_idletasks()

        assert task_list._scrollbar_visible is True
        assert task_list._scrollbar.winfo_manager() == "pack"

        for w in widgets:
            w.destroy()
        task_list.destroy()
    finally:
        win.destroy()


def test_scrollbar_stays_hidden_when_content_fits(root, cfg):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x440+0+0")
        task_list = TaskListView(win, cfg)
        task_list.pack(fill="both", expand=True)
        win.update_idletasks()

        widgets = []
        for i in range(2):
            w = TaskItem(task_list.inner_frame, cfg, task_id=str(i), text=f"Task {i}")
            task_list.add_widget(w)
            widgets.append(w)
        task_list.repack()
        win.update_idletasks()

        assert task_list._scrollbar_visible is False

        for w in widgets:
            w.destroy()
        task_list.destroy()
    finally:
        win.destroy()


def test_scroll_increment_matches_task_row_height_to_prevent_split_rows(root, cfg):
    """yscrollincrement must equal a whole task row's footprint, so Tk's
    canvas can never leave a row rendered half-visible at the viewport
    edge (the last row used to be cut in half with no affordance)."""
    win = tk.Toplevel(root)
    try:
        win.geometry("320x150+0+0")
        task_list = TaskListView(win, cfg)
        task_list.pack(fill="both", expand=True)

        widgets = []
        for i in range(10):
            w = TaskItem(task_list.inner_frame, cfg, task_id=str(i), text=f"Task {i}")
            task_list.add_widget(w)
            widgets.append(w)
        task_list.repack()
        win.update_idletasks()

        expected = min(w.winfo_reqheight() for w in widgets) + 2 * cfg.spacing.xs
        assert int(task_list._canvas["yscrollincrement"]) == expected

        for w in widgets:
            w.destroy()
        task_list.destroy()
    finally:
        win.destroy()


# ── Keyboard navigation (#13) ─────────────────


def test_ensure_visible_scrolls_a_row_into_view(root, cfg):
    win = tk.Toplevel(root)
    try:
        win.geometry("320x150+0+0")
        task_list = TaskListView(win, cfg)
        task_list.pack(fill="both", expand=True)
        widgets = []
        for i in range(15):
            w = TaskItem(task_list.inner_frame, cfg, task_id=str(i), text=f"Task {i}")
            task_list.add_widget(w)
            widgets.append(w)
        task_list.repack()
        win.update()
        assert task_list._canvas.canvasy(0) == 0

        task_list.ensure_visible(widgets[-1])
        win.update()
        view_top = task_list._canvas.canvasy(0)
        view_bottom = view_top + task_list._canvas.winfo_height()
        last = widgets[-1]
        assert view_top > 0
        assert last.winfo_y() + last.winfo_height() <= view_bottom + 1

        task_list.ensure_visible(widgets[0])
        win.update()
        assert task_list._canvas.canvasy(0) <= widgets[0].winfo_y()
    finally:
        win.destroy()


# ── Section header hierarchy ──────────────────


def test_section_headers_are_uppercase_bold_and_use_dedicated_color(root, tmp_path, cfg):
    """Regression for 'headers look like secondary body text': pending/
    completed section headers must render uppercase, in font_section
    (now bold), and in the dedicated section_header colour -- distinct
    from the plain text_secondary/font_footer '+N more' hint."""
    manager = TaskManager(tasks_file=str(tmp_path / "tasks.json"))
    task_a = manager.add_task("Pending A")
    task_b = manager.add_task("Done B", completed=True)

    task_list = TaskListView(root, cfg)
    widgets = []
    for t in (task_a, task_b):
        w = TaskItem(task_list.inner_frame, cfg, task_id=t.id, text=t.text, completed=t.completed)
        task_list.add_widget(w)
        widgets.append(w)
    task_list.repack()

    labels = [w for w in task_list.inner_frame.pack_slaves() if isinstance(w, tk.Label)]
    texts = {lbl.cget("text") for lbl in labels}
    assert "TO DO (1)" in texts
    assert "COMPLETED (1)" in texts
    for lbl in labels:
        assert lbl.cget("fg") == cfg.colors.section_header
        assert "bold" in str(lbl.cget("font"))

    for w in widgets:
        w.destroy()
    task_list.destroy()


def test_more_hidden_indicator_keeps_plain_style_not_header_style(root, cfg):
    """The 'Show N more' link is a meta note, not a structural separator --
    it must stay lowercase and use link_color/font_footer, not the bold
    uppercase section_header treatment."""
    cfg = cfg.with_settings(max_visible_tasks=3)
    task_list = TaskListView(root, cfg)
    widgets = []
    for i in range(5):
        w = TaskItem(task_list.inner_frame, cfg, task_id=str(i), text=f"Task {i}")
        task_list.add_widget(w)
        widgets.append(w)

    try:
        task_list.repack()
        more_label = next(
            w
            for w in task_list.inner_frame.pack_slaves()
            if isinstance(w, tk.Label) and "more" in w.cget("text")
        )
        assert more_label.cget("text") == cfg.string("more_hidden", count=2)
        assert more_label.cget("fg") == cfg.colors.link_color
        assert "bold" not in str(more_label.cget("font"))
    finally:
        for w in widgets:
            w.destroy()
        task_list.destroy()


# ── "Show N more" is actionable (#12) ─────────


@pytest.fixture
def capped_list(root, monkeypatch, cfg):
    """A TaskListView with 8 tasks and max_visible_tasks=3."""
    cfg = cfg.with_settings(max_visible_tasks=3)
    task_list = TaskListView(root, cfg)
    widgets = []
    for i in range(8):
        w = TaskItem(task_list.inner_frame, cfg, task_id=str(i), text=f"Task {i}")
        task_list.add_widget(w)
        widgets.append(w)
    task_list.repack()
    yield task_list, widgets
    task_list.destroy()


def _show_more_link(task_list):
    links = [
        w
        for w in task_list.inner_frame.pack_slaves()
        if isinstance(w, tk.Label) and w.cget("cursor") == "hand2"
    ]
    return links[0] if links else None


def _packed_ids(widgets):
    return [w.task_id for w in widgets if w.winfo_manager()]


def test_show_more_link_names_the_next_page_and_the_total(capped_list, cfg):
    task_list, widgets = capped_list
    link = _show_more_link(task_list)
    assert link is not None
    assert link.cget("text") == cfg.string("more_hidden_paged", count=3, hidden=5)
    assert _packed_ids(widgets) == ["0", "1", "2"]


def test_clicking_show_more_reveals_one_page_at_a_time(capped_list, cfg):
    task_list, widgets = capped_list

    link = _show_more_link(task_list)
    assert link is not None
    link.event_generate("<Button-1>")
    assert _packed_ids(widgets) == ["0", "1", "2", "3", "4", "5"]
    link = _show_more_link(task_list)
    assert link is not None
    assert link.cget("text") == cfg.string("more_hidden", count=2)

    link.event_generate("<Button-1>")
    assert _packed_ids(widgets) == [str(i) for i in range(8)]
    assert _show_more_link(task_list) is None


def test_show_more_works_from_the_keyboard(capped_list):
    task_list, _ = capped_list
    link = _show_more_link(task_list)
    assert link is not None
    assert int(link.cget("takefocus")) == 1
    assert link.bind("<Return>")
    assert link.bind("<space>")


def test_revealed_rows_stay_visible_after_a_repack(capped_list):
    """Adding/toggling a task repacks the list: it must not collapse again."""
    task_list, widgets = capped_list
    task_list.show_more()
    task_list.repack()
    assert len(_packed_ids(widgets)) == 6


def test_link_color_is_validated_against_the_list_background():

    assert ("link_color", "content_bg", 4.5) in _CONTRAST_PAIRS


# ── Scrolling over a row ─────────────────────


def test_wheel_over_any_part_of_a_row_scrolls_the_list(root, cfg):
    """TaskItem.bind_scroll routes the wheel from every child widget, including
    the content frame around the text, which the list used to miss."""
    task_list = TaskListView(root, cfg)
    item = TaskItem(task_list.inner_frame, cfg, task_id="1", text="Task")
    task_list.add_widget(item)
    parts = (item, item._card_canvas, item._content, item._label, item._check, item._delete_btn)
    try:
        for part in parts:
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                assert part.bind(sequence), (part, sequence)
    finally:
        task_list.destroy()


# ── Incremental repack (#25) ──────────────────


def _list_with(root, cfg, count, completed=()):
    task_list = TaskListView(root, cfg)
    widgets = []
    for i in range(count):
        w = TaskItem(
            task_list.inner_frame, cfg, task_id=str(i), text=f"Task {i}", completed=i in completed
        )
        task_list.add_widget(w)
        widgets.append(w)
    task_list.repack()
    return task_list, widgets


def _packed_rows(task_list):
    """Task rows in the order they are packed (what the user sees, top to bottom)."""
    return [w for w in task_list.inner_frame.pack_slaves() if isinstance(w, TaskItem)]


def _spy_pack(widgets):
    """Record which widgets get packed (moved) from now on."""
    calls = []
    for w in widgets:
        real = w.pack

        def spy(*args, _w=w, _real=real, **kwargs):
            calls.append(_w.task_id)
            _real(*args, **kwargs)

        w.pack = spy
    return calls


def test_repack_reuses_section_headers_and_updates_their_counts(root, cfg):
    task_list, widgets = _list_with(root, cfg, 3, completed={2})
    try:
        children = set(task_list.inner_frame.winfo_children())
        widgets[0].completed_var.set(True)
        task_list.repack()

        assert set(task_list.inner_frame.winfo_children()) == children
        texts = [
            w.cget("text") for w in task_list.inner_frame.pack_slaves() if isinstance(w, tk.Label)
        ]
        assert texts == ["TO DO (1)", "COMPLETED (2)"]
        assert _packed_rows(task_list) == [widgets[1], widgets[0], widgets[2]]
    finally:
        task_list.destroy()


def test_a_swap_moves_only_one_row(root, cfg):
    task_list, widgets = _list_with(root, cfg, 6)
    try:
        calls = _spy_pack(widgets)
        task_list.sync_order(["0", "1", "3", "2", "4", "5"])
        task_list.repack()

        assert calls == ["3"]
        assert [w.task_id for w in _packed_rows(task_list)] == ["0", "1", "3", "2", "4", "5"]
    finally:
        task_list.destroy()


def test_an_unchanged_repack_packs_nothing(root, cfg):
    task_list, widgets = _list_with(root, cfg, 4, completed={1})
    try:
        calls = _spy_pack(widgets)
        task_list.repack()
        assert calls == []
    finally:
        task_list.destroy()


@pytest.mark.parametrize("group_completed", [True, False])
def test_packing_follows_the_visual_order_through_any_sequence_of_changes(
    root, cfg, group_completed
):
    """Random adds, deletes, toggles and moves: after each repack the rows on
    screen are exactly the visual order, capped, with the headers in place."""
    rng = random.Random(25)
    cfg = cfg.with_settings(group_completed=group_completed, max_visible_tasks=5)
    task_list, _ = _list_with(root, cfg, 4)
    next_id = 4
    try:
        for _ in range(120):
            widgets = task_list.task_widgets
            op = rng.choice(["add", "delete", "toggle", "move"] if widgets else ["add"])
            if op == "add":
                w = TaskItem(task_list.inner_frame, cfg, task_id=str(next_id), text="t")
                next_id += 1
                task_list.add_widget(w, index=rng.randint(0, len(widgets)))
            elif op == "delete":
                task_list.remove_widget(rng.choice(widgets))
            elif op == "toggle":
                var = rng.choice(widgets).completed_var
                var.set(not var.get())
            else:
                ids = [w.task_id for w in widgets]
                ids.insert(rng.randint(0, len(ids) - 1), ids.pop(rng.randrange(len(ids))))
                task_list.sync_order(ids)
            task_list.repack()

            visible = task_list.visual_order()[: 5 + task_list._extra_visible]
            assert _packed_rows(task_list) == visible
            slaves = task_list.inner_frame.pack_slaves()
            if not task_list.task_widgets:
                assert slaves == [task_list._empty_label]
                continue
            assert slaves[-1] is task_list._spacer
            if group_completed:
                pending = [w for w in task_list.task_widgets if not w.completed_var.get()]
                if pending:
                    assert slaves[0] is task_list._pending_header
                if len(pending) < len(task_list.task_widgets):
                    header = slaves.index(task_list._completed_header)
                    assert all(
                        not w.completed_var.get()
                        for w in slaves[:header]
                        if isinstance(w, TaskItem)
                    )
    finally:
        task_list.destroy()


# ── Lazy rows (#26) ───────────────────────────


def test_rows_past_the_cap_are_built_only_when_shown(root, cfg):
    cfg = cfg.with_settings(max_visible_tasks=3)
    task_list = TaskListView(root, cfg)
    built = []

    def factory(i):
        def create():
            built.append(str(i))
            return TaskItem(task_list.inner_frame, cfg, task_id=str(i), text=f"Task {i}")

        return create

    try:
        for i in range(8):
            task_list.add_lazy(str(i), False, factory(i))
        assert built == []

        task_list.repack()
        assert built == ["0", "1", "2"]
        assert task_list.row_count == 8
        link = _show_more_link(task_list)
        assert link is not None
        assert link.cget("text") == cfg.string("more_hidden_paged", count=3, hidden=5)

        task_list.show_more()
        assert built == ["0", "1", "2", "3", "4", "5"]
        assert [w.task_id for w in _packed_rows(task_list)] == ["0", "1", "2", "3", "4", "5"]
    finally:
        task_list.destroy()


def test_a_lazy_row_keeps_its_group_and_can_be_removed(root, cfg):
    cfg = cfg.with_settings(max_visible_tasks=2)
    task_list = TaskListView(root, cfg)

    def create(i, done):
        return lambda: TaskItem(
            task_list.inner_frame, cfg, task_id=str(i), text="t", completed=done
        )

    try:
        for i, done in enumerate([True, False, False, True]):
            task_list.add_lazy(str(i), done, create(i, done))
        task_list.repack()

        # Pending first: the two pending rows are the ones built and shown.
        assert [r.task_id for r in task_list.visual_order()] == ["1", "2", "0", "3"]
        assert [w.task_id for w in task_list.task_widgets] == ["1", "2"]

        task_list.remove_task("3")  # never built
        task_list.repack()
        assert task_list.row_count == 3
        link = _show_more_link(task_list)
        assert link is not None
        assert link.cget("text") == cfg.string("more_hidden", count=1)
    finally:
        task_list.destroy()
