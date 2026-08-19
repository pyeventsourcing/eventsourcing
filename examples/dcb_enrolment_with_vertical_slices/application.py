from __future__ import annotations

from typing import override
from uuid import uuid4

from eventsourcing.decorator import event
from eventsourcing.pydantic import (
    CommandSlice,
    DcbApplication,
    Decision,
    QuerySlice,
    Selector,
)
from examples.dcb_enrolment.interface import (
    AlreadyJoinedError,
    CourseNotFoundError,
    EnrolmentInterface,
    FullyBookedError,
    NotAlreadyJoinedError,
    StudentNotFoundError,
    TooManyCoursesError,
)


class StudentDecision(Decision):
    student_id: str


class CourseDecision(Decision):
    course_id: str


class StudentRegistered(StudentDecision):
    name: str
    max_courses: int


class StudentNameUpdated(StudentDecision):
    name: str


class StudentMaxCoursesUpdated(StudentDecision):
    max_courses: int


class CourseRegistered(CourseDecision):
    course_id: str
    name: str
    places: int


class CourseNameUpdated(CourseDecision):
    course_id: str
    name: str


class CoursePlacesUpdated(CourseDecision):
    course_id: str
    places: int


class StudentJoinedCourse(StudentDecision, CourseDecision):
    pass


class StudentLeftCourse(StudentDecision, CourseDecision):
    pass


class RegisterStudent(CommandSlice):
    def __init__(self, name: str, max_courses: int):
        self.student_id = f"student-{uuid4()}"
        self.name = name
        self.max_courses = max_courses

    @override
    def consistency_boundary(self) -> Selector:
        return Selector(types=[StudentRegistered], tags=[self.student_id])

    @override
    def execute(self) -> None:
        self.trigger_event(
            StudentRegistered,
            [self.student_id],
            student_id=self.student_id,
            name=self.name,
            max_courses=self.max_courses,
        )


class UpdateStudentName(CommandSlice):
    def __init__(self, student_id: str, name: str) -> None:
        self.student_id = student_id
        self.name = name
        self.student_was_registered: bool = False

    @override
    def consistency_boundary(self) -> Selector:
        return Selector(
            types=[StudentRegistered, StudentNameUpdated], tags=[self.student_id]
        )

    @event(StudentRegistered)
    def _(self) -> None:
        self.student_was_registered = True

    @override
    def execute(self) -> None:
        assert self.student_was_registered
        self.trigger_event(
            StudentNameUpdated,
            [self.student_id],
            student_id=self.student_id,
            name=self.name,
        )


class UpdateMaxCourses(CommandSlice):
    def __init__(self, student_id: str, max_courses: int) -> None:
        self.student_id = student_id
        self.max_courses = max_courses
        self.student_was_registered: bool = False

    @override
    def consistency_boundary(self) -> Selector:
        return Selector(
            types=[StudentRegistered, StudentMaxCoursesUpdated],
            tags=[self.student_id],
        )

    @event(StudentRegistered)
    def _(self) -> None:
        self.student_was_registered = True

    @override
    def execute(self) -> None:
        assert self.student_was_registered
        self.trigger_event(
            StudentMaxCoursesUpdated,
            [self.student_id],
            student_id=self.student_id,
            max_courses=self.max_courses,
        )


class RegisterCourse(CommandSlice):
    def __init__(self, name: str, places: int):
        self.name = name
        self.places = places
        self.course_id = f"course-{uuid4()}"

    @override
    def consistency_boundary(self) -> Selector:
        return Selector(types=[CourseRegistered], tags=[self.course_id])

    @override
    def execute(self) -> None:
        self.trigger_event(
            CourseRegistered,
            [self.course_id],
            course_id=self.course_id,
            name=self.name,
            places=self.places,
        )


