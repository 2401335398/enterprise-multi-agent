# Enterprise Intelligence Frontend

React + TypeScript frontend for the FastAPI multi-agent service.

## Development

```powershell
cd frontend
npm install
npm run dev
```

The development server runs at `http://127.0.0.1:5173`. Vite proxies
`/api` and `/health` to `http://127.0.0.1:8000`, so start the backend in a
separate terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Checks

```powershell
npm run lint
npm run test
npm run build
```

Set `VITE_API_BASE` when the frontend must call an API on a different origin.
That deployment also requires the backend or reverse proxy to allow CORS.
