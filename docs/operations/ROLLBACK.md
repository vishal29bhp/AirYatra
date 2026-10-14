# Roll back

## API and worker (minutes)

Every deployed image stays in ACR under its git SHA. To go back:

1. Find the last good SHA. It is either the "images running now" lines in the summary of the failed deploy run, or:
   ```bash
   az acr repository show-tags -n <acr-name> --repository airyatra-api --orderby time_desc --top 10 -o table
   ```
2. Run **Deploy to Azure** with the same environment and `image_tag = <last good sha>`. Leave `deploy_frontend` on so
   the web app built from that commit goes back too. The workflow checks the tag exists, skips the build, rolls both apps
   and waits for health.
3. If GitHub Actions is unavailable, run the same commands by hand:
   ```bash
   IMAGE=<acr>.azurecr.io/airyatra-api:<last good sha>
   az containerapp update -n $API -g $RG --image $IMAGE
   az containerapp update -n $WORKER -g $RG --image $IMAGE
   ```
   Dev runs the API on App Service (one web app, no worker), so there it is:
   ```bash
   az webapp config container set -n $API -g $RG --container-image-name $IMAGE --container-registry-url https://<acr>.azurecr.io
   ```

## Web app only

Run the workflow with `deploy_api = false`, `deploy_frontend = true` and `image_tag = <last good sha>`. Blob soft delete
(7 days) also keeps the previous files if the build itself cannot be repeated.

## Configuration or infrastructure

- **Terraform change:** revert the commit and `plan` / `apply` again. Review the plan for any replacement of stateful
  resources (Atlas cluster, storage accounts, Key Vault, Redis) before applying.
- **Bad secret value:** see [ROTATE_SECRETS.md](ROTATE_SECRETS.md#roll-back-a-secret). Key Vault keeps every version.

## Data

Code rollback never touches data. If a release wrote bad data, follow [BACKUP_RESTORE.md](BACKUP_RESTORE.md). That
needs Vishal's approval because it overwrites data.