class UpdateCourseName(CommandSlice):
    def __init__(self, course_id: str, name: str) -> None:
        self.course_id = course_id
        self.name = name
        self.course_was_registered: bool = False

    @override
    def consistency_boundary(self) -> Selector:
        return Selector(
            types=[CourseRegistered, CourseNameUpdated], tags=[self.course_id]
        )

    @event(CourseRegistered)
    def _(self) -> None:
        self.course_was_registered = True

    @override
    def execute(self) -> None:
        assert self.course_was_registered
        self.trigger_event(
            CourseNameUpdated,
            [self.course_id],
            course_id=self.course_id,
            name=self.name,
        )


class UpdatePlaces(CommandSlice):
    def __init__(self, course_id: str, places: int) -> None:
        self.course_id = course_id
        self.places = places
        self.course_was_registered: bool = False

    @override
    def consistency_boundary(self) -> Selector:
        return Selector(
            types=[CourseRegistered, CoursePlacesUpdated], tags=[self.course_id]
        )

    @event(CourseRegistered)
    def _(self) -> None:
        self.course_was_registered = True

    @override
    def execute(self) -> None:
        assert self.course_was_registered
        self.trigger_event(
            CoursePlacesUpdated,
            [self.course_id],
            course_id=self.course_id,
            places=self.places,
        )


class StudentJoinsCourse(CommandSlice):
    def __init__(self, student_id: str, course_id: str) -> None:
        self.student_id = student_id
        self.course_id = course_id
        self.course_was_registered = False
        self.student_was_registered = False
        self.student_max_courses = 0
        self.course_places = 0
        self.students_on_course: list[str] = []
        self.courses_for_student: list[str] = []

    @override
    def consistency_boundary(self) -> list[Selector]:
        return [
            Selector(
                types=[
                    StudentRegistered,
                    StudentMaxCoursesUpdated,
                    StudentJoinedCourse,
                    StudentLeftCourse,
                ],
                tags=[self.student_id],
            ),
            Selector(
                types=[
                    CourseRegistered,
                    CoursePlacesUpdated,
                    StudentJoinedCourse,
                    StudentLeftCourse,
                ],
                tags=[self.course_id],
            ),
        ]

    @event(StudentRegistered)
    def _(self, max_courses: int) -> None:
        self.student_was_registered = True
        self.student_max_courses = max_courses

    @event(CourseRegistered)
    def _(self, places: int) -> None:
        self.course_was_registered = True
        self.course_places = places

    @event(StudentJoinedCourse)
    def _(self, student_id: str, course_id: str) -> None:
        if student_id == self.student_id:
            self.courses_for_student.append(course_id)
        if course_id == self.course_id:
            self.students_on_course.append(student_id)

    @event(StudentLeftCourse)
    def _(self, student_id: str, course_id: str) -> None:
        if student_id == self.student_id:
            self.courses_for_student.remove(course_id)
        if course_id == self.course_id:
            self.students_on_course.remove(student_id)

    @event(StudentMaxCoursesUpdated)
    def _(self, max_courses: int) -> None:
        self.student_max_courses = max_courses

    @event(CoursePlacesUpdated)
    def _(self, places: int) -> None:
        self.course_places = places

    @override
    def execute(self) -> None:
        if not self.course_was_registered:
            raise CourseNotFoundError(self.course_id)
        if not self.student_was_registered:
            raise StudentNotFoundError(self.student_id)
        if len(self.students_on_course) >= self.course_places:
            raise FullyBookedError(self.course_id)
        if len(self.courses_for_student) >= self.student_max_courses:
            raise TooManyCoursesError(self.student_id)
        if self.student_id in self.students_on_course:
            raise AlreadyJoinedError((self.student_id, self.course_id))
        self.trigger_event(
            StudentJoinedCourse,
            [self.student_id, self.course_id],
            student_id=self.student_id,
            course_id=self.course_id,
        )


