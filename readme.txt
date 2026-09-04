# Voice AI Hospital Receptionist — Project Report

## 1. Project Overview

The **Voice AI Hospital Receptionist** is an intelligent conversational voice system designed to automate hospital appointment management tasks through natural voice interactions.

Developed for **Apollo OMR Hospital, Chennai**, the system allows patients to speak naturally with an AI receptionist to:

* **Discover Doctors:** Find doctors by medical department or doctor name
* **Check Availability:** Query real-time available 30-minute appointment slots
* **Book Appointments:** Reserve confirmed slots with patient details
* **Reschedule Appointments:** Change appointment date/time while preserving physician assignment
* **Cancel Appointments:** Lookup and cancel active bookings
* **Handle Unavailable Slots:** Intelligently suggest nearby alternative slots
* **Prevent Scheduling Conflicts:** Avoid double-booking via database constraints and backend validation
* **Manage Multiple Appointments:** Disambiguate when a patient holds more than one booking
* **Adapt Mid-Conversation:** Gracefully handle user mind changes and updated preferences
* **Natural Language Understanding:** Parse natural date and time expressions (e.g., "tomorrow at eleven", "make that twelve")
* **Error Recovery:** Offer natural recovery prompts when queries fail or input is invalid

The project is built as a complete **Voice AI (Retell) → REST API (FastAPI) → PostgreSQL Database (Supabase)** production pipeline.

---

## 2. Project Objectives

The primary objective was to build a production-ready conversational AI receptionist capable of executing real appointment operations while maintaining state throughout multi-turn dialogues.

Key requirements:
1. Natural voice interaction with low latency
2. Real doctor and department information
3. Real database-backed transactional operations
4. Real-time availability computation before booking
5. Strict conflict prevention (zero double-bookings)
6. Robust rescheduling and cancellation workflows
7. Handling dynamic mid-call preference adjustments
8. Graceful conversational error recovery
9. Independent backend automated evaluation suite
10. Live cloud deployment and integration

---

## 3. Technology Selection

### Voice AI Platform — Retell AI
**Retell AI** was selected as the voice conversational layer.

**Key Capabilities Utilized:**
* Natural real-time voice streaming
* Conversation-flow-based agent orchestration
* Custom tool / function calling (REST API integration)
* Dynamic variable extraction and state tracking
* Conditional branching and transitions
* Speech interruption handling
* Reusable conversational sub-components

**Agent Configuration:**
* **Language:** English (India)
* **Timezone:** Asia/Calcutta (`IST`)
* **Voice Model:** Retell Cimo
* **Conversation Engine:** Retell Conversation Flow

---

## 4. Overall Architecture

```text
                  Patient (Voice Call)
                           │
                           ▼
                 Retell Voice AI Agent
                           │
                 REST Function Calling
                           │
                           ▼
                  FastAPI Backend (Render)
                           │
                 Supabase Client (PostgreSQL)
                           │
                           ▼
               Appointments / Doctors Database
```

### Component Responsibilities

* **Retell AI:**
  * Voice synthesis (TTS), speech-to-text (STT), and conversational intelligence
  * Turn-taking, interruptions, and dialog flow management
  * Dynamic parameter extraction and confirmation dialogues
  * Executing function calls to the backend API

* **FastAPI Backend:**
  * Business logic, scheduling rules, and input validation
  * Working hours and slot generation algorithms
  * Transaction processing (booking, rescheduling, cancellation)
  * Error formatting into agent-friendly responses

* **Supabase PostgreSQL:**
  * Persistent storage for doctors and appointments
  * Relational integrity (foreign keys)
  * Unique conditional index constraints for active appointment conflict prevention

---

## 5. Hospital Domain Data

**Apollo OMR Hospital, Chennai** was selected as the operational hospital context. Real doctor profiles and departmental schedules were structured into the database across seven key specialties:

