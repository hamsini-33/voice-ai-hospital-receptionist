# Voice AI Hospital Receptionist 🎙️🏥

A real-time Voice AI receptionist for **Apollo OMR Hospital, Chennai**, built to handle common hospital appointment workflows through natural voice conversation.

The agent can help patients:

- Find doctors by department
- Check real appointment availability
- Book appointments
- Reschedule existing appointments
- Cancel appointments
- Handle unavailable or conflicting slots
- Recover from invalid or incomplete requests
- Handle changes in date, time, or doctor during a conversation
- Identify the intended appointment when a patient has multiple active appointments

The system uses **Retell** for the voice conversation layer and a **FastAPI + Supabase** backend for real-time doctor and appointment data.

---

## 🏗️ Architecture

```text
                    ┌─────────────────────────┐
                    │     Patient / Caller    │
                    └────────────┬────────────┘
                                 │
                                 │ Natural Voice
                                 ▼
                    ┌─────────────────────────┐
                    │       Retell AI         │
                    │  Voice Agent / Workflow │
                    └────────────┬────────────┘
                                 │
                         HTTPS API Calls
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │       FastAPI           │
                    │     Backend API         │
                    └────────────┬────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
          ┌──────────────────┐      ┌──────────────────┐
          │     Doctors      │      │   Appointments   │
          │     Supabase     │      │     Supabase     │
          └──────────────────┘      └──────────────────┘
