import pytest

from hodoku.core.cell_set import CellSet

pytestmark = pytest.mark.unit


def test_empty_on_init():
    s = CellSet()
    assert s.is_empty()
    assert s.size() == 0


def test_add_and_contains():
    s = CellSet()
    s.add(0)
    s.add(40)
    s.add(80)
    assert s.contains(0)
    assert s.contains(40)
    assert s.contains(80)
    assert not s.contains(1)
    assert s.size() == 3


def test_remove():
    s = CellSet()
    s.add(5)
    s.remove(5)
    assert not s.contains(5)
    assert s.is_empty()


def test_iteration():
    s = CellSet()
    indices = [0, 9, 18, 27, 80]
    for i in indices:
        s.add(i)
    assert list(s) == indices


def test_get():
    s = CellSet()
    s.add(3)
    s.add(7)
    s.add(15)
    assert s.get(0) == 3
    assert s.get(1) == 7
    assert s.get(2) == 15


def test_and():
    a = CellSet()
    b = CellSet()
    for i in [1, 2, 3, 4]:
        a.add(i)
    for i in [3, 4, 5, 6]:
        b.add(i)
    a.and_(b)
    assert list(a) == [3, 4]


def test_or():
    a = CellSet()
    b = CellSet()
    a.add(1)
    b.add(2)
    a.or_(b)
    assert list(a) == [1, 2]


def test_and_not():
    a = CellSet()
    b = CellSet()
    for i in [1, 2, 3]:
        a.add(i)
    b.add(2)
    a.and_not(b)
    assert list(a) == [1, 3]


def test_clone():
    a = CellSet()
    a.add(10)
    b = a.clone()
    b.add(20)
    assert not a.contains(20)


def test_equality():
    a = CellSet()
    b = CellSet()
    a.add(5)
    b.add(5)
    assert a == b
    b.add(6)
    assert a != b