| ID | Doctor | Department | Working Days | Hours |
| -: | :----- | :--------- | :----------- | :---- |
| 1 | Dr. Vijayaraghavan S | General Medicine | Mon-Sat | 09:00 - 13:00 |
| 2 | Dr. Leela S | General Medicine | Mon-Sat | 17:00 - 18:00 |
| 3 | Dr. R M Kumudha | Internal Medicine | Mon-Sat | 10:00 - 16:00 |
| 4 | Dr. M Nandakishore | General Surgery | Mon-Sat | 09:00 - 17:00 |
| 5 | Dr. Premkumar Balachandran | General Surgery | Mon-Sat | 09:00 - 15:00 |
| 6 | Dr. M.G. Shekar | Urology | Mon-Sat | 11:00 - 14:00 |
| 7 | Dr. Senthur Nambi | Infectious Diseases | Mon | 12:00 - 14:00 |
| 8 | Dr. Arul E D | Cardiology | Mon-Sat | 10:00 - 16:00 |
| 9 | Dr. M Kathiresan | Cardiology | Mon-Sat | 10:00 - 14:00 |
| 10 | Dr. Madhu Prabhu Doss | Cardiology | Mon-Sat | 11:00 - 13:00 |
| 11 | Dr. S Balakumar | Vascular Surgery | Mon-Sat | 09:00 - 19:00 |

*All consultations operate in standard **30-minute appointment slots**.*

---

## 6. Database Design

Supabase PostgreSQL manages all persistent state across two core tables.

### `doctors` Table
```text
doctors
├── id (BIGINT, Primary Key, Auto-increment)
├── name (TEXT)
├── department (TEXT)
├── slot_days (TEXT, e.g. "Mon-Sat", "Mon")
├── slot_start (TIME, e.g. "09:00:00")
├── slot_end (TIME, e.g. "17:00:00")
└── created_at (TIMESTAMPTZ)
```

### `appointments` Table
```text
appointments
├── id (BIGINT, Primary Key, Auto-increment)
├── patient_name (TEXT)
├── patient_phone (TEXT)
├── doctor_id (BIGINT, Foreign Key -> doctors.id)
├── date (DATE)
├── time (TIME)
├── status (TEXT: 'booked' | 'rescheduled' | 'cancelled')
├── created_at (TIMESTAMPTZ)
└── updated_at (TIMESTAMPTZ)
```

---

## 7. Appointment Conflict Prevention

To guarantee zero double-bookings under concurrent requests, a database-level partial unique index is enforced:

```sql
CREATE UNIQUE INDEX unique_active_appointment
ON public.appointments (doctor_id, date, "time")
WHERE status = 'booked';
```

**How it works:**
* Allows multiple historical rows for the same slot if marked `rescheduled` or `cancelled`.
* Strictly prevents more than one active `booked` row for the same `(doctor_id, date, time)`.
* Combined with backend pre-validation, this ensures ACID consistency.

---

## 8. FastAPI Backend Endpoints

The backend provides a clean RESTful interface:

| Method | Endpoint | Description |
| :----- | :------- | :---------- |
| `GET` | `/health` | Service health status check |
| `GET` | `/doctors` | List all doctors or filter by department (`?department=...`) |
| `GET` | `/doctors/by-name` | Lookup doctor record by exact/partial name (`?name=...`) |
| `GET` | `/availability` | Get available 30-min slots for a doctor on a specific date |
| `POST` | `/appointments/book` | Book a new appointment slot |
| `GET` | `/appointments/{patient_phone}` | Retrieve all appointments for a patient phone number |
| `POST` | `/appointments/reschedule` | Reschedule an active appointment to a new date/time |
| `POST` | `/appointments/cancel` | Cancel an active appointment by phone number |

---

## 9. Doctor & Department Lookup

The system supports natural lookup by specialty or physician name:

1. **Department Query:** Patient says *"I need an appointment with a cardiologist."*
   * Extracted parameter: `department = "Cardiology"`
   * API call: `GET /doctors?department=Cardiology`
   * Result: Returns list of cardiologists (Dr. Arul E D, Dr. M Kathiresan, Dr. Madhu Prabhu Doss).
2. **Doctor Selection:** Patient selects a doctor by name (e.g., *"Kathiresan"*).
   * Backend resolves doctor details and records `doctor_id = 9` into conversation state.

---

## 10. Availability & Slot Generation

