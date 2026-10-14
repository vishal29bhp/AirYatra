data "azurerm_client_config" "current" {}

locals {
  name_prefix = "airyatra-${var.environment}-${var.location_short}"
  # Short, globally unique suffix for names that must be unique across Azure.
  suffix = random_string.suffix.result
  tags = merge(var.tags, {
    application = "AirYatra"
    environment = var.environment
    managed_by  = "terraform"
  })
}

resource "random_string" "suffix" {
  length  = 4
  upper   = false
  special = false
  # A new region gets new names, so they never clash with soft-deleted Key Vaults or AI accounts of the old one.
  keepers = {
    location = var.location
  }
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.tags
}

# One identity for the API and the worker: Key Vault, Blob, Redis, OpenAI and ACR without any stored credential.
resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${local.name_prefix}-app"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

module "network" {
  source              = "../network"
  name_prefix         = local.name_prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = var.vnet_address_space
  tags                = local.tags
}

module "observability" {
  source              = "../observability"
  name_prefix         = local.name_prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  retention_in_days   = var.log_retention_days
  alert_email         = var.alert_email
  tags                = local.tags
}

module "keyvault" {
  source                     = "../keyvault"
  name                       = "kv-airyatra-${var.environment}-${local.suffix}"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.this.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  deployer_ip_cidrs          = var.deployer_ip_cidrs
  private_endpoint_subnet_id = module.network.private_endpoint_subnet_id
  private_dns_zone_id        = module.network.private_dns_zone_ids["keyvault"]
  log_analytics_workspace_id = module.observability.log_analytics_workspace_id
  tags                       = local.tags
}

module "storage" {
  source                     = "../storage"
  name                       = "stairyatra${var.environment}${local.suffix}"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.this.name
  replication_type           = var.storage_replication_type
  private_endpoint_subnet_id = module.network.private_endpoint_subnet_id
  private_dns_zone_id        = module.network.private_dns_zone_ids["blob"]
  log_analytics_workspace_id = module.observability.log_analytics_workspace_id
  tags                       = local.tags
}

module "redis" {
  source                     = "../redis"
  name                       = "redis-airyatra-${var.environment}-${local.suffix}"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.this.name
  sku_name                   = var.redis_sku_name
  high_availability_enabled  = var.redis_high_availability
  private_endpoint_subnet_id = module.network.private_endpoint_subnet_id
  private_dns_zone_id        = module.network.private_dns_zone_ids["redis"]
  data_access_object_ids     = { app = azurerm_user_assigned_identity.app.principal_id }
  tags                       = local.tags
}

module "mongodb" {
  source                         = "../mongodb_atlas"
  count                          = var.database_engine == "atlas" ? 1 : 0
  name_prefix                    = local.name_prefix
  atlas_org_id                   = var.atlas_org_id
  instance_size                  = var.atlas_instance_size
  autoscale_max_instance_size    = var.atlas_autoscale_max_instance_size
  dr_node_enabled                = var.atlas_dr_node_enabled
  mongo_major_version            = var.atlas_mongo_major_version
  database_name                  = var.database_name
  termination_protection_enabled = var.atlas_termination_protection
  backup_restore_window_days     = var.atlas_backup_restore_window_days
  azure_location                 = var.location
  resource_group_name            = azurerm_resource_group.this.name
  private_endpoint_subnet_id     = module.network.private_endpoint_subnet_id
  tags                           = local.tags
}

module "cosmos_mongo" {
  source                     = "../cosmos_mongo"
  count                      = var.database_engine == "cosmos_vcore" ? 1 : 0
  name                       = "mongo-airyatra-${var.environment}-${local.suffix}"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.this.name
  compute_tier               = var.cosmos_compute_tier
  storage_size_in_gb         = var.cosmos_storage_size_in_gb
  high_availability_enabled  = var.cosmos_high_availability
  private_endpoint_subnet_id = module.network.private_endpoint_subnet_id
  private_dns_zone_id        = module.network.private_dns_zone_ids["mongo"]
  tags                       = local.tags
}

