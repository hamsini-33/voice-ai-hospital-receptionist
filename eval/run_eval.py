import json
import os
import time
from datetime import date, datetime, timedelta, timezone

import requests

from metrics import calculate_metrics


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = os.getenv(
    "API_URL",
    "https://voice-ai-hospital-receptionist.onrender.com"
).rstrip("/")

RESULT_FILE = os.path.join(
    os.path.dirname(__file__),
    "results",
    "latest_results.json"
)

# Unique phone numbers for every evaluation run.
# This prevents previous evaluation data from affecting
# the current lifecycle tests.
RUN_ID = str(int(time.time()))[-9:]

TEST_PHONE = "9" + RUN_ID
CONFLICT_PHONE = "8" + RUN_ID

TEST_NAME = "Eval Test Patient"

# Real doctor from the deployed doctors table:
# Dr. M Kathiresan - Cardiology
TEST_DOCTOR_ID = 9

# Performance target.
# This affects ONLY the efficiency metric.
# It does not determine functional PASS/FAIL.
LATENCY_TARGET_SECONDS = 3.0


# ============================================================
# HTTP HELPERS
# ============================================================

def api_get(endpoint, params=None):
    start = time.perf_counter()

    try:
        response = requests.get(
            f"{BASE_URL}{endpoint}",
            params=params,
            timeout=30
        )

        latency = time.perf_counter() - start

        return response, latency

    except requests.RequestException as error:

        latency = time.perf_counter() - start

        print(
            f"GET error: {error}"
        )

        return None, latency


def api_post(
    endpoint,
    params=None,
    json_data=None
):
    start = time.perf_counter()

    try:

        response = requests.post(
            f"{BASE_URL}{endpoint}",
            params=params,
            json=json_data,
            timeout=30
        )

        latency = time.perf_counter() - start

        return response, latency

    except requests.RequestException as error:

        latency = time.perf_counter() - start

        print(
            f"POST error: {error}"
        )

        return None, latency


def response_json(response):

    if response is None:
        return {}

    try:
        return response.json()

    except Exception:
        return {}


# ============================================================
# RESULT HANDLING
# ============================================================

def make_result(
    test_name,
    task_success,
    tool_correctness,
    state_consistency,
    truthfulness,
    latency
):
    """
    Functional PASS/FAIL is independent of latency.

    Latency is reported separately as efficiency.
    """

    efficiency = (
        latency is not None
        and latency <= LATENCY_TARGET_SECONDS
    )

    passed = all([
        task_success,
        tool_correctness,
        state_consistency,
        truthfulness
    ])

    return {
        "test": test_name,

        "task_success": bool(
            task_success
        ),

        "tool_correctness": bool(
            tool_correctness
        ),

        "state_consistency": bool(
            state_consistency
        ),

        "truthfulness": bool(
            truthfulness
        ),

        "efficiency": bool(
            efficiency
        ),

        "latency_ms": (
            round(
                latency * 1000,
                2
            )
            if latency is not None
            else None
        ),

        "passed": bool(
            passed
        )
    }


# ============================================================
# DATE / SLOT HELPERS
# ============================================================

def future_dates(max_days=30):
    """
    Generate future dates.

    We do not assume a particular current date.
    """

    today = date.today()

    for offset in range(
        1,
        max_days + 1
    ):
        yield (
            today
            + timedelta(days=offset)
        )


def get_available_slots(
    doctor_id,
    appointment_date
):
    """
    Call the real deployed availability endpoint.
    """

    response, latency = api_get(
        "/availability",
        params={
            "doctor_id": doctor_id,
            "date": appointment_date
        }
    )

    if response is None:
        return None, None, latency

    if response.status_code != 200:
        return None, response, latency

    body = response_json(
        response
    )

    slots = body.get(
        "available_slots",
        []
    )

    return (
        slots,
        response,
        latency
    )


def find_available_slot(
    doctor_id,
    exclude_date=None,
    exclude_time=None
):
    """
    Search future dates until the real API
    returns an available slot.

    No date/time is hardcoded.
    """

    for candidate in future_dates():

        candidate_date = (
            candidate.isoformat()
        )

        slots, response, latency = (
            get_available_slots(
                doctor_id,
                candidate_date
            )
        )

        if not slots:
            continue

        for slot in slots:

            # Ignore the currently booked slot when
            # searching for a reschedule destination.
            if (
                exclude_date == candidate_date
                and exclude_time is not None
                and slot.startswith(
                    str(exclude_time)[:5]
                )
            ):
                continue

            return {
                "date": candidate_date,
                "time": slot
            }

    raise RuntimeError(
        "Could not find a future available slot "
        f"for doctor {doctor_id}."
    )


