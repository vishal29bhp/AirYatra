# Deploy

Releases go through the **Deploy to Azure** workflow (`.github/workflows/azure-deploy.yml`). Nobody deploys from a laptop.

## One-time setup per environment

1. Apply Terraform for the environment ([infra/terraform/README.md](../../infra/terraform/README.md)).
2. In GitHub (Settings, Environments), create the `dev` and `prod` environments. Add Vishal as a **required reviewer on
   `prod`** and limit `prod` to the `main` branch.
3. Add every value from `terraform output github_actions_variables` as an environment **variable** (not a secret).
   None of them is secret. Sign-in uses OIDC, so there is no client secret.

## Release

1. Merge to `main` only when `backend-ci`, `container-image` and CodeQL are green.
2. Actions, **Deploy to Azure**, Run workflow, environment `dev`, leaving `image_tag` empty.
3. The workflow runs these steps:
   - Records the images running now in the run summary (you need them to roll back).
   - Builds `backend/` and scans it with Trivy. It stops on fixable HIGH or CRITICAL findings.
   - Pushes `airyatra-api:<git sha>` to ACR.
   - Rolls the `api` and `worker` apps to that image.
   - Waits for the new revision to be `Running` and `GET /health` to return 200.
   - Builds the web app with `REACT_APP_BACKEND_URL=<public url>`, uploads it to the `$web` container, and purges Front Door.
4. Smoke test dev:
   - Sign in.
   - Search a route and create a test inquiry.
   - Open a booking chat.
   - Run a Razorpay **test-mode** payment.
5. Run the same workflow with environment `prod`. It waits for the `prod` reviewer to approve.
6. Watch for 30 minutes in Application Insights (Failures, Performance) and on the alerts listed in
   [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md). If anything regresses, follow [ROLLBACK.md](ROLLBACK.md).

## Notes

- Both apps run a single active revision (`revision_mode = Single`). A new image replaces the old revision once the new
  one is healthy, so the API has no downtime.
- The worker owns APScheduler and must stay at exactly one replica. Do not scale it out.
- Database changes are additive only (new indexes); nothing in a deploy rewrites stored data. Indexes are created at
  API start-up by `db_optimization.optimize_database()`.
- Terraform ignores the container image, so a later `terraform apply` never undoes a deploy.
