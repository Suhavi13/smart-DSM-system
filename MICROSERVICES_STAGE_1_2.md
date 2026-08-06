
# DSM Microservices Migration — Stages 1 and 2

The original `backend/` monolith is intentionally left unchanged as a rollback
copy. The new `services/` folder contains independently runnable FastAPI
applications split by responsibility.

## New services

| Service | Port | Responsibility |
|---|---:|---|
| auth-service | 8001 | Firebase identity and Viewer/Operator roles |
| sensor-service | 8002 | Sensor inventory, readings, averages, and dashboard data |
| weather-service | 8003 | Open-Meteo integration and Redis caching |
| recommendation-service | 8004 | Rules, optional AI text, and recommendation storage |
| decision-service | 8005 | Approval/rejection/reset workflow and audit history |

## Important transition note

The sensor, recommendation, and decision services currently use the same
PostgreSQL database so the project can be separated without a risky schema
rewrite. Table ownership is:

- sensor-service: `sensor_points`, `sensor_readings`
- recommendation-service: `recommendations`
- decision-service: `recommendation_decisions`

Recommendation-service reads sensor tables, and decision-service updates the
stored recommendation status. Replace those shared-table reads with HTTP APIs
in a later hardening stage.

## Install local dependencies

Run from the `DSM_project` root in your existing virtual environment:

```powershell
py -m pip install -r .\services\requirements-local.txt
```

The service loaders first read the existing `backend/.env`, then override it
with a service-specific `.env` when one exists. This lets the split services
start immediately while you gradually create separate Azure settings.

## Start the five services

Open five PowerShell terminals at the project root.

```powershell
py -m uvicorn app.main:app --app-dir .\services\auth-service --reload --port 8001
```

```powershell
py -m uvicorn app.main:app --app-dir .\services\sensor-service --reload --port 8002
```

```powershell
py -m uvicorn app.main:app --app-dir .\services\weather-service --reload --port 8003
```

```powershell
py -m uvicorn app.main:app --app-dir .\services\recommendation-service --reload --port 8004
```

```powershell
py -m uvicorn app.main:app --app-dir .\services\decision-service --reload --port 8005
```

Test these URLs:

- `http://127.0.0.1:8001/health`
- `http://127.0.0.1:8002/health`
- `http://127.0.0.1:8003/health`
- `http://127.0.0.1:8004/health`
- `http://127.0.0.1:8005/health`

Authenticated API routes keep their existing paths. The frontend is not changed
in these two stages; proxy routing and Docker are the next stages.

## Sensor import tools

Run from the project root:

```powershell
py .\services\sensor-service\tools\validate_sensor_inventory.py
py .\services\sensor-service\tools\import_selected_sensors.py
py .\services\sensor-service\tools\import_sensor_readings.py
```

## What was deliberately not done yet

- No Dockerfiles or Docker Compose file
- No frontend proxy changes
- No ACR or AKS files
- No deletion of the original monolith
- No database-per-service redesign
