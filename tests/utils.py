from typing import Any, Generator


def get_all_types():
    return (
        None,
        True,
        False,
        0,
        123,
        0.0,
        123.5,
        "",
        "stringtest",
        [],
        [1, 2, 3],
        (),
        (1, 2, 3),
        {},
        {"key": "value"},
    )


def get_non_type(_type) -> Generator[Any, None, None]:
    types = get_all_types()
    for t in types:
        if type(t) != _type:
            yield t
