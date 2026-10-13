variable "name" {
  description = "Key Vault name (3-24 chars, globally unique)."
  type        = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "tenant_id" {
  type = string
}
variable "deployer_ip_cidrs" {
  description = "Public IPs allowed through the Key Vault firewall so Terraform can write secrets. Empty = private endpoint only."
  type        = list(string)
  default     = []
}
variable "private_endpoint_subnet_id" {
  type = string
}
variable "private_dns_zone_id" {
  type = string
}
variable "log_analytics_workspace_id" {
  type = string
}
variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_key_vault" "this" {
  #checkov:skip=CKV_AZURE_189:Public endpoint is on only when deployer_ip_cidrs is set, and then only for those IPs; apps use the private endpoint.
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 90
  public_network_access_enabled = length(var.deployer_ip_cidrs) > 0
  tags                          = var.tags

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    ip_rules       = var.deployer_ip_cidrs
  }
}

module "private_endpoint" {
  source               = "../private_endpoint"
  name                 = "pe-${var.name}"
  location             = var.location
  resource_group_name  = var.resource_group_name
  subnet_id            = var.private_endpoint_subnet_id
  target_resource_id   = azurerm_key_vault.this.id
  subresource_names    = ["vault"]
  private_dns_zone_ids = [var.private_dns_zone_id]
  tags                 = var.tags
}

# Audit every secret read (S.2 A09).
resource "azurerm_monitor_diagnostic_setting" "this" {
  name                       = "diag-to-log-analytics"
  target_resource_id         = azurerm_key_vault.this.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category_group = "audit"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

output "id" {
  value = azurerm_key_vault.this.id
}
output "uri" {
  value = azurerm_key_vault.this.vault_uri
}
