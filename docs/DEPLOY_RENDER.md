# Deploy Public URL via Render

This repo includes a Render blueprint at `render.yaml` for:
- `underwriting-dashboard` (public web URL)
- `underwriting-api` (private service)
- `underwriting-redis` (managed Redis)

## One-Time Setup

1. Push this branch to GitHub.
2. In Render, click `New +` -> `Blueprint`.
3. Select this GitHub repo and branch.
4. Render will detect `render.yaml` and show 3 services.
5. Click `Apply` to start deployment.

## Environment Variables

The blueprint already sets required defaults for demo mode:
- `UNDERWRITING_DEMO_MODE=true`
- `SIMULATED_AGENT_DELAY_S=0.05`
- `UNDERWRITING_API_URL=http://underwriting-api:8000` (dashboard -> private API)

If you want real Bedrock-backed behavior instead of demo mode, set in Render for `underwriting-api`:
- `UNDERWRITING_DEMO_MODE=false`
- `AWS_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- Any other Bedrock-related env vars your runtime expects

## Public URL to Share

After deploy succeeds, open the `underwriting-dashboard` service in Render and copy its URL.

It will look like:
- `https://underwriting-dashboard.onrender.com`

That is the public URL you can share.

## Health Checks

- API health: `GET /health`
- Dashboard root: `/`

## Troubleshooting

- If dashboard loads but cannot submit: verify API service is healthy and `UNDERWRITING_API_URL` is exactly `http://underwriting-api:8000`.
- If API fails on Bedrock calls: use demo mode first, then add AWS credentials and region.
- If first deploy is slow: Render cold builds can take several minutes for Python dependencies.
