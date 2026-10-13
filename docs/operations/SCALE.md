# Scale

Sizing targets: about 1,000 users at launch (stage 1) and 20,000 later (stage 2). Everything scales through values in
`infra/terraform/envs/prod/main.tf`. No module changes are needed.

## Planned move to stage 2

| Setting | Stage 1 | Stage 2 | Downtime |
|---|---|---|---|
| `api_min_replicas` / `api_max_replicas` | 2 / 6 | 3 / 20 | None |
| `api_cpu` / `api_memory` | 1 / 2Gi | 2 / 4Gi | None (rolling new revision) |
| `atlas_instance_size` / autoscale max | M10 / M30 | M30 / M50 | None (Atlas rolling resize) |
| `atlas_dr_node_enabled` | false | true | None |
| `redis_sku_name` | Balanced_B1 | Balanced_B5 | Brief reconnects; the app falls back to in-process limits while Redis is unavailable |
| `openai_deployments.capacity` | 30 | 100 | None |
| Front Door, WAF, Key Vault, Blob | unchanged | unchanged | |

Steps:
1. Run the load test at the stage 2 profile against `dev` scaled the same way (master prompt Q.3).
2. Change the values, then `terraform plan`. The plan must only update resources in place, with no destroy or replace.
3. Apply in a quiet hour and watch p95 latency and the error rate for an hour.

## Traffic spike (temporary)

- The API autoscales on HTTP concurrency and CPU up to `api_max_replicas`. To raise the ceiling now, without waiting
  for Terraform:
  ```bash
  az containerapp update -n $API -g $RG --max-replicas 12
  ```
  Put the same value in Terraform afterwards. Otherwise the next apply sets it back.
- Atlas autoscaling grows the cluster up to the autoscale maximum on its own. Check it in Atlas, Metrics.
- Rate limits are shared by every replica (Redis), so adding replicas does not raise any single client's limit.
- **Never scale the worker above one replica.** It runs the scheduled jobs, and two workers would run every job twice
  (duplicate payouts and reminders).

## Watch

Application Insights shows p95 latency and failure rate. The Container Apps metrics show replica count, CPU and memory.
Atlas metrics show CPU, connections and the oplog window. Azure Managed Redis shows server load.