module "openai" {
  source                     = "../openai"
  name                       = "oai-airyatra-${var.environment}-${local.suffix}"
  location                   = var.openai_location
  vnet_location              = var.location
  resource_group_name        = azurerm_resource_group.this.name
  deployments                = var.openai_deployments
  private_endpoint_subnet_id = module.network.private_endpoint_subnet_id
  private_dns_zone_id        = module.network.private_dns_zone_ids["openai"]
  tags                       = local.tags
}

# ---------------- Secrets ----------------
resource "random_password" "jwt" {
  length  = 64
  special = false
}

resource "azurerm_key_vault_secret" "generated" {
  #checkov:skip=CKV_AZURE_41:Rotation is a runbook step (docs/architecture), a hard expiry would take the app down.
  for_each = {
    MONGO_URL      = var.database_engine == "atlas" ? module.mongodb[0].connection_uri : module.cosmos_mongo[0].connection_uri
    JWT_SECRET_KEY = random_password.jwt.result
  }
  name         = lower(replace(each.key, "_", "-"))
  value        = each.value
  key_vault_id = module.keyvault.id
  content_type = "text/plain"
  depends_on   = [azurerm_role_assignment.deployer_kv_officer]
}

# Placeholders so Container Apps can start; real values are set out of band and never touched again by Terraform.
resource "azurerm_key_vault_secret" "manual" {
  #checkov:skip=CKV_AZURE_41:Rotation is a runbook step (docs/architecture), a hard expiry would take the app down.
  for_each     = toset(var.manual_secret_env_vars)
  name         = lower(replace(each.value, "_", "-"))
  value        = "set-me"
  key_vault_id = module.keyvault.id
  content_type = "text/plain"
  depends_on   = [azurerm_role_assignment.deployer_kv_officer]

  lifecycle {
    ignore_changes = [value, content_type, tags]
  }
}