Appointment slots are dynamically computed in real-time:

1. **Working Day Validation:** Validates whether the requested date matches the doctor's `slot_days`.
2. **Slot Generation:** Generates 30-minute intervals between `slot_start` and `slot_end` (e.g. `10:00`, `10:30`, `11:00`, `11:30`, `12:00`, `12:30`, `13:00`, `13:30`).
3. **Booked Slot Subtraction:** Queries active bookings for that doctor and date, removing occupied times.
4. **Validation Rules:**
   * Rejects dates in the past.
   * Rejects times outside working hours.
   * Rejects unaligned slot requests (e.g., 10:15).

---

## 11. Retell Conversation Flow

The Retell agent is structured into modular nodes with clear boundaries:

```text
[Welcome / Intent Detection]
       │
       ├─────────────────────────┬─────────────────────────┐
       ▼                         ▼                         ▼
 [Booking Flow]         [Rescheduling Flow]       [Cancellation Flow]
       │                         │                         │
       ├─────────────────────────┴─────────────────────────┤
       ▼
 [Appointment Lookup & Disambiguation Component]
       │
       ▼
 [Confirmation & Finalization]
       │
       ▼
 [Anything Else? / Wrap Up]
```

---

## 12. Booking Flow

```text
Welcome
   ↓
Identify Department / Doctor
   ↓
GET /doctors?department=...
   ↓
Patient Selects Doctor
   ↓
Resolve & Store doctor_id
   ↓
Prompt for Date
   ↓
GET /availability?doctor_id=...&date=...
   ↓
Present Available Slots
   ↓
Patient Chooses Slot & Confirms
   ↓
Collect Patient Name & Phone
   ↓
POST /appointments/book
   ↓
Confirm Booking Details (Appointment ID, Doctor, Date, Time)
   ↓
Anything Else?
```

---

## 13. Conversation State & Dynamic Variables

The agent maintains conversational context across turns using Retell Dynamic Variables:

| Variable | Type | Description |
| :------- | :--- | :---------- |
| `department` | `string` | Target medical specialty |
| `doctor_name` | `string` | Selected physician name |
| `doctor_id` | `number` | Database ID of the selected doctor |
| `appointment_date` | `string` | Target date (`YYYY-MM-DD`) |
| `appointment_time` | `string` | Target time slot (`HH:MM`) |
| `patient_name` | `string` | Full name of patient |
| `patient_phone` | `string` | Patient contact number |
| `appointment_id` | `number` | ID of created or retrieved appointment |
| `available_slots` | `array` | List of available slots returned by API |

---

## 14. Final Slot Confirmation Mechanism

To prevent hallucinated times, a strict confirmation step is enforced before invoking the booking API:
1. Agent presents verified available slots from the API.
2. Patient states preferred time.
3. Agent explicitly confirms: *"I have you down for Dr. M Kathiresan on 2026-09-05 at 11:00 AM. Shall I confirm this booking?"*
4. Only upon explicit patient confirmation is `POST /appointments/book` triggered.

---

## 15. Rescheduling Flow

```text
Patient Requests Reschedule
   ↓
Lookup Patient Active Appointments (GET /appointments/{phone})
   ↓
Extract Active Appointment & Doctor
   ↓
Prompt for New Date & Time
   ↓
Check Availability (GET /availability)
   ↓
Confirm New Slot Selection
   ↓
POST /appointments/reschedule
   ↓
Update Old Status ('rescheduled') & Create New Booking ('booked')
   ↓
Confirm New Booking Details
```

*Note: The existing physician assignment is preserved during rescheduling.*

---

## 16. Active Appointment Lookup Component

A reusable **Get Active Appointment** sub-flow handles appointment retrieval:
1. Queries appointments using `patient_phone`.
2. Filters for active appointments (`status == 'booked'`).
3. **Single Booking Found:** Automatically proceeds with that appointment.
4. **Multiple Bookings Found:** Prompts the patient: *"I see two upcoming appointments—one with Dr. Arul on Friday and one with Dr. Shekar on Monday. Which one would you like to update?"*
5. Resolves target appointment without exposing database primary keys to the user.