# ============================================================
# APPOINTMENT HELPERS
# ============================================================

def get_patient_appointments(
    phone
):
    response, latency = api_get(
        f"/appointments/{phone}"
    )

    if response is None:
        return None, None, latency

    body = response_json(
        response
    )

    return (
        response,
        body,
        latency
    )


def find_active_appointments(
    phone
):
    """
    Return all active/booked appointments.
    """

    response, body, latency = (
        get_patient_appointments(
            phone
        )
    )

    if response is None:
        return [], latency

    if response.status_code != 200:
        return [], latency

    appointments = body.get(
        "appointments",
        []
    )

    active = [
        appointment
        for appointment in appointments
        if appointment.get("status")
        == "booked"
    ]

    return (
        active,
        latency
    )


def find_active_appointment(
    phone
):
    """
    Return the first active appointment.
    """

    active, latency = (
        find_active_appointments(
            phone
        )
    )

    if not active:
        return None, latency

    return (
        active[0],
        latency
    )


# ============================================================
# HEALTH TEST
# ============================================================

def test_health():

    response, latency = api_get(
        "/health"
    )

    if response is None:

        return make_result(
            "health_check",
            False,
            False,
            False,
            False,
            latency
        )

    body = response_json(
        response
    )

    status_ok = (
        response.status_code == 200
    )

    health_ok = (
        body.get("status")
        == "ok"
    )

    return make_result(
        "health_check",
        status_ok and health_ok,
        status_ok,
        health_ok,
        status_ok and health_ok,
        latency
    )


# ============================================================
# DOCTOR TESTS
# ============================================================

def test_doctors():

    response, latency = api_get(
        "/doctors"
    )

    if response is None:

        return make_result(
            "doctor_lookup",
            False,
            False,
            False,
            False,
            latency
        )

    body = response_json(
        response
    )

    status_ok = (
        response.status_code == 200
    )

    has_doctors = (
        isinstance(body, list)
        and len(body) > 0
    )

    valid_structure = (
        has_doctors
        and all(
            isinstance(
                doctor.get("id"),
                int
            )
            and doctor.get("name")
            and doctor.get("department")
            for doctor in body
        )
    )

    return make_result(
        "doctor_lookup",
        status_ok and valid_structure,
        status_ok,
        valid_structure,
        status_ok and valid_structure,
        latency
    )


def test_department_filter():

    response, latency = api_get(
        "/doctors",
        params={
            "department": "Cardiology"
        }
    )

    if response is None:

        return make_result(
            "department_filter",
            False,
            False,
            False,
            False,
            latency
        )

    body = response_json(
        response
    )

    status_ok = (
        response.status_code == 200
    )

    has_doctors = (
        isinstance(body, list)
        and len(body) > 0
    )

    department_correct = (
        has_doctors
        and all(
            "cardiology"
            in doctor.get(
                "department",
                ""
            ).lower()
            for doctor in body
        )
    )

    return make_result(
        "department_filter",
        status_ok and department_correct,
        status_ok,
        department_correct,
        status_ok and department_correct,
        latency
    )


def test_unknown_department():

    response, latency = api_get(
        "/doctors",
        params={
            "department":
                "NonexistentDepartment"
        }
    )

    if response is None:

        return make_result(
            "unknown_department",
            False,
            False,
            False,
            False,
            latency
        )

    body = response_json(
        response
    )

    status_ok = (
        response.status_code == 200
    )

    no_fake_doctors = (
        isinstance(body, list)
        and len(body) == 0
    )

    return make_result(
        "unknown_department",
        status_ok and no_fake_doctors,
        status_ok,
        no_fake_doctors,
        status_ok and no_fake_doctors,
        latency
    )


# ============================================================
# AVAILABILITY TESTS
# ============================================================

