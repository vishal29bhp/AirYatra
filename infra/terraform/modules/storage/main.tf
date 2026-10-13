# Private Blob storage that replaces local disk (uploads/, secure_uploads/), boto3 S3 and Emergent object storage.
# Access is Entra-only (no shared keys); downloads use short-lived user-delegation SAS URLs.

variable "name" {
  description = "Storage account name (3-24 lowercase alphanumerics, globally unique)."
  type        = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "replication_type" {
  description = "LRS/ZRS for dev, RAGZRS for prod (geo copy in the paired South India region)."
  type        = string
}
variable "soft_delete_days" {
  type    = number
  default = 30
}
variable "audit_log_retention_days" {
  description = "WORM retention for the append-only audit log container."
  type        = number
  default     = 365
}
variable "private_endpoint_subnet_id" {
  type = string
}
variable "private_dns_zone_id" {
  type = string
}
variable "enable_malware_scanning" {
  description = "Defender for Storage malware scanning on upload (S.3 file uploads)."
  type        = bool
  default     = true
}
variable "log_analytics_workspace_id" {
  type = string
}
variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  # One container per data class so access and lifecycle can differ.
  containers = ["uploads", "documents", "kyc", "invoices", "exports", "audit-logs"]
}

resource "azurerm_storage_account" "this" {
  #checkov:skip=CKV2_AZURE_1:KYC files keep the existing app-level encryption (FILE_ENCRYPTION_KEY in Key Vault) on top of platform encryption; CMK is a later option.
  #checkov:skip=CKV_AZURE_33:Queue service is not used.
  #checkov:skip=CKV2_AZURE_21:Blob read/write/delete logs go to Log Analytics through azurerm_monitor_diagnostic_setting.blob.
  #checkov:skip=CKV_AZURE_206:Replication is set per environment (RAGZRS in prod).
  name                              = var.name
  location                          = var.location
  resource_group_name               = var.resource_group_name
  account_kind                      = "StorageV2"
  account_tier                      = "Standard"
  account_replication_type          = var.replication_type
  min_tls_version                   = "TLS1_2"
  https_traffic_only_enabled        = true
  shared_access_key_enabled         = false
  default_to_oauth_authentication   = true
  allow_nested_items_to_be_public   = false
  public_network_access_enabled     = false
  infrastructure_encryption_enabled = true
  cross_tenant_replication_enabled  = false
  tags                              = var.tags

  blob_properties {
    versioning_enabled  = true
    change_feed_enabled = true

    delete_retention_policy {
      days = var.soft_delete_days
    }
    container_delete_retention_policy {
      days = var.soft_delete_days
    }
  }

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }
}

# Containers are created through ARM (storage_account_id), so Terraform does not need data-plane network access.
resource "azurerm_storage_container" "this" {
  #checkov:skip=CKV2_AZURE_21:Blob logging is configured once on the blob service (diagnostic setting), not per container.
  for_each              = toset(local.containers)
  name                  = each.value
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

resource "azurerm_storage_container_immutability_policy" "audit" {
  storage_container_resource_manager_id = azurerm_storage_container.this["audit-logs"].id
  immutability_period_in_days           = var.audit_log_retention_days
  protected_append_writes_enabled       = true
  # Left unlocked so retention can be tuned before go-live; lock it after the DPDP retention schedule is signed off.
  locked = false
}

resource "azurerm_storage_management_policy" "this" {
  storage_account_id = azurerm_storage_account.this.id

  rule {
    name    = "exports-expire"
    enabled = true
    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["exports/"]
    }
    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = 30
      }
    }
  }

  rule {
    name    = "documents-cool-tier"
    enabled = true
    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["uploads/", "documents/", "invoices/"]
    }
    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than = 90
      }
      version {
        delete_after_days_since_creation = 365
      }
    }
  }
}

module "private_endpoint" {
  source               = "../private_endpoint"
  name                 = "pe-${var.name}-blob"
  location             = var.location
  resource_group_name  = var.resource_group_name
  subnet_id            = var.private_endpoint_subnet_id
  target_resource_id   = azurerm_storage_account.this.id
  subresource_names    = ["blob"]
  private_dns_zone_ids = [var.private_dns_zone_id]
  tags                 = var.tags
}

resource "azurerm_security_center_storage_defender" "this" {
  count                                       = var.enable_malware_scanning ? 1 : 0
  storage_account_id                          = azurerm_storage_account.this.id
  malware_scanning_on_upload_enabled          = true
  malware_scanning_on_upload_cap_gb_per_month = 50
  sensitive_data_discovery_enabled            = true
}

resource "azurerm_monitor_diagnostic_setting" "blob" {
  name                       = "diag-to-log-analytics"
  target_resource_id         = "${azurerm_storage_account.this.id}/blobServices/default"
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "audit"
  }
}

output "id" {
  value = azurerm_storage_account.this.id
}
output "blob_endpoint" {
  value = azurerm_storage_account.this.primary_blob_endpoint
}