class StudentLeavesCourse(CommandSlice):
    def __init__(self, student_id: str, course_id: str) -> None:
        self.student_id = student_id
        self.course_id = course_id
        self.course_was_registered = False
        self.student_was_registered = False
        self.students_on_course: list[str] = []
        self.courses_for_student: list[str] = []

    @override
    def consistency_boundary(self) -> list[Selector]:
        return [
            Selector(
                types=[StudentRegistered, StudentJoinedCourse, StudentLeftCourse],
                tags=[self.student_id],
            ),
            Selector(
                types=[CourseRegistered, StudentJoinedCourse, StudentLeftCourse],
                tags=[self.course_id],
            ),
        ]

    @event(StudentRegistered)
    def _(self) -> None:
        self.student_was_registered = True

    @event(CourseRegistered)
    def _(self) -> None:
        self.course_was_registered = True

    @event(StudentJoinedCourse)
    def _(self, student_id: str, course_id: str) -> None:
        if student_id == self.student_id:
            self.courses_for_student.append(course_id)
        if course_id == self.course_id:
            self.students_on_course.append(student_id)

    @event(StudentLeftCourse)
    def _(self, student_id: str, course_id: str) -> None:
        if student_id == self.student_id:
            self.courses_for_student.remove(course_id)
        if course_id == self.course_id:
            self.students_on_course.remove(student_id)

    @override
    def execute(self) -> None:
        if not self.course_was_registered:
            raise CourseNotFoundError
        if not self.student_was_registered:
            raise StudentNotFoundError
        if self.student_id not in self.students_on_course:
            raise NotAlreadyJoinedError
        self.trigger_event(
            StudentLeftCourse,
            [self.student_id, self.course_id],
            student_id=self.student_id,
            course_id=self.course_id,
        )


class StudentsIDs(QuerySlice):
    def __init__(self, course_id: str) -> None:
        self.course_id = course_id
        self.student_ids: list[str] = []

    @override
    def consistency_boundary(self) -> Selector:
        return Selector(
            types=[StudentJoinedCourse, StudentLeftCourse], tags=[self.course_id]
        )

    @event(StudentJoinedCourse)
    def _(self, student_id: str) -> None:
        self.student_ids.append(student_id)

    @event(StudentLeftCourse)
    def _(self, student_id: str) -> None:
        self.student_ids.remove(student_id)


class StudentNames(QuerySlice):
    def __init__(self, student_ids: list[str]) -> None:
        self.student_id_names: dict[str, str | None] = dict.fromkeys(student_ids, None)

    @override
    def consistency_boundary(self) -> list[Selector]:
        return [
            Selector(types=[StudentRegistered, StudentNameUpdated], tags=[student_id])
            for student_id in self.student_id_names
        ]

    @event(StudentRegistered)
    def _(self, student_id: str, name: str) -> None:
        self.student_id_names[student_id] = name

    @event(StudentNameUpdated)
    def _(self, student_id: str, name: str) -> None:
        self.student_id_names[student_id] = name

    @property
    def names(self) -> list[str]:
        return [n for n in self.student_id_names.values() if n]


class CourseIDs(QuerySlice):
    def __init__(self, student_id: str) -> None:
        self.student_id = student_id
        self.course_ids: list[str] = []

    @override
    def consistency_boundary(self) -> Selector:
        return Selector(
            types=[StudentJoinedCourse, StudentLeftCourse], tags=[self.student_id]
        )

    @event(StudentJoinedCourse)
    def _(self, course_id: str) -> None:
        self.course_ids.append(course_id)

    @event(StudentLeftCourse)
    def _(self, course_id: str) -> None:
        self.course_ids.remove(course_id)


class CourseNames(QuerySlice):
    def __init__(self, course_ids: list[str]) -> None:
        self.course_id_names: dict[str, str | None] = dict.fromkeys(course_ids, None)

    @override
    def consistency_boundary(self) -> list[Selector]:
        return [
            Selector(types=[CourseRegistered, CourseNameUpdated], tags=[student_id])
            for student_id in self.course_id_names
        ]

    @event(CourseRegistered)
    def _(self, course_id: str, name: str) -> None:
        self.course_id_names[course_id] = name

    @event(CourseNameUpdated)
    def _(self, course_id: str, name: str) -> None:
        self.course_id_names[course_id] = name

    @property
    def names(self) -> list[str]:
        return [n for n in self.course_id_names.values() if n]


