import dataclasses
import json

import pytest

from fly_notes.model.task import MAX_TEXT_LENGTH, Task


def test_new_task_gets_a_unique_id():
    a, b = Task.new("a"), Task.new("b")
    assert a.id and b.id and a.id != b.id
    assert a.completed is False
    assert Task.new("done", completed=True).completed is True


def test_task_is_immutable():
    task = Task.new("a")
    with pytest.raises(dataclasses.FrozenInstanceError):
        task.text = "b"  # type: ignore[misc]
    assert dataclasses.replace(task, text="b") == Task(id=task.id, text="b", completed=False)


def test_to_dict_matches_the_tasks_json_format():
    task = Task(id="abc", text="Hello", completed=True)
    assert task.to_dict() == {"id": "abc", "text": "Hello", "completed": True}
    assert json.loads(json.dumps(task.to_dict())) == task.to_dict()


def test_from_dict_round_trips_to_dict():
    task = Task(id="abc", text="Hello", completed=True)
    assert Task.from_dict(task.to_dict()) == task


def test_from_dict_normalises_values():
    task = Task.from_dict({"text": "Hello", "completed": "True"})
    assert task.text == "Hello"
    assert task.completed is True
    assert isinstance(task.id, str) and task.id

    assert Task.from_dict({"id": "x", "text": 42}).text == "42"
    assert Task.from_dict({"id": "x"}) == Task(id="x", text="", completed=False)


@pytest.mark.parametrize("bad_id", [None, 1, "", "   ", ["x"]])
def test_from_dict_replaces_an_invalid_id(bad_id):
    task = Task.from_dict({"id": bad_id, "text": "t"})
    assert isinstance(task.id, str) and task.id.strip()


def test_from_dict_truncates_oversized_text():
    task = Task.from_dict({"id": "x", "text": "a" * (MAX_TEXT_LENGTH + 5)})
    assert len(task.text) == MAX_TEXT_LENGTH


@pytest.mark.parametrize("raw", ["not a dict", 3, None, ["id", "text"]])
def test_from_dict_rejects_non_dicts(raw):
    with pytest.raises(TypeError):
        Task.from_dict(raw)
