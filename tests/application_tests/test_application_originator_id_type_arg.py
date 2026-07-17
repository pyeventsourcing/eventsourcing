# from typing import Generic
# from unittest import TestCase
# from uuid import UUID
#
# from typing_extensions import TypeVar
#
# from eventsourcing.application import Application
#
# TAggregateID = TypeVar("TAggregateID", bound=UUID | str, default=UUID)
# T = TypeVar("T")
#
#
# class TestApplicationOriginatorIdTypeArg(TestCase):
#     def test_base_class(self) -> None:
#         self.assertIs(Application.aggregate_id_type, UUID)
#
#     def test_subclass_provides_no_arg(self) -> None:
#         class MyApplication(Application):
#             pass
#
#         self.assertIs(MyApplication.aggregate_id_type, UUID)
#
#     def test_subclass_provides_invalid_arg(self) -> None:
#         with self.assertRaises(TypeError) as cm:
#
#             class _MyApp(Application[int]):  # type: ignore[type-var]
#                 pass
#
#         self.assertIn("Invalid type arg", str(cm.exception))
#
#     def test_subclass_provides_arg_uuid(self) -> None:
#         class MyApplication(Application):
#             pass
#
#         self.assertIs(MyApplication.aggregate_id_type, UUID)
#
#     def test_subclass_provides_arg_str(self) -> None:
#         class MyApplication(Application[str]):
#             pass
#
#         self.assertIs(MyApplication.aggregate_id_type, str)
#
#     def test_subclass_provides_arg_typearg(self) -> None:
#         class SubApplication(Application[TAggregateID]):
#             pass
#
#         class MyApplication(SubApplication[str]):
#             pass
#
#         self.assertIs(MyApplication.aggregate_id_type, str)
#
#     def test_subclass_introduces_param(self) -> None:
#         class SubApplication(Application[TAggregateID], Generic[T, TAggregateID]):
#             pass
#
#         class MyApplication(SubApplication[int, str]):
#             pass
#
#         self.assertIs(MyApplication.aggregate_id_type, str)
#
#     def test_subsubclass_introduces_param(self) -> None:
#         class SubApplication(Application[str], Generic[T, TAggregateID]):
#             pass
#
#         class SubSubpplication(SubApplication[int, TAggregateID]):
#             pass
#
#         class MyApplication(SubSubpplication[str]):
#             pass
#
#         self.assertIs(MyApplication.aggregate_id_type, str)
#
#     def test_subclass_sets_class_var(self) -> None:
#         class MyApplication(Application):
#             aggregate_id_type = None  # type: ignore[assignment]
#
#         with self.assertRaises(TypeError) as cm:
#             MyApplication()
#
#         self.assertIn("Invalid type argument", str(cm.exception))
