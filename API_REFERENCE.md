# FlowDraft API Reference

This document provides a comprehensive list of HTTP endpoints, exact JSON schemas for diagram specifications and export requests, and the state machine transition definitions of the video export queue.

---

## 1. Exposed API Endpoints

All endpoints support both the `/api/v1` and `/api` prefixes transparently. Authentication is performed via OAuth2 Password Bearer flow. Requests requiring authorization must supply the `Authorization: Bearer <token>` header.

### Authentication Endpoints

#### Register User
- **Route**: `POST /api/v1/auth/signup` (also `POST /api/auth/signup`)
- **Authentication**: None
- **Request Payload (`UserRegister` schema)**:
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword123"
  }
  ```
- **Response (`UserResponse` schema - `201 Created`)**:
  ```json
  {
    "id": "7a26f634-8c88-4f10-911e-ecb4f877f0a1",
    "email": "user@example.com",
    "is_active": true,
    "created_at": "2026-07-16T14:00:00Z",
    "updated_at": "2026-07-16T14:00:00Z"
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: If the email is already registered (`{"detail": "Email already registered"}`).

#### Get JWT Access Token
- **Route**: `POST /api/v1/auth/token` (also `POST /api/auth/token`)
- **Authentication**: None (Standard OAuth2 Password Request Form)
- **Request Body (Form Data)**:
  - `username`: `user@example.com`
  - `password`: `securepassword123`
- **Response (`Token` schema - `200 OK`)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```
- **Error Responses**:
  - `401 Unauthorized`: For incorrect credentials (`{"detail": "Incorrect email or password"}`).

---

### Diagrams Repository Endpoints

All Diagram operations require a valid bearer token header.

#### Create Diagram
- **Route**: `POST /api/v1/diagrams` (also `POST /api/diagrams`)
- **Authentication**: Bearer Token
- **Request Payload**:
  Accepts either a flat canvas spec JSON (containing elements and canvas details directly) OR a `DiagramCreate` payload structure:
  - **Option A (DiagramCreate)**:
    ```json
    {
      "title": "Production Microservices",
      "description": "Flow of requests from Gateway to database nodes.",
      "spec": { ... },
      "theme": "dark"
    }
    ```
  - **Option B (Direct Spec)**:
    ```json
    {
      "title": "Production Microservices",
      "description": "Flow of requests",
      "canvas": { "width": 1920, "height": 1080 },
      "elements": [ ... ],
      "theme": "dark"
    }
    ```
- **Response (`DiagramResponse` schema - `201 Created`)**:
  ```json
  {
    "id": "c62cf398-e7eb-410a-ba22-832f2f7161b3",
    "title": "Production Microservices",
    "description": "Flow of requests from Gateway to database nodes.",
    "spec": { ... },
    "theme": "dark",
    "user_id": "7a26f634-8c88-4f10-911e-ecb4f877f0a1",
    "created_at": "2026-07-16T14:10:00Z",
    "updated_at": "2026-07-16T14:10:00Z"
  }
  ```

#### List Diagrams
- **Route**: `GET /api/v1/diagrams` (also `GET /api/diagrams`)
- **Authentication**: Bearer Token
- **Response (`200 OK`)**: List of `DiagramResponse` objects.

#### Retrieve Diagram
- **Route**: `GET /api/v1/diagrams/{id}` (also `GET /api/diagrams/{id}`)
- **Authentication**: Bearer Token
- **Response (`200 OK`)**: Single `DiagramResponse` object.
- **Error Responses**:
  - `404 Not Found`: If diagram does not exist.
  - `403 Forbidden`: If diagram belongs to another user.

#### Update Diagram
- **Route**: `PUT /api/v1/diagrams/{id}` (also `PUT /api/diagrams/{id}`)
- **Authentication**: Bearer Token
- **Request Payload (`DiagramUpdate` schema)**:
  ```json
  {
    "title": "Updated Title",
    "description": "Updated Description",
    "spec": { ... },
    "theme": "light"
  }
  ```
- **Response (`200 OK`)**: Single updated `DiagramResponse` object.

#### Delete Diagram
- **Route**: `DELETE /api/v1/diagrams/{id}` (also `DELETE /api/diagrams/{id}`)
- **Authentication**: Bearer Token
- **Response**: `204 No Content`

---

### Export Job Endpoints

All Export operations require a valid bearer token header.

#### Submit Export Job
- **Route**: `POST /api/v1/export` (also `POST /api/export`)
- **Authentication**: Bearer Token
- **Request Payload**:
  Accepts either a flat spec JSON containing `canvas.format` OR an `ExportJobCreate` payload structure:
  - **Option A (ExportJobCreate)**:
    ```json
    {
      "diagram_id": "c62cf398-e7eb-410a-ba22-832f2f7161b3",
      "spec_override": null,
      "format": "mp4"
    }
    ```
  - **Option B (Spec Override)**:
    ```json
    {
      "diagram_id": null,
      "spec_override": {
        "canvas": { "width": 1920, "height": 1080, "fps": 30 },
        "elements": [ ... ]
      },
      "format": "gif"
    }
    ```
- **Response (`200 OK`)**:
  ```json
  {
    "job_id": "18cfc771-46da-49bc-8aa4-b3ef398d5f30",
    "status": "queued"
  }
  ```

#### Get Export Job Status
- **Route**: `GET /api/v1/export/{job_id}` (also `GET /api/export/{job_id}`)
- **Authentication**: Bearer Token
- **Response (`200 OK`)**:
  ```json
  {
    "job_id": "18cfc771-46da-49bc-8aa4-b3ef398d5f30",
    "status": "completed",
    "download_url": "http://localhost:9000/exports/18cfc771-46da-49bc-8aa4-b3ef398d5f30.mp4?AWSAccessKeyId=...",
    "error_message": null
  }
  ```
- **Statuses returned**: `"queued"`, `"processing"`, `"completed"`, `"failed"`.
- **Note**: `download_url` is only returned if the status is `"completed"`. If the job failed, `error_message` will describe the error.

---

## 2. Diagram Specification JSON Schema

The `spec` object is validated using the FlowDraft core python schema. Below is the detailed schema specification.

### Top-Level Spec Schema
```json
{
  "canvas": {
    "width": 1920,      // Default 1920, positive float/integer
    "height": 1440,     // Default 1440, positive float/integer
    "mode": "dynamic",  // "dynamic" (auto-layout), "absolute" (fixed x/y), or "graph"
    "fps": 30.0,        // Frames per second, default 30.0
    "duration": 3.0,    // Animation duration in seconds, default 3.0
    "frames": 90        // Total frame count, default 90. MUST equal (fps * duration)
  },
  "theme": "dark",      // "dark", "light", or "white". Can also be a custom theme dictionary
  "elements": [ ... ],  // List of element objects (At least one required)
  "connections": [ ... ], // Optional list of connection objects
  "annotations": [ ... ]  // Optional list of annotation objects
}
```

### Element Object Schema
Nested child elements inside the `children` or `footer` lists are automatically flattened on ingestion into top-level items, with a `parent` back-reference assigned.
```json
{
  "id": "node_id_1",     // Required, unique non-empty string identifier
  "type": "card",        // Required: "card", "diamond", "panel", "input", "label", "group"
  "title": "Gateway",    // Optional string (default: "")
  "body": "Nginx Proxy", // Optional string (default: "")
  "icon": "globe",       // Optional string icon name (default: null)
  "parent": null,        // Optional parent ID (populated automatically if nested)
  "x": 100.0,            // Optional X-coordinate. If set, Y must also be specified
  "y": 150.0,            // Optional Y-coordinate. If set, X must also be specified
  "style": {             // Optional style dictionary
    "strokeWidth": 2.0,   // Non-negative number
    "cornerRadius": 8.0,  // Non-negative number
    "padding": 15.0       // Non-negative number or dictionary {"left", "right", "top", "bottom"}
  },
  "layout": {            // Optional layout configurations for panels/groups
    "direction": "row",   // "row" or "column" (default: "row")
    "gap": 20.0,          // Distance between nested children, non-negative number
    "padding": 20.0       // Container margin padding, number or dictionary
  },
  "children": [ ... ],   // Optional nested list of element objects (invalid for leaf types)
  "footer": { ... }      // Optional single element object (valid only for panel type)
}
```

### Connection Object Schema
```json
{
  "from": "node_id_1",   // Required, source element ID
  "to": "node_id_2",     // Required, target element ID
  "exitPort": "right",   // Optional: "top", "bottom", "left", "right" (alias: fromPort)
  "entryPort": "left",   // Optional: "top", "bottom", "left", "right" (alias: toPort)
  "label": "HTTP GET",   // Optional connection text label
  "style": "solid",      // Optional connection stroke style: "solid", "dashed", "dotted"
  "color": "#ff0000"     // Optional hex color code override
}
```

### Annotation Object Schema
```json
{
  "text": "100ms SLA",   // Required annotation text
  "attachTo": "node_id", // Attach to specific element. Mutually exclusive with (from + to)
  "from": "node_id_1",   // Used with "to" to attach annotation to connection midpoint
  "to": "node_id_2",     // Used with "from" to attach annotation to connection midpoint
  "position": "top"      // Annotation placement: "top", "bottom", "left", "right", "midpoint",
                         // "top-left", "top-right", "bottom-left", "bottom-right", "top-label", "center"
}
```

---

## 3. Export Job Queue State Transitions

FlowDraft enqueues and coordinates jobs via a state-machine using PostgreSQL for state storage and Redis for transactional queueing.

```
                  ┌───────────────┐
                  │  (User POST)  │
                  └───────┬───────┘
                          │
                          ▼
                  ┌───────────────┐
                  │    queued     │ (Database record created with status="queued")
                  └───────┬───────┘ (LPUSH job_id & spec payload to Redis "export-jobs")
                          │
                   BRPOP from Redis
                          │
                          ▼
                  ┌───────────────┐
                  │  processing   │ (Worker changes state in DB to "processing")
                  └───────┬───────┘ (Launches Playwright, captures frames, compiles via FFmpeg)
                          │
              ┌───────────┴───────────┐
              │                       │
      Render Success           Render Failure / Error
              │                       │
              ▼                       ▼
      ┌───────────────┐       ┌───────────────┐
      │   completed   │       │    failed     │
      └───────────────┘       └───────────────┘
      (Uploads to MinIO,      (Records error message in DB,
       saves signed URL)       closes browser process cleanly)
```

1. **State: `queued`**
   - **Trigger**: Client posts to `/api/export`.
   - **Database Action**: Creates an `ExportJob` row with `status = "queued"`.
   - **Broker Action**: Gateway converts spec to JSON and pushes `{job_id, spec, format}` to Redis list `export-jobs`.

2. **State: `processing`**
   - **Trigger**: The worker pulls a job ID using a blocking `BRPOP` on `export-jobs` list.
   - **Database Action**: Changes the `ExportJob` status column to `"processing"`.
   - **Worker Operations**: Playwright automation spins up browser, captures screenshots, and FFmpeg processes the PNG stream into media bytes.

3. **State: `completed`**
   - **Trigger**: FFmpeg finishes encoding and the file is uploaded to MinIO.
   - **Database Action**: Saves status as `"completed"`, stores the presigned URL in the `download_url` column, and writes the `updated_at` timestamp.

4. **State: `failed`**
   - **Trigger**: Any exception raised during spec loading, browser rendering, screenshot capture, FFmpeg encoding, or MinIO uploading.
   - **Database Action**: Saves status as `"failed"`, writes the stringified exception to the `error_message` column, and writes the `updated_at` timestamp.
