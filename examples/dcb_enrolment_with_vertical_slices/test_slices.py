from __future__ import annotations

from unittest import TestCase

from eventsourcing.dcb.gwt import given
from eventsourcing.domain import TaggedEvent
from examples.dcb_enrolment.interface import (
    AlreadyJoinedError,
    CourseNotFoundError,
    FullyBookedError,
    NotAlreadyJoinedError,
    StudentNotFoundError,
    TooManyCoursesError,
)
from examples.dcb_enrolment_with_vertical_slices.application import (
    Course,
    CourseIDs,
    CourseNames,
    CourseNameUpdated,
    CoursePlacesUpdated,
    CourseRegistered,
    RegisterCourse,
    RegisterStudent,
    Student,
    StudentJoinedCourse,
    StudentJoinsCourse,
    StudentLeavesCourse,
    StudentLeftCourse,
    StudentMaxCoursesUpdated,
    StudentNames,
    StudentNameUpdated,
    StudentRegistered,
    StudentsIDs,
    UpdateCourseName,
    UpdateMaxCourses,
    UpdatePlaces,
    UpdateStudentName,
)


class TestEnrolmentSlices(TestCase):
    # --- RegisterStudent ---

    def test_register_student(self) -> None:
        s = RegisterStudent(name="Alice", max_courses=3)
        student_id = s.student_id

        given().when(s).then(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=3
                ),
                tags=[student_id],
            )
        )

    # --- UpdateStudentName ---

    def test_update_student_name(self) -> None:
        student_id = "student-1"

        given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=3
                ),
                tags=[student_id],
            ),
        ).when(
            UpdateStudentName(student_id, "Bob"),
        ).then(
            TaggedEvent(
                decision=StudentNameUpdated(student_id=student_id, name="Bob"),
                tags=[student_id],
            )
        )

    def test_update_student_name_after_previous_rename(self) -> None:
        student_id = "student-1"

        given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=3
                ),
                tags=[student_id],
            ),
            TaggedEvent(
                decision=StudentNameUpdated(student_id=student_id, name="Bob"),
                tags=[student_id],
            ),
        ).when(
            UpdateStudentName(student_id, "Charlie"),
        ).then(
            TaggedEvent(
                decision=StudentNameUpdated(student_id=student_id, name="Charlie"),
                tags=[student_id],
            )
        )

    # --- UpdateMaxCourses ---

    def test_update_max_courses(self) -> None:
        student_id = "student-1"

        given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=3
                ),
                tags=[student_id],
            ),
        ).when(
            UpdateMaxCourses(student_id, 5),
        ).then(
            TaggedEvent(
                decision=StudentMaxCoursesUpdated(student_id=student_id, max_courses=5),
                tags=[student_id],
            )
        )

    # --- RegisterCourse ---

    def test_register_course(self) -> None:
        s = RegisterCourse(name="Maths", places=10)
        course_id = s.course_id

        given().when(s).then(
            TaggedEvent(
                decision=CourseRegistered(course_id=course_id, name="Maths", places=10),
                tags=[course_id],
            )
        )

    # --- UpdateCourseName ---

    def test_update_course_name(self) -> None:
        course_id = "course-1"

        given(
            TaggedEvent(
                decision=CourseRegistered(course_id=course_id, name="Maths", places=10),
                tags=[course_id],
            ),
        ).when(
            UpdateCourseName(course_id, "Mathematics"),
        ).then(
            TaggedEvent(
                decision=CourseNameUpdated(course_id=course_id, name="Mathematics"),
                tags=[course_id],
            )
        )

    # --- UpdatePlaces ---

    def test_update_places(self) -> None:
        course_id = "course-1"

        given(
            TaggedEvent(
                decision=CourseRegistered(course_id=course_id, name="Maths", places=10),
                tags=[course_id],
            ),
        ).when(
            UpdatePlaces(course_id, 20),
        ).then(
            TaggedEvent(
                decision=CoursePlacesUpdated(course_id=course_id, places=20),
                tags=[course_id],
            )
        )

    # --- StudentJoinsCourse ---

    def test_student_joins_course(self) -> None:
        student_id = "student-1"
        course_id = "course-1"

        given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=3
                ),
                tags=[student_id],
            ),
            TaggedEvent(
                decision=CourseRegistered(course_id=course_id, name="Maths", places=10),
                tags=[course_id],
            ),
        ).when(
            StudentJoinsCourse(student_id, course_id),
        ).then(
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id=course_id
                ),
                tags=[student_id, course_id],
            )
        )

    def test_student_joins_course_fully_booked(self) -> None:
        student_id = "student-1"
        other_student_id = "student-2"
        course_id = "course-1"

        with self.assertRaises(FullyBookedError):
            given(
                TaggedEvent(
                    decision=StudentRegistered(
                        student_id=student_id, name="Alice", max_courses=3
                    ),
                    tags=[student_id],
                ),
                TaggedEvent(
                    decision=CourseRegistered(
                        course_id=course_id, name="Maths", places=1
                    ),
                    tags=[course_id],
                ),
                TaggedEvent(
                    decision=StudentJoinedCourse(
                        student_id=other_student_id, course_id=course_id
                    ),
                    tags=[other_student_id, course_id],
                ),
            ).when(
                StudentJoinsCourse(student_id, course_id),
            )

    def test_student_joins_course_too_many_courses(self) -> None:
        student_id = "student-1"
        course_id = "course-1"
        other_course_id = "course-2"

        with self.assertRaises(TooManyCoursesError):
            given(
                TaggedEvent(
                    decision=StudentRegistered(
                        student_id=student_id, name="Alice", max_courses=1
                    ),
                    tags=[student_id],
                ),
                TaggedEvent(
                    decision=CourseRegistered(
                        course_id=course_id, name="Maths", places=10
                    ),
                    tags=[course_id],
                ),
                TaggedEvent(
                    decision=StudentJoinedCourse(
                        student_id=student_id, course_id=other_course_id
                    ),
                    tags=[student_id, other_course_id],
                ),
            ).when(
                StudentJoinsCourse(student_id, course_id),
            )

    def test_student_joins_course_already_joined(self) -> None:
        student_id = "student-1"
        course_id = "course-1"

        with self.assertRaises(AlreadyJoinedError):
            given(
                TaggedEvent(
                    decision=StudentRegistered(
                        student_id=student_id, name="Alice", max_courses=3
                    ),
                    tags=[student_id],
                ),
                TaggedEvent(
                    decision=CourseRegistered(
                        course_id=course_id, name="Maths", places=10
                    ),
                    tags=[course_id],
                ),
                TaggedEvent(
                    decision=StudentJoinedCourse(
                        student_id=student_id, course_id=course_id
                    ),
                    tags=[student_id, course_id],
                ),
            ).when(
                StudentJoinsCourse(student_id, course_id),
            )

    def test_student_joins_course_student_not_found(self) -> None:
        student_id = "student-1"
        course_id = "course-1"

        with self.assertRaises(StudentNotFoundError):
            given(
                TaggedEvent(
                    decision=CourseRegistered(
                        course_id=course_id, name="Maths", places=10
                    ),
                    tags=[course_id],
                ),
            ).when(
                StudentJoinsCourse(student_id, course_id),
            )

    def test_student_joins_course_course_not_found(self) -> None:
        student_id = "student-1"
        course_id = "course-1"

        with self.assertRaises(CourseNotFoundError):
            given(
                TaggedEvent(
                    decision=StudentRegistered(
                        student_id=student_id, name="Alice", max_courses=3
                    ),
                    tags=[student_id],
                ),
            ).when(
                StudentJoinsCourse(student_id, course_id),
            )

    # --- StudentLeavesCourse ---

    def test_student_leaves_course(self) -> None:
        student_id = "student-1"
        course_id = "course-1"

        given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=3
                ),
                tags=[student_id],
            ),
            TaggedEvent(
                decision=CourseRegistered(course_id=course_id, name="Maths", places=10),
                tags=[course_id],
            ),
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id=course_id
                ),
                tags=[student_id, course_id],
            ),
        ).when(
            StudentLeavesCourse(student_id, course_id),
        ).then(
            TaggedEvent(
                decision=StudentLeftCourse(student_id=student_id, course_id=course_id),
                tags=[student_id, course_id],
            )
        )

    def test_student_leaves_course_not_already_joined(self) -> None:
        student_id = "student-1"
        course_id = "course-1"

        with self.assertRaises(NotAlreadyJoinedError):
            given(
                TaggedEvent(
                    decision=StudentRegistered(
                        student_id=student_id, name="Alice", max_courses=3
                    ),
                    tags=[student_id],
                ),
                TaggedEvent(
                    decision=CourseRegistered(
                        course_id=course_id, name="Maths", places=10
                    ),
                    tags=[course_id],
                ),
            ).when(
                StudentLeavesCourse(student_id, course_id),
            )

    # --- StudentJoinsCourse with updated max_courses and places ---

    def test_student_joins_after_max_courses_updated(self) -> None:
        student_id = "student-1"
        course_id = "course-1"
        other_course_id = "course-2"

        given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=1
                ),
                tags=[student_id],
            ),
            TaggedEvent(
                decision=StudentMaxCoursesUpdated(student_id=student_id, max_courses=2),
                tags=[student_id],
            ),
            TaggedEvent(
                decision=CourseRegistered(course_id=course_id, name="Maths", places=10),
                tags=[course_id],
            ),
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id=other_course_id
                ),
                tags=[student_id, other_course_id],
            ),
        ).when(
            StudentJoinsCourse(student_id, course_id),
        ).then(
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id=course_id
                ),
                tags=[student_id, course_id],
            )
        )

    def test_student_joins_after_places_updated(self) -> None:
        student_id = "student-1"
        other_student_id = "student-2"
        course_id = "course-1"

        given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=3
                ),
                tags=[student_id],
            ),
            TaggedEvent(
                decision=CourseRegistered(course_id=course_id, name="Maths", places=1),
                tags=[course_id],
            ),
            TaggedEvent(
                decision=CoursePlacesUpdated(course_id=course_id, places=2),
                tags=[course_id],
            ),
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=other_student_id, course_id=course_id
                ),
                tags=[other_student_id, course_id],
            ),
        ).when(
            StudentJoinsCourse(student_id, course_id),
        ).then(
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id=course_id
                ),
                tags=[student_id, course_id],
            )
        )

    # --- StudentJoinsCourse after leaving ---

    def test_student_rejoins_after_leaving(self) -> None:
        student_id = "student-1"
        course_id = "course-1"

        given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=3
                ),
                tags=[student_id],
            ),
            TaggedEvent(
                decision=CourseRegistered(course_id=course_id, name="Maths", places=10),
                tags=[course_id],
            ),
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id=course_id
                ),
                tags=[student_id, course_id],
            ),
            TaggedEvent(
                decision=StudentLeftCourse(student_id=student_id, course_id=course_id),
                tags=[student_id, course_id],
            ),
        ).when(
            StudentJoinsCourse(student_id, course_id),
        ).then(
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id=course_id
                ),
                tags=[student_id, course_id],
            )
        )

    # --- StudentsIDs (read-only projection) ---

    def test_students_ids_empty(self) -> None:
        course_id = "course-1"
        s = StudentsIDs(course_id)

        when = given().when(s)
        when.then()
        self.assertEqual(s.student_ids, [])

    def test_students_ids_with_joins(self) -> None:
        course_id = "course-1"
        s = StudentsIDs(course_id)

        when = given(
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id="student-1", course_id=course_id
                ),
                tags=["student-1", course_id],
            ),
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id="student-2", course_id=course_id
                ),
                tags=["student-2", course_id],
            ),
        ).when(s)
        when.then()
        self.assertEqual(s.student_ids, ["student-1", "student-2"])

    def test_students_ids_after_leave(self) -> None:
        course_id = "course-1"
        s = StudentsIDs(course_id)

        when = given(
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id="student-1", course_id=course_id
                ),
                tags=["student-1", course_id],
            ),
            TaggedEvent(
                decision=StudentLeftCourse(student_id="student-1", course_id=course_id),
                tags=["student-1", course_id],
            ),
        ).when(s)
        when.then()
        self.assertEqual(s.student_ids, [])

    # --- StudentNames (read-only projection) ---

    def test_student_names_empty(self) -> None:
        s = StudentNames([])

        when = given().when(s)
        when.then()
        self.assertEqual(s.names, [])

    def test_student_names(self) -> None:
        s = StudentNames(["student-1", "student-2"])

        when = given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id="student-1", name="Alice", max_courses=3
                ),
                tags=["student-1"],
            ),
            TaggedEvent(
                decision=StudentRegistered(
                    student_id="student-2", name="Bob", max_courses=3
                ),
                tags=["student-2"],
            ),
        ).when(s)
        when.then()
        self.assertEqual(s.names, ["Alice", "Bob"])

    def test_student_names_after_update(self) -> None:
        s = StudentNames(["student-1"])

        when = given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id="student-1", name="Alice", max_courses=3
                ),
                tags=["student-1"],
            ),
            TaggedEvent(
                decision=StudentNameUpdated(student_id="student-1", name="Alicia"),
                tags=["student-1"],
            ),
        ).when(s)
        when.then()
        self.assertEqual(s.names, ["Alicia"])

    # --- CourseIDs (read-only projection) ---

    def test_course_ids_empty(self) -> None:
        student_id = "student-1"
        s = CourseIDs(student_id)

        when = given().when(s)
        when.then()
        self.assertEqual(s.course_ids, [])

    def test_course_ids_with_joins(self) -> None:
        student_id = "student-1"
        s = CourseIDs(student_id)

        given(
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id="course-1"
                ),
                tags=[student_id, "course-1"],
            ),
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id="course-2"
                ),
                tags=[student_id, "course-2"],
            ),
        ).when(s).then()
        self.assertEqual(s.course_ids, ["course-1", "course-2"])

    def test_course_ids_after_leave(self) -> None:
        student_id = "student-1"
        s = CourseIDs(student_id)

        when = given(
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id="course-1"
                ),
                tags=[student_id, "course-1"],
            ),
            TaggedEvent(
                decision=StudentLeftCourse(student_id=student_id, course_id="course-1"),
                tags=[student_id, "course-1"],
            ),
        ).when(s)
        when.then()
        self.assertEqual(s.course_ids, [])

    # --- CourseNames (read-only projection) ---

    def test_course_names_empty(self) -> None:
        s = CourseNames([])

        when = given().when(s)
        when.then()
        self.assertEqual(s.names, [])

    def test_course_names(self) -> None:
        s = CourseNames(["course-1", "course-2"])

        when = given(
            TaggedEvent(
                decision=CourseRegistered(
                    course_id="course-1", name="Maths", places=10
                ),
                tags=["course-1"],
            ),
            TaggedEvent(
                decision=CourseRegistered(
                    course_id="course-2", name="Physics", places=20
                ),
                tags=["course-2"],
            ),
        ).when(s)
        when.then()
        self.assertEqual(s.names, ["Maths", "Physics"])

    def test_course_names_after_update(self) -> None:
        s = CourseNames(["course-1"])

        when = given(
            TaggedEvent(
                decision=CourseRegistered(
                    course_id="course-1", name="Maths", places=10
                ),
                tags=["course-1"],
            ),
            TaggedEvent(
                decision=CourseNameUpdated(course_id="course-1", name="Mathematics"),
                tags=["course-1"],
            ),
        ).when(s)
        when.then()
        self.assertEqual(s.names, ["Mathematics"])

    # --- Student (read-only projection) ---

    def test_student_projection(self) -> None:
        student_id = "student-1"
        s = Student(student_id)

        when = given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=3
                ),
                tags=[student_id],
            ),
        ).when(s)
        when.then()
        self.assertTrue(s.student_was_registered)
        self.assertEqual(s.name, "Alice")
        self.assertEqual(s.max_courses, 3)
        self.assertEqual(s.course_ids, [])

    def test_student_projection_with_updates_and_courses(self) -> None:
        student_id = "student-1"
        s = Student(student_id)

        when = given(
            TaggedEvent(
                decision=StudentRegistered(
                    student_id=student_id, name="Alice", max_courses=3
                ),
                tags=[student_id],
            ),
            TaggedEvent(
                decision=StudentNameUpdated(student_id=student_id, name="Alicia"),
                tags=[student_id],
            ),
            TaggedEvent(
                decision=StudentMaxCoursesUpdated(student_id=student_id, max_courses=5),
                tags=[student_id],
            ),
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id="course-1"
                ),
                tags=[student_id, "course-1"],
            ),
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id=student_id, course_id="course-2"
                ),
                tags=[student_id, "course-2"],
            ),
            TaggedEvent(
                decision=StudentLeftCourse(student_id=student_id, course_id="course-1"),
                tags=[student_id, "course-1"],
            ),
        ).when(s)
        when.then()
        self.assertEqual(s.name, "Alicia")
        self.assertEqual(s.max_courses, 5)
        self.assertEqual(s.course_ids, ["course-2"])

    # --- Course (read-only projection) ---

    def test_course_projection(self) -> None:
        course_id = "course-1"
        s = Course(course_id)

        when = given(
            TaggedEvent(
                decision=CourseRegistered(course_id=course_id, name="Maths", places=10),
                tags=[course_id],
            ),
        ).when(s)
        when.then()
        self.assertTrue(s.course_was_registered)
        self.assertEqual(s.name, "Maths")
        self.assertEqual(s.places, 10)
        self.assertEqual(s.student_ids, [])

    def test_course_projection_with_updates_and_students(self) -> None:
        course_id = "course-1"
        s = Course(course_id)

        given(
            TaggedEvent(
                decision=CourseRegistered(course_id=course_id, name="Maths", places=10),
                tags=[course_id],
            ),
            TaggedEvent(
                decision=CourseNameUpdated(course_id=course_id, name="Mathematics"),
                tags=[course_id],
            ),
            TaggedEvent(
                decision=CoursePlacesUpdated(course_id=course_id, places=20),
                tags=[course_id],
            ),
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id="student-1", course_id=course_id
                ),
                tags=["student-1", course_id],
            ),
            TaggedEvent(
                decision=StudentJoinedCourse(
                    student_id="student-2", course_id=course_id
                ),
                tags=["student-2", course_id],
            ),
            TaggedEvent(
                decision=StudentLeftCourse(student_id="student-1", course_id=course_id),
                tags=["student-1", course_id],
            ),
        ).when(s).then()
        self.assertEqual(s.name, "Mathematics")
        self.assertEqual(s.places, 20)
        self.assertEqual(s.student_ids, ["student-2"])
