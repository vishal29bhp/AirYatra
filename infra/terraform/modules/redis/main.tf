# Azure Managed Redis (successor to Azure Cache for Redis): rate-limit counters, login lockout state,
# response cache and the WebSocket pub/sub backplane shared by every API replica.

variable "name" {
  type = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "sku_name" {
  description = "Balanced_B0 for dev, Balanced_B1 at 1K users, Balanced_B3/B5 at 20K users."
  type        = string
}
variable "high_availability_enabled" {
  type = bool
}
variable "private_endpoint_subnet_id" {
  type = string
}
variable "private_dns_zone_id" {
  type = string
}
variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_managed_redis" "this" {
  name                      = var.name
  location                  = var.location
  resource_group_name       = var.resource_group_name
  sku_name                  = var.sku_name
  high_availability_enabled = var.high_availability_enabled
  public_network_access     = "Disabled"
  tags                      = var.tags

  default_database {
    # Entra ID (managed identity) auth only; no access keys.
    access_keys_authentication_enabled = false
    client_protocol                    = "Encrypted"
    clustering_policy                  = "EnterpriseCluster"
    eviction_policy                    = "VolatileLRU"
  }
}

module "private_endpoint" {
  source               = "../private_endpoint"
  name                 = "pe-${var.name}"
  location             = var.location
  resource_group_name  = var.resource_group_name
  subnet_id            = var.private_endpoint_subnet_id
  target_resource_id   = azurerm_managed_redis.this.id
  subresource_names    = ["redisEnterprise"]
  private_dns_zone_ids = [var.private_dns_zone_id]
  tags                 = var.tags
}

output "id" {
  value = azurerm_managed_redis.this.id
}
output "hostname" {
  value = azurerm_managed_redis.this.hostname
}

variable "data_access_object_ids" {
  description = "Entra object ids (managed identities) granted data access to the default database."
  type        = map(string)
  default     = {}
}

resource "azurerm_managed_redis_access_policy_assignment" "this" {
  for_each         = var.data_access_object_ids
  managed_redis_id = azurerm_managed_redis.this.id
  object_id        = each.value
}
