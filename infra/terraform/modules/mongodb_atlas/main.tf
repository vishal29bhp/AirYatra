# MongoDB Atlas on Azure (Central India). Same engine as today, so documents, types and query
# semantics stay byte-for-byte identical (Constraint 1). Reached only over Azure Private Link.

terraform {
  required_providers {
    mongodbatlas = {
      source = "mongodb/mongodbatlas"
    }
    azurerm = {
      source = "hashicorp/azurerm"
    }
    random = {
      source = "hashicorp/random"
    }
  }
}

variable "name_prefix" {
  type = string
}
variable "atlas_org_id" {
  type = string
}
variable "atlas_region" {
  description = "Atlas region name for the primary, e.g. INDIA_CENTRAL."
  type        = string
  default     = "INDIA_CENTRAL"
}
variable "atlas_dr_region" {
  description = "Atlas region for the DR electable node, e.g. INDIA_SOUTH."
  type        = string
  default     = "INDIA_SOUTH"
}
variable "dr_node_enabled" {
  description = "Stage 2: add an electable node in South India so the replica set survives a regional outage."
  type        = bool
  default     = false
}
variable "instance_size" {
  description = "M10 for dev and 1K users, M30 at 20K users."
  type        = string
}
variable "autoscale_max_instance_size" {
  type = string
}
variable "mongo_major_version" {
  description = "Keep equal to the version the data is exported from so behaviour does not change."
  type        = string
  default     = "7.0"
}
variable "database_name" {
  type    = string
  default = "airyatra_db"
}
variable "termination_protection_enabled" {
  type = bool
}
variable "backup_restore_window_days" {
  description = "Point-in-time restore window (RPO <= 15 min needs continuous backup)."
  type        = number
}
variable "azure_location" {
  description = "Azure region of the VNet that connects over Private Link, e.g. centralindia."
  type        = string
}
variable "resource_group_name" {
  type = string
}
variable "private_endpoint_subnet_id" {
  type = string
}
variable "tags" {
  type    = map(string)
  default = {}
}

resource "mongodbatlas_project" "this" {
  name   = var.name_prefix
  org_id = var.atlas_org_id
  tags   = var.tags
}

resource "mongodbatlas_advanced_cluster" "this" {
  project_id                     = mongodbatlas_project.this.id
  name                           = var.name_prefix
  cluster_type                   = "REPLICASET"
  mongo_db_major_version         = var.mongo_major_version
  backup_enabled                 = true
  pit_enabled                    = true
  termination_protection_enabled = var.termination_protection_enabled
  tags                           = var.tags

  advanced_configuration = {
    # Fixes the w:1 / journal:false setting in backend/database.py at the server side too.
    default_write_concern        = "majority"
    minimum_enabled_tls_protocol = "TLS1_2"
    # No server-side JavaScript ($where, $function): closes a NoSQL-injection path (S.2 A03).
    javascript_enabled = false
  }

  replication_specs = [
    {
      region_configs = concat(
        [
          {
            provider_name = "AZURE"
            region_name   = var.atlas_region
            priority      = 7
            electable_specs = {
              instance_size = var.instance_size
              node_count    = var.dr_node_enabled ? 2 : 3
            }
            auto_scaling = {
              compute_enabled            = true
              compute_scale_down_enabled = true
              compute_min_instance_size  = var.instance_size
              compute_max_instance_size  = var.autoscale_max_instance_size
              disk_gb_enabled            = true
            }
          }
        ],
        var.dr_node_enabled ? [
          {
            provider_name = "AZURE"
            region_name   = var.atlas_dr_region
            priority      = 6
            electable_specs = {
              instance_size = var.instance_size
              node_count    = 1
            }
            auto_scaling = {
              compute_enabled            = true
              compute_scale_down_enabled = true
              compute_min_instance_size  = var.instance_size
              compute_max_instance_size  = var.autoscale_max_instance_size
              disk_gb_enabled            = true
            }
          }
        ] : []
      )
    }
  ]

  lifecycle {
    # Atlas auto-scaling changes the live instance size; do not fight it on every plan.
    ignore_changes = [replication_specs[0].region_configs[0].electable_specs.instance_size]
  }
}

resource "mongodbatlas_cloud_backup_schedule" "this" {
  project_id          = mongodbatlas_project.this.id
  cluster_name        = mongodbatlas_advanced_cluster.this.name
  restore_window_days = var.backup_restore_window_days

  policy_item_hourly {
    frequency_interval = 6
    retention_unit     = "days"
    retention_value    = 7
  }
  policy_item_daily {
    frequency_interval = 1
    retention_unit     = "days"
    retention_value    = 35
  }
}

# ---- Private Link: Atlas endpoint service <-> Azure private endpoint in the app VNet ----

resource "mongodbatlas_privatelink_endpoint" "this" {
  project_id    = mongodbatlas_project.this.id
  provider_name = "AZURE"
  region        = var.azure_location
}

resource "azurerm_private_endpoint" "atlas" {
  name                = "pe-${var.name_prefix}-atlas"
  location            = var.azure_location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = mongodbatlas_privatelink_endpoint.this.private_link_service_name
    private_connection_resource_id = mongodbatlas_privatelink_endpoint.this.private_link_service_resource_id
    is_manual_connection           = true
    request_message                = "AirYatra API to Atlas"
  }
}

resource "mongodbatlas_privatelink_endpoint_service" "this" {
  project_id                  = mongodbatlas_privatelink_endpoint.this.project_id
  private_link_id             = mongodbatlas_privatelink_endpoint.this.private_link_id
  endpoint_service_id         = azurerm_private_endpoint.atlas.id
  private_endpoint_ip_address = azurerm_private_endpoint.atlas.private_service_connection[0].private_ip_address
  provider_name               = "AZURE"
}

# ---- Application user: readWrite on the app database only (least privilege) ----

resource "random_password" "app" {
  length  = 40
  special = false
}

resource "mongodbatlas_database_user" "app" {
  project_id         = mongodbatlas_project.this.id
  username           = "airyatra-api"
  password           = random_password.app.result
  auth_database_name = "admin"

  roles {
    role_name     = "readWrite"
    database_name = var.database_name
  }

  scopes {
    name = mongodbatlas_advanced_cluster.this.name
    type = "CLUSTER"
  }
}

locals {
  # Prefer the Private Link SRV string; it only exists after the endpoint service is up.
  private_srv = try(
    [for pe in mongodbatlas_advanced_cluster.this.connection_strings.private_endpoint : pe.srv_connection_string
    if length([for e in pe.endpoints : e if e.endpoint_id == azurerm_private_endpoint.atlas.id]) > 0][0],
    mongodbatlas_advanced_cluster.this.connection_strings.standard_srv
  )
  connection_uri = replace(
    local.private_srv,
    "mongodb+srv://",
    "mongodb+srv://${mongodbatlas_database_user.app.username}:${random_password.app.result}@"
  )
}

output "project_id" {
  value = mongodbatlas_project.this.id
}
output "cluster_name" {
  value = mongodbatlas_advanced_cluster.this.name
}
output "connection_uri" {
  description = "Full MONGO_URL with credentials; written to Key Vault, never to app settings."
  value       = "${local.connection_uri}/?retryWrites=true&w=majority&journal=true"
  sensitive   = true
}
