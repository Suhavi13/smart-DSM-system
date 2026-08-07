# DSM Microservices — Stages 4, 5, and 6

This patch continues after `MICROSERVICES_STAGE_1_2.md`.

- **Stage 4:** Route the frontend to five locally running FastAPI services.
- **Stage 5:** Build one Docker image per service.
- **Stage 6:** Start the full system with Docker Compose, PostgreSQL, and Redis.

Run commands from the `DSM_project` root unless a step says otherwise.

---

## Files added or changed

```text
frontend/config.js
frontend/vite.config.js
frontend/Dockerfile
frontend/nginx.conf
frontend/.dockerignore
services/auth-service/Dockerfile
services/sensor-service/Dockerfile
services/weather-service/Dockerfile
services/recommendation-service/Dockerfile
services/decision-service/Dockerfile
compose.yaml
.env.compose.example
.dockerignore
.gitignore
secrets/README.md
```

The original `backend/` monolith is not deleted. You can still use it as a
reference while verifying the new services.

---

# Stage 4 — Connect the Vite frontend to local microservices

## 4.1 Start the five FastAPI services

Open five PowerShell terminals.

### Terminal 1 — Authentication

```powershell
cd services\auth-service
py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### Terminal 2 — Sensors and dashboard

```powershell
cd services\sensor-service
py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

### Terminal 3 — Weather

```powershell
cd services\weather-service
py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8003
```

### Terminal 4 — Recommendations

```powershell
cd services\recommendation-service
py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8004
```

### Terminal 5 — Decisions

```powershell
cd services\decision-service
py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8005
```

Check the health endpoints:

```text
http://localhost:8001/health
http://localhost:8002/health
http://localhost:8003/health
http://localhost:8004/health
http://localhost:8005/health
```

## 4.2 Start Vite

Open a sixth PowerShell terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open:

```text
http://localhost:5500
```

`frontend/config.js` now always calls the frontend's own origin. Vite forwards
API paths as follows:

| Browser path | Local service |
|---|---|
| `/api/v1/auth/*` | `http://localhost:8001` |
| `/api/v1/sensors/*` | `http://localhost:8002` |
| `/api/v1/dashboard/*` | `http://localhost:8002` |
| `/api/v1/external/*` | `http://localhost:8003` |
| `/api/v1/recommendations/*` | `http://localhost:8004` |
| `/api/v1/decisions/*` | `http://localhost:8005` |

Do not use `py -m http.server` for Stage 4. That server cannot perform the Vite
API proxying.

## 4.3 Test a partial failure

1. Leave all services running.
2. Stop only weather-service with `Ctrl+C`.
3. Refresh the dashboard.
4. Sensor pages should continue working, while weather-dependent content should
   show an error.
5. Restart weather-service.

This demonstrates that the features now have separate application lifecycles.

---

# Stage 5 — Build Docker images

## 5.1 Check Docker Desktop

Start Docker Desktop, then run:

```powershell
docker --version
docker compose version
```

## 5.2 Prepare the Compose environment

Create the local Compose environment file:

```powershell
Copy-Item .env.compose.example .env.compose
```

Open `.env.compose` and change at least:

```env
POSTGRES_PASSWORD=replace-with-a-strong-local-password
```

Add your existing OpenRouter key only when you want AI wording. A blank key
keeps the transparent rule-based recommendations.

## 5.3 Add the Firebase Admin credential

Create the secrets folder if necessary:

```powershell
New-Item -ItemType Directory -Force .\secrets
```

Copy your Firebase Admin service-account JSON to this exact path:

```text
DSM_project\secrets\firebase-service-account.json
```

Example:

```powershell
Copy-Item "C:\secure-path\firebase-service-account.json" `
  ".\secrets\firebase-service-account.json"
