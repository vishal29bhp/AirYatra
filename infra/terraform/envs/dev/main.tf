# AirYatra dev: smallest footprint that still exercises every production component.
module "platform" {
  source = "../../modules/platform"

  environment        = "dev"
  vnet_address_space = "10.20.0.0/16"
  deployer_ip_cidrs  = var.deployer_ip_cidrs

  # Compute: 1 API replica is enough for dev; no zone redundancy.
  api_image               = var.api_image
  worker_image            = var.worker_image
  api_cpu                 = 0.5
  api_memory              = "1Gi"
  api_min_replicas        = 1
  api_max_replicas        = 3
  worker_cpu              = 0.25
  worker_memory           = "0.5Gi"
  zone_redundancy_enabled = false
  registry_sku            = "Basic"

  # Data
  storage_replication_type          = "LRS"
  redis_sku_name                    = "Balanced_B0"
  redis_high_availability           = false
  atlas_org_id                      = var.atlas_org_id
  atlas_instance_size               = "M10"
  atlas_autoscale_max_instance_size = "M20"
  atlas_dr_node_enabled             = false
  atlas_termination_protection      = false
  atlas_backup_restore_window_days  = 2

  # AI
  openai_deployments = {
    "gpt-4o-mini" = {
      model_name    = "gpt-4o-mini"
      model_version = "2024-07-18"
      sku_name      = "GlobalStandard"
      capacity      = 10
    }
  }

  # Edge: Standard Front Door (no managed WAF rules, API reached over its public ingress), WAF in detection.
  frontdoor_sku        = "Standard_AzureFrontDoor"
  waf_mode             = "Detection"
  custom_domains       = var.custom_domains
  cors_allowed_origins = ["http://localhost:3000"]

  # Operations
  log_retention_days    = 30
  alert_email           = var.alert_email
  monthly_budget_amount = 300
  budget_start_date     = var.budget_start_date
  enable_defender_plans = false
  enable_load_testing   = true
}