class Student(QuerySlice):
    def __init__(self, student_id: str) -> None:
        self.student_id = student_id
        self.student_was_registered: bool = False
        self.name: str = ""
        self.max_courses: int = 0
        self.course_ids: list[str] = []

    @override
    def consistency_boundary(self) -> Selector:
        return Selector(tags=[self.student_id])

    @event(StudentRegistered)
    def _(self, name: str, max_courses: int) -> None:
        self.student_was_registered = True
        self.name = name
        self.max_courses = max_courses

    @event(StudentNameUpdated)
    def _(self, name: str) -> None:
        self.name = name

    @event(StudentMaxCoursesUpdated)
    def _(self, max_courses: int) -> None:
        self.max_courses = max_courses

    @event(StudentJoinedCourse)
    def _(self, course_id: str) -> None:
        self.course_ids.append(course_id)

    @event(StudentLeftCourse)
    def _(self, course_id: str) -> None:
        self.course_ids.remove(course_id)


class Course(QuerySlice):
    def __init__(self, course_id: str) -> None:
        self.course_id = course_id
        self.course_was_registered: bool = False
        self.name: str = ""
        self.places = 0
        self.student_ids: list[str] = []

    @override
    def consistency_boundary(self) -> Selector:
        return Selector(tags=[self.course_id])

    @event(CourseRegistered)
    def _(self, name: str, places: int) -> None:
        self.course_was_registered = True
        self.name = name
        self.places = places

    @event(CourseNameUpdated)
    def _(self, name: str) -> None:
        self.name = name

    @event(CoursePlacesUpdated)
    def _(self, places: int) -> None:
        self.places = places

    @event(StudentJoinedCourse)
    def _(self, student_id: str) -> None:
        self.student_ids.append(student_id)

    @event(StudentLeftCourse)
    def _(self, student_id: str) -> None:
        self.student_ids.remove(student_id)


class EnrolmentWithVerticalSlices(DcbApplication, EnrolmentInterface):
    @override
    def register_student(self, name: str, max_courses: int) -> tuple[int, str]:
        cmd = RegisterStudent(name, max_courses)
        return self.do(cmd), cmd.student_id

    @override
    def register_course(self, name: str, places: int) -> tuple[int, str]:
        cmd = RegisterCourse(name, places)
        return self.do(cmd), cmd.course_id

    @override
    def join_course(self, student_id: str, course_id: str) -> int:
        return self.do(StudentJoinsCourse(student_id, course_id))

    @override
    def list_students_for_course(self, course_id: str) -> list[str]:
        return self.do(StudentNames(self.do(StudentsIDs(course_id)).student_ids)).names

    @override
    def list_courses_for_student(self, student_id: str) -> list[str]:
        return self.do(CourseNames(self.do(CourseIDs(student_id)).course_ids)).names

    def leave_course(self, student_id: str, course_id: str) -> int:
        return self.do(StudentLeavesCourse(student_id, course_id))

    def update_student_name(self, student_id: str, name: str) -> int:
        return self.do(UpdateStudentName(student_id, name))

    def update_max_courses(self, student_id: str, max_courses: int) -> int:
        return self.do(UpdateMaxCourses(student_id, max_courses))

    def update_course_name(self, course_id: str, name: str) -> int:
        return self.do(UpdateCourseName(course_id, name))

    def update_places(self, course_id: str, places: int) -> int:
        return self.do(UpdatePlaces(course_id, places))

    def get_student(self, student_id: str) -> Student:
        return self.do(Student(student_id=student_id))

    def get_course(self, course_id: str) -> Course:
        return self.do(Course(course_id=course_id))
