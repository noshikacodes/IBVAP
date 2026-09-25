# 🛡️ IBVAP — Intelligent Border Video Analytics Platform

> An AI-powered video analytics and command-and-control platform for real-time perimeter monitoring, threat detection, incident management, and operational visibility.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Prometheus](https://img.shields.io/badge/Prometheus-Monitoring-E6522C?logo=prometheus&logoColor=white)](https://prometheus.io/)

## 📖 Overview

**IBVAP (Intelligent Border Video Analytics Platform)** is a full-stack computer-vision and command-and-control application designed to transform CCTV/RTSP video streams into structured, actionable security events.

The platform brings together **real-time object detection, multi-object tracking, spatial intrusion rules, ANPR, facial-recognition workflows, PTZ control, incident management, evidence integrity, event streaming, and observability** in a single modular system.

The project follows a simple pipeline:

**Video Ingestion → AI Analysis → Threat Detection → Alerting → Incident Response → Evidence & Observability**

## ✨ Key Features

- 🎥 **Real-Time Video Analytics** — Process CCTV/RTSP streams with YOLO-based detection and frame-level analysis.
- 🎯 **Multi-Object Tracking** — Maintain persistent track IDs and trajectories using ByteTrack / IoU-based tracking.
- 🗺️ **Spatial Threat Detection** — Configure polygon exclusion zones, directional tripwires, and loitering/dwell-time rules.
- 🚘 **ANPR Pipeline** — Detect number plates with YOLO, recognize characters with EasyOCR, normalize Indian/Bharat Series plates, and use multi-frame consensus.
- 👤 **Face Recognition** — Generate face embeddings and compare probes against an enrolled watchlist gallery using cosine similarity.
- 📷 **PTZ Slew-to-Cue** — Translate detected threat locations into pan/tilt/zoom commands with simulated and ONVIF-compatible drivers.
- 🚨 **Live Alerting** — Publish prioritized security events through Redis Pub/Sub and deliver them to clients over WebSockets.
- 🗂️ **Incident Management** — Track incidents through structured operational states from opening to closure.
- 🔐 **Evidence Integrity** — Attach evidence records protected with deterministic SHA-256 integrity digests.
- 📄 **Dossier Generation** — Export machine-readable JSON dossiers and PDF incident reports.
- 📊 **Command & Control Dashboard** — Monitor cameras, alerts, incidents, evidence, maps, and PTZ controls through a React interface.
- 📈 **Observability** — Expose Prometheus metrics and monitor platform health through Grafana dashboards.
- 🐳 **Containerized Deployment** — Run the complete multi-service platform through Docker Compose.

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite |
| Backend | FastAPI, Uvicorn, Pydantic |
| Computer Vision | Python, PyTorch, Ultralytics YOLO, OpenCV |
| OCR | EasyOCR |
| Tracking | ByteTrack, IoU-based tracking |
| ANPR | YOLO + EasyOCR + plate normalization |
| Face Recognition | Face embeddings + cosine similarity |
| Streaming | MediaMTX, RTSP, HLS, WebRTC |
| Messaging | Redis Pub/Sub |
| API Communication | REST + WebSockets |
| Observability | Prometheus + Grafana |
| Deployment | Docker + Docker Compose |
| Testing | Pytest + Vitest |

## 🏗️ Architecture at a Glance

```text
CCTV / RTSP Cameras
        │
        ▼
┌───────────────────────┐
│       MediaMTX        │
│ RTSP / HLS / WebRTC   │
└──────────┬────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│          AI VISION ENGINE           │
│                                     │
│ Video Reader → YOLO → Tracking      │
│               ↓                     │
│         Spatial Rules               │
│          ↓       ↓                  │
│        ANPR   Face Recognition      │
│          \       /                  │
│             PTZ                      │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│           FASTAPI BACKEND           │
│                                     │
│ Alerts • Incidents • Dispatch       │
│ Evidence • REST • WebSockets        │
│ Metrics • Health                    │
└──────────────┬───────────────┬──────┘
               │               │
               ▼               ▼
        ┌─────────────┐  ┌───────────────┐
        │ Redis Pub/Sub│  │ Prometheus +  │
        │ Event Bus    │  │ Grafana       │
        └──────┬──────┘  └───────────────┘
               │
               ▼
      ┌─────────────────────┐
      │ React C2 Dashboard  │
      │ Cameras • Alerts    │
      │ Incidents • Evidence│
      │ PTZ • Maps          │
      └─────────────────────┘
```

## 📂 Project Structure

```text
IBVAP/
├── ai_engine/                  # AI / computer-vision subsystem
│   ├── pipeline/
│   │   ├── anpr/               # Plate detection, OCR, normalization
│   │   ├── face/               # Face detection, embeddings, matching
│   │   ├── ptz/                # PTZ control and coordinate mapping
│   │   ├── detector.py         # YOLO detector wrapper
│   │   ├── tracker.py          # Multi-object tracking
│   │   ├── spatial_rules.py    # Geofences, tripwires, loitering
│   │   ├── stream_reader.py    # RTSP/OpenCV stream reader
│   │   └── inference_runner.py # Pipeline orchestration
│   ├── stream_manager/         # Multi-process stream supervisor
│   ├── telemetry/              # Metrics engine
│   └── worker.py               # AI worker entry point
│
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/v1/             # REST and WebSocket routes
│   │   ├── core/               # Configuration and settings
│   │   ├── schemas/             # Pydantic schemas
│   │   └── services/            # Alert, incident, dispatch, dossier logic
│   └── main.py
│
├── frontend/                   # React + TypeScript C2 dashboard
│   └── src/
│       ├── api/                # API client layer
│       ├── components/         # Reusable dashboard components
│       ├── views/              # Operational pages
│       ├── types/              # TypeScript domain types
│       └── tests/              # Frontend tests
│
├── mock_streams/               # Demo streams and test configurations
├── observability/              # Prometheus and Grafana configuration
├── scripts/                    # Verification and demo utilities
├── data/                       # Project data assets
├── docs/                       # Additional documentation
├── docker-compose.yml          # Full multi-service stack
├── docker-compose.dev.yml      # Development Compose setup
├── .env.example                # Environment variable template
└── README.md                   # Project documentation
```

## 🚀 Getting Started

### Prerequisites

Make sure you have:

- **Python 3.10+**
- **Node.js 18+**
- **npm**
- **Git**
- **Docker Desktop** (recommended for the full platform)

### 1. Clone the repository

```bash
git clone https://github.com/noshikacodes/IBVAP.git
cd IBVAP
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Review the values before starting the application.

### 3. Set up Python

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux / macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r backend/requirements.txt
pip install -r ai_engine/requirements.txt
```

### 4. Set up the frontend

```bash
cd frontend
npm install
cd ..
```

## 🐳 Run with Docker Compose

The complete platform can be started with:

```bash
docker compose up --build
```

### Services

| Service | Port | Purpose |
|---|---:|---|
| Frontend | `80` | React C2 dashboard |
| Backend | `8000` | REST API + WebSockets |
| MediaMTX | `8554 / 8888 / 8889` | RTSP / HLS / WebRTC |
| Redis | `6379` | Event bus |
| Prometheus | `9090` | Metrics |
| Grafana | `3000` | Monitoring dashboards |
| AI Supervisor | — | Multi-stream AI processing |

### Local URLs

- **C2 Dashboard:** `http://localhost`
- **FastAPI Swagger:** `http://localhost:8000/api/v1/docs`
- **Prometheus:** `http://localhost:9090`
- **Grafana:** `http://localhost:3000`

## ▶️ Run in Development Mode

### Backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm run dev
```

### AI stream supervisor

```bash
python -m ai_engine.stream_manager --config mock_streams/streams.json
```

## 🧠 How It Works

IBVAP follows an event-driven surveillance workflow:

1. **Ingest video** from CCTV / RTSP sources through MediaMTX and the stream reader.
2. **Detect objects** with the YOLO inference layer.
3. **Track objects** across frames and maintain persistent identities.
4. **Evaluate spatial rules** such as exclusion zones, tripwires, and loitering.
5. **Enrich events** with ANPR, face recognition, and PTZ workflows.
6. **Generate alerts** and distribute them through Redis Pub/Sub and WebSockets.
7. **Create incidents** for events requiring operational handling.
8. **Attach evidence** and protect its integrity with SHA-256 digests.
9. **Dispatch and document** incidents through structured workflows and dossier exports.
10. **Monitor system health** through Prometheus and Grafana.

## 🔌 API Highlights

Interactive API documentation is available through FastAPI Swagger:

**`http://localhost:8000/api/v1/docs`**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/cameras` | List registered cameras |
| `POST` | `/api/v1/cameras` | Register a camera |
| `POST` | `/api/v1/cameras/{id}/ptz/move` | PTZ movement |
| `GET` | `/api/v1/alerts` | Query security alerts |
| `POST` | `/api/v1/alerts/{id}/acknowledge` | Acknowledge alert |
| `POST` | `/api/v1/alerts/{id}/resolve` | Resolve alert |
| `GET` | `/api/v1/incidents` | List incidents |
| `POST` | `/api/v1/incidents` | Create incident |
| `POST` | `/api/v1/incidents/{id}/evidence` | Attach evidence |
| `POST` | `/api/v1/incidents/{id}/dispatch` | Dispatch incident |
| `GET` | `/api/v1/incidents/{id}/dossier/json` | Export JSON dossier |
| `GET` | `/api/v1/incidents/{id}/dossier/pdf` | Export PDF dossier |
| `GET` | `/metrics` | Prometheus metrics |
| `WS` | `/api/v1/ws/alerts` | Live alert feed |

## 🧪 Testing

### Backend & AI tests

```bash
pytest -v
```

### Frontend tests

```bash
cd frontend
npm test
```

### Production build

```bash
cd frontend
npm run build
```

### End-to-end verification

```bash
python scripts/verify_e2e_full_stack.py
python scripts/verify_api_and_ws.py
python scripts/verify_phase64_telemetry.py
```

## 🎯 Project Goals

- Build an integrated video-intelligence layer over conventional CCTV infrastructure.
- Reduce manual surveillance effort for identifying notable events.
- Connect AI detections to structured alert and incident workflows.
- Provide operational context through a unified C2 interface.
- Maintain a modular architecture that can be extended with additional models, sensors, and rules.

## 🔮 Future Improvements

Potential extensions include:

- Live camera and sensor integrations.
- More advanced threat-classification models.
- Additional detection and tracking models.
- Richer map-based operational views.
- Role-based access control and audit trails.
- Scalable GPU inference for larger camera deployments.
- Improved alert prioritization and event correlation.
- Additional deployment and monitoring integrations.

## 🔐 Security Notes

This repository is intended as a technical research/development platform and should be independently secured, tested, and validated before use in security-critical environments.

Important practices:

- Never commit real credentials or secrets.
- Use secure secret management for production deployments.
- Protect RTSP streams and API endpoints.
- Restrict access to Redis, Prometheus, and Grafana.
- Treat biometric/watchlist information as sensitive data.
- Add authentication and role-based authorization before production use.
- Apply appropriate retention, audit, and access-control policies.

> **Do not reuse development credentials or demo configuration unchanged in production.**

## 🤝 Contributing

Contributions, ideas, and improvements are welcome.

For significant changes, open an issue first to discuss the proposed direction. Pull requests should include relevant tests and documentation updates where applicable.

## 📄 License

No explicit open-source license is currently defined in the repository. If you intend to distribute the project under specific reuse terms, add an appropriate `LICENSE` file.

## 👨‍💻 Author

**noshika**

GitHub: [@noshikacodes](https://github.com/noshikacodes)

---

⭐ If you find IBVAP interesting, consider starring the repository.
