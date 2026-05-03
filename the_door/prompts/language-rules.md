# Language Rules — The Door Phase 1-min

## Purpose

L1 output must use purely functional language that non-engineers can understand. This document defines the prohibited terms and provides translation guidance.

## Prohibited Technical Terms (③)

The following terms MUST NOT appear in any `label` or `description` field:

| Term | Why Prohibited |
|------|---------------|
| Service | Technical architecture term |
| Handler | Implementation pattern |
| Controller | MVC pattern term |
| Loader | Technical mechanism |
| IoC | Inversion of Control — architecture pattern |
| Middleware | Technical pipeline concept |
| Decorator | Programming pattern |
| Class | OOP concept |
| Module | Code organization term |
| Import | Code dependency term |
| Endpoint | API technical term |
| Router | Network/API term |
| Provider | DI pattern term |
| Factory | Design pattern |
| Repository | Data access pattern |
| DAO | Data Access Object pattern |
| ORM | Object-Relational Mapping |
| SDK | Software Development Kit |
| API | Application Programming Interface (as implementation reference) |

## Positive Examples

Instead of technical terms, describe what the system DOES for users:

| ❌ Technical | ✅ Functional |
|---|---|
| "Authentication Service" | "User sign-in" |
| "Payment Controller" | "Payment processing" |
| "Email Handler" | "Sending notifications to users" |
| "Data Repository" | "Storing and retrieving user information" |
| "Cache Middleware" | "Speeding up repeated requests" |
| "Event Subscriber" | "Reacting to changes in the system" |
| "API Endpoint" | "Accepting requests from users" |
| "Task Scheduler" | "Running maintenance automatically" |

## Trigger Mechanism Translation Table

When describing HOW a feature is triggered, translate technical mechanisms to human language:

| Technical Trigger | Human-Readable Description |
|---|---|
| HTTP route handler / `@app.route` | "When a user submits a request" |
| Cron job / `@Cron` / Agenda | "System runs automatically on a schedule" |
| EventSubscriber / `@On` / event listener | "Triggered automatically after another function completes" |
| IoC constructor injection | "Configured automatically at system startup" |
| Middleware / `@Use` | "Automatic pre-check before each request" |
| WebSocket handler | "When a user connects for real-time updates" |
| Queue consumer / worker | "Processes tasks in the background" |
| File watcher | "Reacts when files change" |
| Database trigger | "Reacts when data changes" |

## Matching Rules

- Matching is **case-insensitive** (e.g., "handler" matches "Handler")
- Matching uses **word boundaries** (e.g., "class" matches "Class" but not "classification")
- ALL prohibited terms in a single feature are reported (not just the first one)
