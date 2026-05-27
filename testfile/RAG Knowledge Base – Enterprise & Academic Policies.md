# RAG Knowledge Base – Enterprise & Academic Policies

## Document Purpose

This document provides structured, atomic text blocks for use in an internal RAG system (e.g., employee chatbot, student assistant). Each chunk is self-contained, includes metadata, and is optimized for semantic retrieval. The content covers common HR, IT, finance, academic integrity, library, and student life policies.

------

## 1. Enterprise Scenarios (Employee Handbook & Internal Processes)

| ID             | Category                | Title                                | Content Block                                                |
| :------------- | :---------------------- | :----------------------------------- | :----------------------------------------------------------- |
| CORP-HR-001    | HR / Leave              | Paid Annual Leave Policy             | Full‑time employees are entitled to **15 working days** of paid annual leave per calendar year. Eligibility begins after completing 12 months of continuous employment. Leave may be taken in half‑day increments and must be requested via the HR system at least 3 business days in advance. Unused leave may carry over **up to 10 days** to the next year; any excess is forfeited. Upon termination, unused leave is compensated at **three times the daily wage**. |
| CORP-HR-002    | HR / Benefits           | Parental Leave & Nursing Rooms       | Female employees receive **98 calendar days** of fully paid maternity leave. Male employees receive **7 calendar days** of paternity leave. The company provides two private nursing rooms (Building A, 3rd floor and Building B, 1st floor) – reserve via the corporate WeChat app. Parental leave (5 days/year) is available for employees with a child under age 3. |
| CORP-IT-001    | IT / Security           | Remote Access to Corporate Network   | Remote work requires the company‑issued VPN client (Cisco AnyConnect). For personal devices, install endpoint detection software (CrowdStrike) beforehand. Do not download sensitive company files to personal computers; use the VDI virtual desktop for any editing tasks. |
| CORP-FIN-001   | Finance / Reimbursement | Travel Expense Reimbursement Process | Submit expense claims within **14 days** after the trip ends (OA System → Finance Module → Travel Reimbursement). Required attachments: flight/train tickets, hotel invoice (with corporate tax ID), itinerary. Accommodation caps: ¥600/night in tier‑1 cities, ¥400/night in other cities. Any excess is borne by the employee. Approved reimbursements are processed within 10 business days. |
| CORP-LEGAL-001 | Legal / Compliance      | Data Classification & Handling       | Data is classified as Public, Internal, Confidential, or Restricted. Customer lists and financial forecasts are “Confidential”; source code and unpublished earnings are “Restricted”. When handling Confidential or Restricted data, do not use personal USB drives or unencrypted email. Violations may lead to disciplinary action including legal liability. |
| CORP-HR-003    | HR / Performance        | Annual Performance Review Cycle      | Performance reviews occur twice a year (mid‑year and year‑end). Employees complete a self‑assessment, followed by manager evaluation and calibration meeting. Ratings: Exceeds Expectations (EE), Meets Expectations (ME), or Needs Improvement (NI). Employees with consecutive NI ratings may be placed on a **60‑day performance improvement plan (PIP)**. |

------

## 2. Academic Scenarios (Student Handbook & Regulations)

| ID            | Category                 | Title                                | Content Block                                                |
| :------------ | :----------------------- | :----------------------------------- | :----------------------------------------------------------- |
| SCH-REG-001   | Registrar / Enrollment   | Undergraduate Course Registration    | Pre‑registration opens in week 15 of each semester (via the Academic Information System). The system uses a random lottery mechanism – no need to rush. Unsuccessful selections can be applied for during the add/drop period (first week of classes). Minimum load: 12 credits per semester; maximum: 28 credits (including retaken courses). |
| SCH-ACA-001   | Academic / Integrity     | Definition of Academic Misconduct    | The following constitute academic misconduct: (1) plagiarism – six consecutive words identical to a published source without quotation marks; (2) contract cheating or impersonation; (3) data fabrication; (4) submitting the same work for multiple courses without permission. Upon finding, the course grade is **F** and the case is reported to the Academic Integrity Committee. A second violation results in **suspension for one semester**. |
| SCH-LIB-001   | Library / Facilities     | Borrowing Rules & Overdue Fines      | General books: loan period **30 days**, renewable once (additional 15 days). Short‑loan course reserves: **7 days**, non‑renewable. Overdue fines: general books – ¥0.50/day per book; course reserves – ¥2.00/day per book. Borrowing privileges are suspended if you have overdue items or accumulated fines ≥ ¥10. |
| SCH-FIN-001   | Finance / Scholarships   | Chancellor’s Scholarship Eligibility | Requirements: GPA ≥ 3.7 (on 4.0 scale), no disciplinary record, and at least 20 hours of verified volunteer service. Application materials: official transcript, personal statement, two letters of recommendation from faculty. Deadline: 15 October (fall semester). Recipients announced in December. |
| SCH-EVENT-001 | Campus Life / Activities | Academic Lecture Attendance Policy   | Students must attend at least **4 academic lectures** per semester (e.g., distinguished speaker series, faculty research talks). Attendance is recorded by scanning student ID at entry and exit – each session must be at least 30 minutes to count. Failure to meet the requirement disqualifies the student from “Outstanding Student” awards. |
| SCH-REG-002   | Registrar / Exams        | Medical Absence from Final Exams     | If a student cannot attend a final exam due to illness, they must submit within **3 working days** after the exam: (1) a certificate from a grade‑A hospital; (2) a completed Deferred Exam Application form signed by their academic advisor. The deferred exam will be scheduled during week 2 of the following semester; the grade is recorded as earned (no additional curve). Forging a medical certificate is treated as academic misconduct under SCH-ACA-001. |

------

## 3. Example Retrieval & RAG-Generated Answers

### Example 1 – Enterprise Query

**User query:**

> “I stayed in a hotel in Shanghai for ¥650 per night. Will the company reimburse the full amount?”

**Retrieved chunk:** `CORP-FIN-001` (accommodation cap for tier‑1 cities = ¥600).
**RAG answer (grounded):**

> According to the travel expense reimbursement policy (CORP-FIN-001), the maximum reimbursement for a tier‑1 city like Shanghai is ¥600 per night. Your expense of ¥650 exceeds the cap by ¥50, which you must cover personally. When you submit your claim in the OA system, enter ¥600 for the hotel cost and attach the original invoice.

------

### Example 2 – Academic Query

**User query:**

> “I missed my final exam because I was sick. Will I be penalized for academic misconduct?”

**Retrieved chunks:** `SCH-REG-002` (medical absence process) + `SCH-ACA-001` (definition of misconduct).
**RAG answer (grounded):**

> No, a genuine medical absence is not considered academic misconduct. However, you must follow the deferred exam procedure (SCH-REG-002): submit a hospital certificate and the deferred exam application within 3 working days of the missed exam. If you submit a forged medical certificate, that would be treated as misconduct under SCH-ACA-001 and could result in an F grade and further sanctions.