---

## 17. Cancellation Flow

```text
Get Active Appointment (by phone)
   ↓
Confirm Cancellation Intent with Patient
   ↓
POST /appointments/cancel
   ↓
Update Status to 'cancelled' in Database
   ↓
Deliver Friendly Cancellation Confirmation
   ↓
Wrap Up / "Anything else I can help with?"
```

---

## 18. Handling Unavailable Slots

When a patient requests an occupied or non-working time:
1. The system detects the slot is unavailable.
2. Instead of failing the conversation, the agent proactively offers alternatives:
   > *"10:00 AM is currently booked, but Dr. Kathiresan has openings at 10:30 AM, 11:00 AM, and 11:30 AM. Would one of those work for you?"*
3. Patient selects an alternative or suggests another date.

---

## 19. Conflicting Bookings Handling

1. **Pre-check:** Backend checks for existing active appointments prior to insertion.
2. **Race condition protection:** If two calls book simultaneously, the PostgreSQL partial unique index throws a constraint violation.
3. **Response:** Backend returns HTTP 409 (`SLOT_UNAVAILABLE`), prompting the agent to offer alternative slots.

---

## 20. Natural Language Understanding

The conversational agent naturally parses complex colloquial phrasing:
* *"I need to see someone for chest pain."* → Maps to Cardiology.
* *"Can I come in tomorrow morning around 11?"* → Resolves next calendar date + `11:00`.
* *"Actually, make that Saturday instead."* → Overwrites date variable while preserving doctor.
* *"No wait, 12 would be better."* → Adjusts time variable before final confirmation.

---

## 21. Mid-Conversation Changes

If a patient changes their mind during the conversation:
* New values overwrite earlier temporary variables.
* The agent re-validates the new combination (e.g. checks availability for the new date).
* Only the final confirmed state is sent to the backend.

---

## 22. Error Recovery Strategies

| Scenario | Agent Recovery Behavior |
| :------- | :---------------------- |
| Doctor not found | Informs patient and lists available doctors in the department |
| Department not found | Clarifies available departments and requests re-selection |
| Day not working | Informs patient of doctor's working schedule and offers next open day |
| Slot unavailable | Suggests closest alternative open slots on that date |
| No active appointment | Informs patient no booking was found for their phone number |
| Network / API failure | Apologizes politely and suggests trying again or transferring to staff |

---

## 23. Example Live Interaction Trace

### Dialogue Trace:
```text
Patient : "I'd like an appointment with a cardiologist."
Agent   : "We have three cardiologists at Apollo OMR: Dr. Arul E D, Dr. M Kathiresan, and Dr. Madhu Prabhu Doss. Which doctor would you prefer?"
Patient : "Kathiresan."
Agent   : "Dr. M Kathiresan is available Monday through Saturday between 10:00 AM and 2:00 PM. What date would you like to visit?"
Patient : "Tomorrow."
Agent   : "For tomorrow, Dr. Kathiresan has slots at 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 13:00, and 13:30. What time works best?"
Patient : "Eleven."
Agent   : "May I have your full name and phone number to confirm the booking for tomorrow at 11:00 AM?"
Patient : "Anita, 9876543210."
Agent   : "Thank you Anita. Your appointment with Dr. M Kathiresan on 2026-09-05 at 11:00 AM has been confirmed. Your appointment ID is 31. Is there anything else I can help you with?"
```

### Backend JSON Response:
```json
{
  "success": true,
  "appointment_id": 31,
  "patient_name": "Anita",
  "doctor_id": 9,
  "doctor": "Dr. M Kathiresan",
  "department": "Cardiology",
  "date": "2026-09-05",
  "time": "11:00",
  "status": "booked"
}
```

---

## 24. Evaluation Framework

An automated end-to-end Python evaluation harness (`eval/run_eval.py`) validates the deployed backend across **15 standardized test cases**:

### Test Categories
1. **Health Check:** API responsiveness and database connectivity
2. **Doctor Discovery:** Doctor lookup, department filtering, unknown department handling
3. **Availability:** Valid slot generation, working day validation, invalid doctor handling
4. **Booking:** Standard booking, double-booking conflict rejection, invalid slot time rejection
5. **Appointment Management:** Phone lookup, active booking filtering, rescheduling, cancellation, invalid ID handling

