# AirYatra prod, sized for stage 1 (about 1,000 users). Stage 2 (20,000 users) is a tfvars change:
# see docs/architecture/01-target-architecture.md, "Scale triggers".
module "platform" {
  source = "../../modules/platform"

  environment        = "prod"
  vnet_address_space = "10.10.0.0/16"
  deployer_ip_cidrs  = var.deployer_ip_cidrs

  # Compute: 2 replicas minimum for HA across zones.
  api_image               = var.api_image
  worker_image            = var.worker_image
  api_cpu                 = 1
  api_memory              = "2Gi"
  api_min_replicas        = 2
  api_max_replicas        = 6
  worker_cpu              = 0.5
  worker_memory           = "1Gi"
  zone_redundancy_enabled = true
  registry_sku            = "Premium"

  # Data: geo-redundant blobs, HA Redis, Atlas M10 with continuous backup (PITR) and autoscale to M30.
  storage_replication_type = "RAGZRS"
  redis_sku_name           = "Balanced_B1"
  redis_high_availability  = true
  # Switch to "cosmos_vcore" (with cosmos_compute_tier = "M30", cosmos_high_availability = true) to avoid Atlas.
  database_engine                   = "atlas"
  atlas_org_id                      = var.atlas_org_id
  atlas_instance_size               = "M10"
  atlas_autoscale_max_instance_size = "M30"
  atlas_dr_node_enabled             = false
  atlas_termination_protection      = var.atlas_termination_protection
  atlas_backup_restore_window_days  = 7

  # AI: India-region deployment keeps prompts in India.
  openai_deployments = {
    # gpt-4o-mini (2024-07-18) no longer accepts new deployments.
    "airyatra-chat" = {
      model_name    = "gpt-5-mini"
      model_version = "2025-08-07"
      sku_name      = "Standard"
      capacity      = 30
    }
  }

  # Edge: Premium Front Door (OWASP + bot rules, Private Link to an internal API), WAF blocking.
  frontdoor_sku         = "Premium_AzureFrontDoor"
  waf_mode              = "Prevention"
  custom_domains        = var.custom_domains
  allowed_country_codes = []

  # Operations
  log_retention_days    = 90
  alert_email           = var.alert_email
  monthly_budget_amount = 1200
  budget_start_date     = var.budget_start_date
  enable_defender_plans = true
  enable_load_testing   = true
}