def test_availability():

    try:

        slot = find_available_slot(
            TEST_DOCTOR_ID
        )

    except Exception as error:

        print(
            f"Availability discovery error: "
            f"{error}"
        )

        return make_result(
            "availability",
            False,
            False,
            False,
            False,
            None
        )

    response, latency = api_get(
        "/availability",
        params={
            "doctor_id":
                TEST_DOCTOR_ID,
            "date":
                slot["date"]
        }
    )

    if response is None:

        return make_result(
            "availability",
            False,
            False,
            False,
            False,
            latency
        )

    body = response_json(
        response
    )

    status_ok = (
        response.status_code == 200
    )

    slots = body.get(
        "available_slots",
        []
    )

    content_ok = (
        isinstance(slots, list)
        and len(slots) > 0
        and slot["time"] in slots
    )

    return make_result(
        "availability",
        status_ok and content_ok,
        status_ok,
        content_ok,
        status_ok and content_ok,
        latency
    )


def test_invalid_doctor_availability():

    response, latency = api_get(
        "/availability",
        params={
            "doctor_id": 9999,
            "date": next(
                future_dates()
            ).isoformat()
        }
    )

    if response is None:

        return make_result(
            "invalid_doctor_availability",
            False,
            False,
            False,
            False,
            latency
        )

    status_ok = (
        response.status_code == 400
    )

    return make_result(
        "invalid_doctor_availability",
        status_ok,
        status_ok,
        status_ok,
        status_ok,
        latency
    )


# ============================================================
# BOOKING
# ============================================================

def test_booking():
    """
    Book a real dynamically discovered slot.

    Returns booking_info for subsequent
    lifecycle tests.
    """

    try:

        slot = find_available_slot(
            TEST_DOCTOR_ID
        )

    except Exception as error:

        print(
            f"Booking slot discovery error: "
            f"{error}"
        )

        return (
            None,
            make_result(
                "booking",
                False,
                False,
                False,
                False,
                None
            )
        )

    response, latency = api_post(
        "/appointments/book",
        json_data={
            "patient_name":
                TEST_NAME,

            "patient_phone":
                TEST_PHONE,

            "doctor_id":
                TEST_DOCTOR_ID,

            "appointment_date":
                slot["date"],

            "appointment_time":
                slot["time"]
        }
    )

    if response is None:

        return (
            None,
            make_result(
                "booking",
                False,
                False,
                False,
                False,
                latency
            )
        )

    body = response_json(
        response
    )

    status_ok = (
        response.status_code == 200
    )

    success_ok = (
        body.get("success")
        is True
    )

    appointment_id = body.get(
        "appointment_id"
    )

    id_ok = isinstance(
        appointment_id,
        int
    )

    active, verify_latency = (
        find_active_appointments(
            TEST_PHONE
        )
    )

    matching = [
        appointment
        for appointment in active
        if appointment.get("id")
        == appointment_id
    ]

    state_ok = False

    if matching:

        appointment = matching[0]

        state_ok = (
            appointment.get(
                "doctor_id"
            )
            == TEST_DOCTOR_ID

            and appointment.get(
                "date"
            )
            == slot["date"]

            and str(
                appointment.get(
                    "time",
                    ""
                )
            ).startswith(
                slot["time"][:5]
            )

            and appointment.get(
                "status"
            )
            == "booked"
        )

    result = make_result(
        "booking",

        (
            status_ok
            and success_ok
            and id_ok
            and state_ok
        ),

        (
            status_ok
            and success_ok
            and id_ok
        ),

        state_ok,

        (
            status_ok
            and success_ok
            and id_ok
            and state_ok
        ),

        latency
    )

    booking_info = {
        "appointment_id":
            appointment_id,

        "doctor_id":
            TEST_DOCTOR_ID,

        "date":
            slot["date"],

        "time":
            slot["time"]
    }

    return (
        booking_info,
        result
    )


# ============================================================
# BOOKING CONFLICT
# ============================================================

def test_booking_conflict(
    booking_info
):
    """
    Attempt to book the exact same active slot
    using a different patient.

    The database unique_active_appointment index
    should prevent this.
    """

    response, latency = api_post(
        "/appointments/book",
        json_data={
            "patient_name":
                "Eval Conflict Patient",

            "patient_phone":
                CONFLICT_PHONE,

            "doctor_id":
                booking_info["doctor_id"],

            "appointment_date":
                booking_info["date"],

            "appointment_time":
                booking_info["time"]
        }
    )

    if response is None:

        return make_result(
            "booking_conflict",
            False,
            False,
            False,
            False,
            latency
        )

    conflict_detected = (
        response.status_code == 409
    )

    return make_result(
        "booking_conflict",
        conflict_detected,
        conflict_detected,
        conflict_detected,
        conflict_detected,
        latency
    )


# ============================================================
# INVALID BOOKING
# ============================================================

