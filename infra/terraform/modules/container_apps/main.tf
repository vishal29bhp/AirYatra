locals {
  placeholder_image = "mcr.microsoft.com/k8se/quickstart:latest"
  # Container Apps secret names must be lowercase alphanumerics and dashes.
  secrets = { for env_name, kv_id in var.key_vault_secrets : env_name => {
    name  = replace(lower(env_name), "_", "-")
    kv_id = kv_id
  } }
  common_env = merge(var.env_vars, {
    AZURE_CLIENT_ID = var.identity_client_id
  })
}

resource "azurerm_container_registry" "this" {
  #checkov:skip=CKV_AZURE_139:GitHub-hosted runners push over the public endpoint with Entra (OIDC) auth; no admin user or keys.
  #checkov:skip=CKV_AZURE_163:Images are scanned by Defender for Containers (governance module) and Trivy in CI.
  #checkov:skip=CKV_AZURE_164:Image signing (Notation) is planned for Phase 5; CI builds from protected main only.
  #checkov:skip=CKV_AZURE_165:Single-region compute until stage 2 DR.
  #checkov:skip=CKV_AZURE_166:Quarantine needs a scanner hook; covered by Defender + CI scanning gate.
  #checkov:skip=CKV_AZURE_233:Zone redundancy is on for Premium (prod); Basic dev registry has none.
  #checkov:skip=CKV_AZURE_237:Dedicated data endpoints only matter with firewall rules, which runners cannot use.
  name                = var.registry_name
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = var.registry_sku
  # Entra-only pulls/pushes: no admin user or shared credentials.
  admin_enabled = false
  # Premium-only features: untagged manifest cleanup and zone redundancy (prod).
  retention_policy_in_days = var.registry_sku == "Premium" ? 7 : null
  zone_redundancy_enabled  = var.registry_sku == "Premium"
  tags                     = var.tags
}

resource "azurerm_container_app_environment" "this" {
  name                           = "cae-${var.name_prefix}"
  location                       = var.location
  resource_group_name            = var.resource_group_name
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  infrastructure_subnet_id       = var.infrastructure_subnet_id
  internal_load_balancer_enabled = var.internal_only
  zone_redundancy_enabled        = var.zone_redundancy_enabled
  tags                           = var.tags

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

resource "azurerm_container_app" "api" {
  name                         = "ca-${var.name_prefix}-api"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.identity_id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = var.identity_id
  }

  dynamic "secret" {
    for_each = local.secrets
    content {
      name                = secret.value.name
      key_vault_secret_id = secret.value.kv_id
      identity            = var.identity_id
    }
  }

  ingress {
    # "external" inside an internal environment = reachable from the VNet / Front Door Private Link only.
    external_enabled           = true
    allow_insecure_connections = false
    target_port                = var.api_image == local.placeholder_image ? 80 : var.api_port
    transport                  = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.api_min_replicas
    max_replicas = var.api_max_replicas

    http_scale_rule {
      name                = "http-concurrency"
      concurrent_requests = tostring(var.api_concurrent_requests_per_replica)
    }

    custom_scale_rule {
      name             = "cpu"
      custom_rule_type = "cpu"
      metadata = {
        type  = "Utilization"
        value = "70"
      }
    }

    container {
      name   = "api"
      image  = var.api_image
      cpu    = var.api_cpu
      memory = var.api_memory

      dynamic "env" {
        for_each = merge(local.common_env, { SCHEDULER_ENABLED = "false", OTEL_SERVICE_NAME = "airyatra-api" })
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.secrets
        content {
          name        = env.key
          secret_name = env.value.name
        }
      }

      dynamic "liveness_probe" {
        for_each = var.api_image == local.placeholder_image ? [] : [1]
        content {
          transport        = "HTTP"
          port             = var.api_port
          path             = var.health_path
          interval_seconds = 15
        }
      }

      dynamic "readiness_probe" {
        for_each = var.api_image == local.placeholder_image ? [] : [1]
        content {
          transport        = "HTTP"
          port             = var.api_port
          path             = var.health_path
          interval_seconds = 10
        }
      }
    }
  }

  lifecycle {
    # CI/CD rolls new images; Terraform owns everything else.
    ignore_changes = [template[0].container[0].image]
  }
}

# Single-replica worker: runs APScheduler so jobs fire exactly once however far the API scales (Q.2 item 10).
resource "azurerm_container_app" "worker" {
  name                         = "ca-${var.name_prefix}-worker"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.identity_id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = var.identity_id
  }

  dynamic "secret" {
    for_each = local.secrets
    content {
      name                = secret.value.name
      key_vault_secret_id = secret.value.kv_id
      identity            = var.identity_id
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name    = "worker"
      image   = var.worker_image
      cpu     = var.worker_cpu
      memory  = var.worker_memory
      command = var.worker_image == local.placeholder_image ? null : var.worker_command

      dynamic "env" {
        for_each = merge(local.common_env, { SCHEDULER_ENABLED = "true", OTEL_SERVICE_NAME = "airyatra-worker" })
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.secrets
        content {
          name        = env.key
          secret_name = env.value.name
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }
}
