# Dev on an Azure Free Trial: the subscription allows a single Container Apps environment, so the API
# runs on one App Service instance instead. With one instance the scheduler runs in the API process
# (SCHEDULER_ENABLED=true) and still fires each job once, so there is no separate worker.
locals {
  placeholder = !startswith(var.image, var.registry_login_server)
  # "registry/repo:tag" -> "repo:tag"; App Service wants the registry URL separately.
  image_name   = local.placeholder ? replace(var.image, "mcr.microsoft.com/", "") : trimprefix(var.image, "${var.registry_login_server}/")
  registry_url = local.placeholder ? "https://mcr.microsoft.com" : "https://${var.registry_login_server}"
  port         = local.placeholder ? 80 : var.api_port
}

resource "azurerm_service_plan" "this" {
  #checkov:skip=CKV_AZURE_212:Dev runs a single B1 instance; production uses Container Apps with several replicas.
  #checkov:skip=CKV_AZURE_225:Zone redundancy needs Premium plans; dev only.
  name                = "asp-${var.name_prefix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"
  sku_name            = var.sku_name
  tags                = var.tags
}

resource "azurerm_linux_web_app" "api" {
  #checkov:skip=CKV_AZURE_17:Users sign in with JWTs; client certificates do not apply to a public web app.
  #checkov:skip=CKV_AZURE_88:No Azure Files mounts; state lives in Cosmos DB, Blob and Redis.
  #checkov:skip=CKV_AZURE_13:The API authenticates users itself with JWTs; Easy Auth would block the public routes.
  #checkov:skip=CKV_AZURE_222:The API is public by design (the browser calls it directly in dev).
  name                            = "app-${var.name_prefix}-api"
  location                        = var.location
  resource_group_name             = var.resource_group_name
  service_plan_id                 = azurerm_service_plan.this.id
  https_only                      = true
  virtual_network_subnet_id       = var.subnet_id
  key_vault_reference_identity_id = var.identity_id
  client_affinity_enabled         = false
  tags                            = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.identity_id]
  }

  site_config {
    always_on                                     = true
    vnet_route_all_enabled                        = true
    ftps_state                                    = "Disabled"
    minimum_tls_version                           = "1.2"
    http2_enabled                                 = true
    websockets_enabled                            = true
    health_check_path                             = var.health_path
    health_check_eviction_time_in_min             = 10
    container_registry_use_managed_identity       = !local.placeholder
    container_registry_managed_identity_client_id = local.placeholder ? null : var.identity_client_id

    application_stack {
      docker_image_name   = local.image_name
      docker_registry_url = local.registry_url
    }
  }

  logs {
    detailed_error_messages = true
    failed_request_tracing  = true

    http_logs {
      file_system {
        retention_in_days = 7
        retention_in_mb   = 35
      }
    }
  }

  app_settings = merge(
    var.env_vars,
    {
      AZURE_CLIENT_ID                     = var.identity_client_id
      SCHEDULER_ENABLED                   = "true"
      OTEL_SERVICE_NAME                   = "airyatra-api"
      WEBSITES_PORT                       = tostring(local.port)
      WEBSITES_ENABLE_APP_SERVICE_STORAGE = "false"
    },
    { for name, id in var.key_vault_secrets : name => "@Microsoft.KeyVault(SecretUri=${id})" },
  )

  lifecycle {
    # CI/CD rolls new images (and switches the pull to the managed identity); Terraform owns the rest.
    ignore_changes = [
      site_config[0].application_stack,
      site_config[0].container_registry_use_managed_identity,
      site_config[0].container_registry_managed_identity_client_id,
      app_settings["WEBSITES_PORT"],
    ]
  }
}