def test_invalid_doctor_booking():

    response, latency = api_post(
        "/appointments/book",
        json_data={
            "patient_name":
                "Eval Invalid Patient",

            "patient_phone":
                "7" + RUN_ID,

            "doctor_id":
                9999,

            "appointment_date":
                next(
                    future_dates()
                ).isoformat(),

            "appointment_time":
                "11:00"
        }
    )

    if response is None:

        return make_result(
            "invalid_doctor_booking",
            False,
            False,
            False,
            False,
            latency
        )

    status_ok = (
        response.status_code == 400
    )

    return make_result(
        "invalid_doctor_booking",
        status_ok,
        status_ok,
        status_ok,
        status_ok,
        latency
    )


def test_invalid_time():
    """
    Doctor 9 works from 10:00 to 14:00.
    18:00 is outside the working hours.
    """

    response, latency = api_post(
        "/appointments/book",
        json_data={
            "patient_name":
                "Eval Invalid Time",

            "patient_phone":
                "6" + RUN_ID,

            "doctor_id":
                TEST_DOCTOR_ID,

            "appointment_date":
                next(
                    future_dates()
                ).isoformat(),

            "appointment_time":
                "18:00"
        }
    )

    if response is None:

        return make_result(
            "invalid_appointment_time",
            False,
            False,
            False,
            False,
            latency
        )

    status_ok = (
        response.status_code == 400
    )

    return make_result(
        "invalid_appointment_time",
        status_ok,
        status_ok,
        status_ok,
        status_ok,
        latency
    )


# ============================================================
# APPOINTMENT LOOKUP
# ============================================================

def test_patient_appointment_lookup(
    booking_info
):

    response, body, latency = (
        get_patient_appointments(
            TEST_PHONE
        )
    )

    if response is None:

        return make_result(
            "appointment_lookup",
            False,
            False,
            False,
            False,
            latency
        )

    status_ok = (
        response.status_code == 200
    )

    appointments = body.get(
        "appointments",
        []
    )

    appointment_found = any(
        appointment.get("id")
        == booking_info[
            "appointment_id"
        ]
        for appointment in appointments
    )

    return make_result(
        "appointment_lookup",
        status_ok and appointment_found,
        status_ok,
        appointment_found,
        status_ok and appointment_found,
        latency
    )


# ============================================================
# RESCHEDULING
# ============================================================

def test_reschedule(
    booking_info
):
    """
    Find a different real available slot,
    reschedule the appointment, then verify:

    old appointment -> rescheduled
    new appointment -> booked
    """

    try:

        new_slot = find_available_slot(
            booking_info["doctor_id"],
            exclude_date=
                booking_info["date"],
            exclude_time=
                booking_info["time"]
        )

    except Exception as error:

        print(
            f"Reschedule slot discovery error: "
            f"{error}"
        )

        return make_result(
            "reschedule",
            False,
            False,
            False,
            False,
            None
        )

    # --------------------------------------------------------
    # IMPORTANT:
    # The finalized backend requires appointment_id.
    # --------------------------------------------------------

    response, latency = api_post(
        "/appointments/reschedule",
        json_data={
            "patient_phone":
                TEST_PHONE,

            "appointment_id":
                booking_info[
                    "appointment_id"
                ],

            "new_date":
                new_slot["date"],

            "new_time":
                new_slot["time"]
        }
    )

    if response is None:

        return make_result(
            "reschedule",
            False,
            False,
            False,
            False,
            latency
        )

    body = response_json(
        response
    )

    status_ok = (
        response.status_code == 200
    )

    success_ok = (
        body.get("success")
        is True
    )

    new_id = body.get(
        "appointment_id"
    )

    previous_id = body.get(
        "previous_appointment_id"
    )

    new_id_ok = isinstance(
        new_id,
        int
    )

    previous_id_ok = isinstance(
        previous_id,
        int
    )

    previous_reference_ok = (
        previous_id
        == booking_info[
            "appointment_id"
        ]
    )

    response, body, verify_latency = (
        get_patient_appointments(
            TEST_PHONE
        )
    )

    state_ok = False

    if response is not None:

        appointments = body.get(
            "appointments",
            []
        )

        old_rows = [
            appointment
            for appointment in appointments
            if appointment.get("id")
            == booking_info[
                "appointment_id"
            ]
        ]

        new_rows = [
            appointment
            for appointment in appointments
            if appointment.get("id")
            == new_id
        ]

        if old_rows and new_rows:

            old_row = old_rows[0]
            new_row = new_rows[0]

            old_state_ok = (
                old_row.get("status")
                == "rescheduled"
            )

            new_state_ok = (
                new_row.get("status")
                == "booked"

                and new_row.get(
                    "doctor_id"
                )
                == booking_info[
                    "doctor_id"
                ]

                and new_row.get(
                    "date"
                )
                == new_slot[
                    "date"
                ]

                and str(
                    new_row.get(
                        "time",
                        ""
                    )
                ).startswith(
                    new_slot[
                        "time"
                    ][:5]
                )
            )

            state_ok = (
                old_state_ok
                and new_state_ok
            )

    functional_success = (
        status_ok
        and success_ok
        and new_id_ok
        and previous_id_ok
        and previous_reference_ok
        and state_ok
    )

    return make_result(
        "reschedule",

        functional_success,

        (
            status_ok
            and success_ok
            and new_id_ok
            and previous_id_ok
            and previous_reference_ok
        ),

        state_ok,

        functional_success,

        latency
    )


