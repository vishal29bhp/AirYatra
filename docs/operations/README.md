# Operations runbooks

These runbooks cover AirYatra on Azure, as built by [infra/terraform](../../infra/terraform/README.md). Each one assumes the
operator has `az login` access to the subscription and Owner or Contributor on the environment's resource group
(`rg-airyatra-<env>-cin`).

| Runbook | Use it when |
|---|---|
| [DEPLOY.md](DEPLOY.md) | Releasing a new API, worker or web build |
| [ROLLBACK.md](ROLLBACK.md) | A release is broken and the previous build must come back |
| [ROTATE_SECRETS.md](ROTATE_SECRETS.md) | A key is due for rotation, or one may have leaked |
| [SCALE.md](SCALE.md) | Moving from 1K to 20K users, or handling a traffic spike |
| [BACKUP_RESTORE.md](BACKUP_RESTORE.md) | Restoring data (RPO 15 min, RTO 4 h), or running the quarterly restore test |
| [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) | Something is down, slow or compromised |
| [../migration/CUTOVER_RUNBOOK.md](../migration/CUTOVER_RUNBOOK.md) | The one-time move from Emergent to Azure |

Actions that need Vishal's written approval in the project thread before anyone runs them (master prompt
Constraint 9):
- Deleting or overwriting data, which includes restoring over the live cluster.
- DNS cutover.
- Rotating live payment keys.
- Anything that touches `prod` outside the deploy workflow.

## Shell variables used in every runbook

```bash
ENV=prod                                   # or dev
RG=rg-airyatra-$ENV-cin
API=$(az containerapp list -g $RG --query "[?ends_with(name,'-api')].name | [0]" -o tsv)
WORKER=$(az containerapp list -g $RG --query "[?ends_with(name,'-worker')].name | [0]" -o tsv)
KV=$(az keyvault list -g $RG --query "[0].name" -o tsv)
```

The same names come from Terraform: `terraform -chdir=infra/terraform/envs/$ENV output github_actions_variables`.