# ---------------- RBAC (least privilege, managed identities only) ----------------
resource "azurerm_role_assignment" "deployer_kv_officer" {
  scope                = module.keyvault.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "app_kv_secrets_user" {
  scope                = module.keyvault.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "app_blob" {
  scope                = module.storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

# Needed to mint user-delegation SAS URLs for short-lived downloads.
resource "azurerm_role_assignment" "app_blob_delegator" {
  scope                = module.storage.id
  role_definition_name = "Storage Blob Delegator"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "app_openai" {
  scope                = module.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "app_acr_pull" {
  scope                = module.container_apps.registry_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
  principal_type       = "ServicePrincipal"
}

# ---------------- Compute ----------------
module "container_apps" {
  source                     = "../container_apps"
  name_prefix                = local.name_prefix
  location                   = var.location
  resource_group_name        = azurerm_resource_group.this.name
  infrastructure_subnet_id   = module.network.aca_subnet_id
  internal_only              = var.frontdoor_sku == "Premium_AzureFrontDoor"
  zone_redundancy_enabled    = var.zone_redundancy_enabled
  log_analytics_workspace_id = module.observability.log_analytics_workspace_id
  registry_name              = "crairyatra${var.environment}${local.suffix}"
  registry_sku               = var.registry_sku
  identity_id                = azurerm_user_assigned_identity.app.id
  identity_client_id         = azurerm_user_assigned_identity.app.client_id
  api_image                  = var.api_image
  worker_image               = var.worker_image
  api_cpu                    = var.api_cpu
  api_memory                 = var.api_memory
  api_min_replicas           = var.api_min_replicas
  api_max_replicas           = var.api_max_replicas
  worker_cpu                 = var.worker_cpu
  worker_memory              = var.worker_memory
  tags                       = local.tags

  env_vars = {
    APP_ENV                               = var.environment
    DB_NAME                               = var.database_name
    CORS_ORIGINS                          = join(",", local.cors_origins)
    FRONTEND_URL                          = local.public_url
    ACCESS_TOKEN_EXPIRE_MINUTES           = tostring(var.access_token_expire_minutes)
    COOKIE_SECURE                         = "true"
    COOKIE_SAMESITE                       = "strict"
    STORAGE_PROVIDER                      = "azure_blob"
    AZURE_STORAGE_ACCOUNT_URL             = module.storage.blob_endpoint
    LLM_PROVIDER                          = "azure_openai"
    STRIPE_PROVIDER                       = "stripe"
    FRONT_DOOR_ID                         = module.frontdoor.profile_resource_guid
    AZURE_OPENAI_ENDPOINT                 = module.openai.endpoint
    AZURE_OPENAI_DEPLOYMENT               = keys(var.openai_deployments)[0]
    REDIS_HOST                            = module.redis.hostname
    REDIS_PORT                            = "10000"
    APPLICATIONINSIGHTS_CONNECTION_STRING = module.observability.application_insights_connection_string
  }

  key_vault_secrets = merge(
    { for k, s in azurerm_key_vault_secret.generated : k => s.versionless_id },
    { for k, s in azurerm_key_vault_secret.manual : k => s.versionless_id },
  )

  depends_on = [azurerm_role_assignment.app_kv_secrets_user]
}

# ---------------- Edge ----------------
module "frontdoor" {
  source                   = "../frontdoor"
  enabled                  = var.frontdoor_enabled
  name_prefix              = local.name_prefix
  resource_group_name      = azurerm_resource_group.this.name
  location                 = var.location
  sku_name                 = var.frontdoor_sku
  waf_mode                 = var.waf_mode
  web_storage_account_name = "stairyatraweb${var.environment}${local.suffix}"
  api_fqdn                 = module.container_apps.api_fqdn
  api_private_link = var.frontdoor_sku == "Premium_AzureFrontDoor" ? {
    environment_id = module.container_apps.environment_id
    location       = module.container_apps.environment_location
  } : null
  custom_domains             = var.custom_domains
  allowed_country_codes      = var.allowed_country_codes
  log_analytics_workspace_id = module.observability.log_analytics_workspace_id
  tags                       = local.tags
}

locals {
  public_url = (
    !var.frontdoor_enabled ? module.frontdoor.web_endpoint :
    length(var.custom_domains) > 0 ? "https://${var.custom_domains[0]}" : "https://${module.frontdoor.endpoint_host_name}"
  )
  # With Front Door the site and API share one address; without it the browser calls the API's own address.
  api_url      = var.frontdoor_enabled ? local.public_url : "https://${module.container_apps.api_fqdn}"
  cors_origins = distinct(concat([local.public_url], var.cors_allowed_origins))
}

# ---------------- Delivery and governance ----------------
module "github_oidc" {
  source                 = "../github_oidc"
  name_prefix            = local.name_prefix
  location               = var.location
  resource_group_name    = azurerm_resource_group.this.name
  resource_group_id      = azurerm_resource_group.this.id
  github_repository      = var.github_repository
  github_environment     = var.environment
  registry_id            = module.container_apps.registry_id
  web_storage_account_id = module.frontdoor.web_storage_account_id
  tags                   = local.tags
}

module "governance" {
  source                = "../governance"
  name_prefix           = local.name_prefix
  resource_group_id     = azurerm_resource_group.this.id
  allowed_locations     = distinct([var.location, var.dr_location, var.openai_location])
  monthly_budget_amount = var.monthly_budget_amount
  budget_start_date     = var.budget_start_date
  alert_email           = var.alert_email
  enable_defender_plans = var.enable_defender_plans
}

resource "azurerm_load_test" "this" {
  count               = var.enable_load_testing ? 1 : 0
  name                = "lt-${local.name_prefix}"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  description         = "k6/JMeter runs for the Q.3 1K and 20K user profiles."
  tags                = local.tags
}
