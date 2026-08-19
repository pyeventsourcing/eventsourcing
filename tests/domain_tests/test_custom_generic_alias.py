import types
from typing import Any, Self, override
from unittest import TestCase


class CustomGenericAlias(types.GenericAlias):
    def __new__(cls, t_origin: type, t_args: tuple[Any, ...]) -> Self:
        # Forward the parameters to the base C-level constructor
        return super().__new__(cls, t_origin, t_args)

    @override
    def __getattr__(self, name: str) -> Any:
        # Force Python to look up the method on the subclass first

        try:
            value: Any = self.__dict__[name]
        except KeyError:
            try:
                value = getattr(type(self), name)
            except KeyError:
                return super().__getattr__(name)
        if hasattr(value, "__get__"):
            return value.__get__(self, type(self))
        return value

    def custom_method(self) -> str:
        return f"This is an alias for {self.__origin__} wrapped with {self.__args__}"


# 1. Define a class that intercepts subscription using __class_getitem__
# and returns our custom generic alias subclass


class MyContainer[T]:
    @classmethod
    def __class_getitem__(cls, item: type | tuple[type, ...]) -> CustomGenericAlias:
        # If multiple arguments like MyContainer[str, int] are given, item is a tuple
        t_args: tuple[type, ...] = item if isinstance(item, tuple) else (item,)
        return CustomGenericAlias(cls, t_args)


class TestGenericAlias(TestCase):
    def test(self) -> None:
        # 2. Use the syntax
        my_hint = MyContainer[str]

        # 3. Test the runtime characteristics
        print(type(my_hint))  # <class '__main__.CustomGenericAlias'>
        print(my_hint.__origin__)  # type: ignore[attr-defined]
        print(my_hint.__args__)  # type: ignore[attr-defined]
        print(my_hint.custom_method())  # type: ignore[attr-defined]