```

Do not place this JSON in `frontend/config.js`. The browser config is public;
the Admin service account is private server-side material.

## 5.4 Validate the Compose file

```powershell
docker compose config
```

This should print the resolved configuration without an error.

## 5.5 Build all six application images

Stop the five local Uvicorn processes and Vite first so the host ports are free.
Then run:

```powershell
docker compose build
```

Inspect the images:

```powershell
docker images
```

You should see:

```text
dsm/frontend:v1
dsm/auth-service:v1
dsm/sensor-service:v1
dsm/weather-service:v1
dsm/recommendation-service:v1
dsm/decision-service:v1
```

The Docker build context is the project root because each backend image needs
both its own `app/` folder and `services/shared/`. The root `.dockerignore`
prevents the old monolith, virtual environments, node_modules, secrets, and the
large data files from being sent into those builds.

---

# Stage 6 — Run the complete application with Docker Compose

## 6.1 Start all normal containers

```powershell
docker compose up --build -d
```

Compose starts:

```text
frontend
five FastAPI services
PostgreSQL
Redis
```

Inspect them:

```powershell
docker compose ps
```

Wait until the application containers show `healthy`.

## 6.2 Check logs

```powershell
docker compose logs frontend
docker compose logs sensor-service
docker compose logs recommendation-service
```

Follow all logs live when debugging:

```powershell
docker compose logs -f
```

Press `Ctrl+C` to stop following logs; the containers continue running.

## 6.3 Understand the Docker ports

| Component | Browser/host address | Container address |
|---|---|---|
| Frontend | `http://localhost:8080` | `frontend:80` |
| Auth | `http://localhost:8001/health` | `auth-service:8000` |
| Sensors | `http://localhost:8002/health` | `sensor-service:8000` |
| Weather | `http://localhost:8003/health` | `weather-service:8000` |
| Recommendations | `http://localhost:8004/health` | `recommendation-service:8000` |
| Decisions | `http://localhost:8005/health` | `decision-service:8000` |
| PostgreSQL | `localhost:5433` | `postgres:5432` |
| Redis | `localhost:6380` | `redis:6379` |

Inside a container, `localhost` means that same container. Nginx therefore
uses names such as `sensor-service`, and recommendation-service uses
`http://weather-service:8000`.

## 6.4 Import the historical dataset into Docker PostgreSQL

The Docker PostgreSQL database is new and initially contains no sensor data.
The CSV and Excel files are not copied into any image. The one-off importer
mounts them read-only from your existing `data/` and `docs/` folders.

Run:

```powershell
docker compose --profile import run --rm sensor-import
```

This performs both imports:

```text
Sensor_Inventory.xlsx -> sensor_points
merged_timeseries_student.csv -> sensor_readings
```

The large CSV can take several minutes. Do not close Docker Desktop during the
import.

After it finishes, confirm the sensor service still looks healthy:

```powershell
docker compose ps
docker compose logs sensor-service --tail 100
```

## 6.5 Open and test the application

Open:

```text
http://localhost:8080
```

Test these flows:

1. Sign in with Firebase.
2. Open the dashboard and verify charts load.
3. Open Sensors and calculate averages.
4. Verify weather appears.
5. Sign in as an Operator and generate recommendations.
6. Approve, reject, and reset a recommendation.

## 6.6 Stop the containers

Stop and remove containers while keeping PostgreSQL data:

```powershell
docker compose down
```

Start them again later:

```powershell
docker compose up -d
```

To completely erase the Docker PostgreSQL data and begin again:

```powershell
docker compose down -v
```

Use `down -v` only when you intentionally want to re-import all sensor data.

---

# Quick troubleshooting

## `.env.compose` not found

```powershell
Copy-Item .env.compose.example .env.compose
```

## Firebase returns 503

Confirm this file exists:

```text
secrets\firebase-service-account.json
```

Then recreate the containers:

```powershell
docker compose up -d --force-recreate
```

## A port is already allocated

Stop local Uvicorn, Vite, PostgreSQL, Redis, or old containers using the same
port. You can also change the left side of `5433:5432` or `6380:6379` in
`compose.yaml`.

## Frontend shows `502 Bad Gateway`

Check the backend containers:

```powershell
docker compose ps
docker compose logs auth-service --tail 100
docker compose logs sensor-service --tail 100
```

## A container continuously restarts

```powershell
docker compose logs <service-name> --tail 200
```

Common causes are a wrong PostgreSQL password, missing Firebase JSON, an invalid
environment value, or a Python import error.

## No sensors appear

Run the one-off import:

```powershell
docker compose --profile import run --rm sensor-import
```

## PostgreSQL password was changed after the first startup

PostgreSQL initializes credentials only when the volume is first created. For a
local reset:

```powershell
docker compose down -v
docker compose up -d
```

Then run the importer again.