---

## 25. Evaluation Benchmark Results

The evaluation test suite was executed against the **live production API**:

```text
============================================================
              EVALUATION BENCHMARK SUMMARY
============================================================
Total Test Cases : 15
Passed           : 15
Failed           : 0
============================================================
```

### Core Metrics

| Evaluation Metric | Score | Status |
| :---------------- | :---- | :----- |
| **Task Success Rate** | **100%** | PASS |
| **Tool / API Correctness** | **100%** | PASS |
| **State Consistency** | **100%** | PASS |
| **Truthfulness & Data Integrity** | **100%** | PASS |
| **Efficiency Score** | **100%** | PASS |
| **Overall Benchmark Score** | **100%** | **PASS** |

### Latency Performance
* **Average Response Latency:** `1.44 s`
* **95th Percentile (P95):** `2.58 s`

---

## 26. Deployment & CI/CD

* **Hosting Platform:** Render Web Service
* **Version Control:** GitHub Repository
* **Database:** Supabase Managed PostgreSQL (AWS Region `ap-south-1`)
* **Live API URL:** `https://voice-ai-hospital-receptionist.onrender.com`

---

## 27. Security & Configuration

* API credentials and database connection strings are managed strictly through environment variables.
* Secrets are excluded from version control via `.gitignore`.
* Required environment variables:
  * `SUPABASE_URL`: Supabase project HTTPS endpoint
  * `SUPABASE_KEY`: Supabase service role / anon key

---

## 28. Project Repository Structure

```text
voice-ai-receptionist/
├── app/
│   ├── __init__.py           # Package initializer
│   ├── main.py               # FastAPI application & route declarations
│   ├── database.py           # Supabase client connection setup
│   ├── models.py             # Pydantic schema validation models
│   └── services.py           # Core business logic & scheduling algorithms
│
├── eval/
│   ├── __init__.py           # Eval package initializer
│   ├── test_cases.json       # 15 automated test scenario definitions
│   ├── run_eval.py           # Evaluation runner script
│   ├── metrics.py            # Benchmark scoring & metrics calculator
│   └── results/
│       └── latest_results.json # Timestamped evaluation reports
│
├── .env                      # Local environment configuration (gitignored)
├── .env.example              # Sample environment template
├── .gitignore                # Git exclusion rules
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
└── readme.txt                # Comprehensive project report
```

---

## 29. End-to-End System Diagram

```text
                 ┌─────────────────────────────┐
                 │       Patient (Voice)       │
                 └──────────────┬──────────────┘
                                │
                                ▼
                 ┌─────────────────────────────┐
                 │       Retell AI Agent       │
                 │  • Voice Synthesis & STT    │
                 │  • Conversation Flow        │
                 │  • Dynamic Variable State   │
                 └──────────────┬──────────────┘
                                │
                         Function Calls
                                │
                                ▼
                 ┌─────────────────────────────┐
                 │       FastAPI Backend       │
                 │  • Input Validation         │
                 │  • Slot Computation         │
                 │  • Booking & Rescheduling   │
                 └──────────────┬──────────────┘
                                │
                                ▼
                 ┌─────────────────────────────┐
                 │    Supabase (PostgreSQL)    │
                 │  • Doctor Schedules         │
                 │  • Appointments Table       │
                 │  • Unique Constraint Index  │
                 └─────────────────────────────┘
```

---

## 30. Final Outcome

The project successfully delivered a fully functional, production-ready Voice AI Hospital Receptionist:

* **Complete Functional Coverage:** Doctor search, real-time availability checking, booking, conflict resolution, rescheduling, cancellation, and multi-appointment disambiguation.
* **Production Quality:** Clean layered architecture separating conversational flow, backend business logic, and transactional database persistence.
* **Zero Hallucination:** Strict slot validation and verification ensures only real available doctor slots are booked.
* **100% Evaluation Score:** Automated end-to-end verification confirms 15/15 test scenarios passing on the live deployment.