def test_reschedule_nonexistent():

    response, latency = api_post(
        "/appointments/reschedule",
        json_data={
            # Deliberately nonexistent patient.
            "patient_phone":
                "9999999998",

            # Required by the finalized API.
            # Deliberately nonexistent appointment.
            "appointment_id":
                999999999,

            "new_date":
                next(
                    future_dates()
                ).isoformat(),

            "new_time":
                "11:00"
        }
    )

    if response is None:

        return make_result(
            "invalid_reschedule",
            False,
            False,
            False,
            False,
            latency
        )

    status_ok = (
        response.status_code == 404
    )

    return make_result(
        "invalid_reschedule",
        status_ok,
        status_ok,
        status_ok,
        status_ok,
        latency
    )


# ============================================================
# CANCELLATION
# ============================================================

def test_cancellation():
    """
    Cancel the currently active appointment and
    verify the database-visible state.
    """

    appointment, lookup_latency = (
        find_active_appointment(
            TEST_PHONE
        )
    )

    if appointment is None:

        return make_result(
            "cancellation",
            False,
            False,
            False,
            False,
            None
        )

    appointment_id = appointment.get(
        "id"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # The finalized backend accepts cancellation
    # data in the JSON request body.
    # --------------------------------------------------------

    response, latency = api_post(
        "/appointments/cancel",
        json_data={
            "patient_phone":
                TEST_PHONE,

            "appointment_id":
                appointment_id
        }
    )

    if response is None:

        return make_result(
            "cancellation",
            False,
            False,
            False,
            False,
            latency
        )

    body = response_json(
        response
    )

    status_ok = (
        response.status_code == 200
    )

    success_ok = (
        body.get("success")
        is True
    )

    response, body, verify_latency = (
        get_patient_appointments(
            TEST_PHONE
        )
    )

    state_ok = False

    if response is not None:

        appointments = body.get(
            "appointments",
            []
        )

        matching = [
            appointment
            for appointment in appointments
            if appointment.get("id")
            == appointment_id
        ]

        state_ok = (
            len(matching) == 1
            and matching[0].get(
                "status"
            )
            == "cancelled"
        )

    functional_success = (
        status_ok
        and success_ok
        and state_ok
    )

    return make_result(
        "cancellation",

        functional_success,

        status_ok
        and success_ok,

        state_ok,

        functional_success,

        latency
    )


def test_cancellation_nonexistent():

    response, latency = api_post(
        "/appointments/cancel",
        json_data={
            "patient_phone":
                "9999999997",

            "appointment_id":
                999999999
        }
    )

    if response is None:

        return make_result(
            "invalid_cancellation",
            False,
            False,
            False,
            False,
            latency
        )

    status_ok = (
        response.status_code == 404
    )

    return make_result(
        "invalid_cancellation",
        status_ok,
        status_ok,
        status_ok,
        status_ok,
        latency
    )


# ============================================================
# PRINTING
# ============================================================

def print_result(result):

    status = (
        "PASS"
        if result["passed"]
        else "FAIL"
    )

    latency = result.get(
        "latency_ms"
    )

    if latency is not None:

        print(
            f"  {result['test']:<30}"
            f"{status:<6}"
            f"{latency:>9.2f} ms"
        )

    else:

        print(
            f"  {result['test']:<30}"
            f"{status}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("VOICE AI HOSPITAL RECEPTIONIST")
    print("BACKEND EVALUATION")
    print("=" * 70)

    print(
        f"API: {BASE_URL}"
    )

    print(
        f"Evaluation phone: {TEST_PHONE}"
    )

    print()

    results = []

    # ========================================================
    # HEALTH
    # ========================================================

    print("HEALTH")
    print("-" * 70)

    result = test_health()

    results.append(result)

    print_result(result)

    # ========================================================
    # DOCTORS
    # ========================================================

    print()
    print("DOCTORS")
    print("-" * 70)

    result = test_doctors()

    results.append(result)

    print_result(result)

    result = test_department_filter()

    results.append(result)

    print_result(result)

    result = test_unknown_department()

    results.append(result)

    print_result(result)

    # ========================================================
    # AVAILABILITY
    # ========================================================

    print()
    print("AVAILABILITY")
    print("-" * 70)

    result = test_availability()

    results.append(result)

    print_result(result)

    result = test_invalid_doctor_availability()

    results.append(result)

    print_result(result)

    # ========================================================
    # BOOKING
    # ========================================================

    print()
    print("BOOKING")
    print("-" * 70)

    booking_info, result = test_booking()

    results.append(result)

    print_result(result)

    if booking_info is None:

        print()
        print(
            "Booking failed. Lifecycle tests that "
            "depend on the booking will be skipped."
        )

        # Still run independent invalid tests.
        result = test_invalid_doctor_booking()

        results.append(result)

        print_result(result)

        result = test_invalid_time()

        results.append(result)

        print_result(result)

    else:

        print(
            f"  Created appointment ID: "
            f"{booking_info['appointment_id']}"
        )

        print(
            f"  Date: "
            f"{booking_info['date']}"
        )

        print(
            f"  Time: "
            f"{booking_info['time']}"
        )

        result = test_booking_conflict(
            booking_info
        )

        results.append(result)

        print_result(result)

        result = test_invalid_doctor_booking()

        results.append(result)

        print_result(result)

        result = test_invalid_time()

        results.append(result)

        print_result(result)

        # ====================================================
        # APPOINTMENT LOOKUP
        # ====================================================

        print()
        print("APPOINTMENT LOOKUP")
        print("-" * 70)

        result = (
            test_patient_appointment_lookup(
                booking_info
            )
        )

        results.append(result)

        print_result(result)

        # ====================================================
        # RESCHEDULE
        # ====================================================

        print()
        print("RESCHEDULING")
        print("-" * 70)

        result = test_reschedule(
            booking_info
        )

        results.append(result)

        print_result(result)

        result = test_reschedule_nonexistent()

        results.append(result)

        print_result(result)

        # ====================================================
        # CANCELLATION
        # ====================================================

        print()
        print("CANCELLATION")
        print("-" * 70)

        result = test_cancellation()

        results.append(result)

        print_result(result)

        result = test_cancellation_nonexistent()

        results.append(result)

        print_result(result)

    # ========================================================
    # METRICS
    # ========================================================

    metrics = calculate_metrics(
        results
    )

    output = {
        "api_url":
            BASE_URL,

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "evaluation_phone":
            TEST_PHONE,

        "metrics":
            metrics,

        "results":
            results
    }

    os.makedirs(
        os.path.dirname(
            RESULT_FILE
        ),
        exist_ok=True
    )

    with open(
        RESULT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=2
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    print(
        f"Total tests       : "
        f"{metrics['total_tests']}"
    )

    print(
        f"Passed tests      : "
        f"{metrics['passed_tests']}"
    )

    print(
        f"Failed tests      : "
        f"{metrics['failed_tests']}"
    )

    print()

    print(
        f"Task Success      : "
        f"{metrics['task_success']}%"
    )

    print(
        f"Tool Correctness  : "
        f"{metrics['tool_correctness']}%"
    )

    print(
        f"State Consistency : "
        f"{metrics['state_consistency']}%"
    )

    print(
        f"Truthfulness      : "
        f"{metrics['truthfulness']}%"
    )

    print(
        f"Efficiency        : "
        f"{metrics['efficiency']}%"
    )

    print()

    print(
        f"Average Latency   : "
        f"{metrics['average_latency_ms']} ms"
    )

    print(
        f"P95 Latency       : "
        f"{metrics['p95_latency_ms']} ms"
    )

    print()

    print(
        f"Overall Score     : "
        f"{metrics['overall_score']}%"
    )

    print()

    print("Results saved to:")

    print(
        RESULT_FILE
    )

    print("=" * 70)


if __name__ == "__main__":
    main()