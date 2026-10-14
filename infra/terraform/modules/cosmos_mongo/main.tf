# Azure Cosmos DB for MongoDB (vCore): the database option Terraform can create with nothing but the Azure
# subscription. Same wire protocol as MongoDB, so the app, schema and data are unchanged. Reached only through a
# private endpoint; the connection string goes to Key Vault.

variable "name" {
  type = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "compute_tier" {
  description = "M10/M20 are burstable (dev); M30 and up for production load."
  type        = string
  default     = "M10"
}
variable "storage_size_in_gb" {
  type    = number
  default = 32
}
variable "high_availability_enabled" {
  description = "Zone-redundant standby. Not available on the burstable M10/M20 tiers."
  type        = bool
  default     = false
}
variable "mongo_version" {
  type    = string
  default = "7.0"
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

locals {
  # Azure only accepts Latin letters and digits here.
  admin_username = "airyatraapp"
}

# Letters and digits only, so the password needs no escaping inside the connection string.
resource "random_password" "admin" {
  length  = 40
  special = false
}

resource "azurerm_mongo_cluster" "this" {
  name                   = var.name
  location               = var.location
  resource_group_name    = var.resource_group_name
  administrator_username = local.admin_username
  administrator_password = random_password.admin.result
  compute_tier           = var.compute_tier
  storage_size_in_gb     = var.storage_size_in_gb
  shard_count            = 1
  high_availability_mode = var.high_availability_enabled ? "ZoneRedundantPreferred" : "Disabled"
  version                = var.mongo_version
  public_network_access  = "Disabled"
  tags                   = var.tags

  lifecycle {
    ignore_changes = [administrator_password]
  }
}

module "private_endpoint" {
  source               = "../private_endpoint"
  name                 = "pe-${var.name}"
  location             = var.location
  resource_group_name  = var.resource_group_name
  subnet_id            = var.private_endpoint_subnet_id
  target_resource_id   = azurerm_mongo_cluster.this.id
  subresource_names    = ["MongoCluster"]
  private_dns_zone_ids = [var.private_dns_zone_id]
  tags                 = var.tags
}

output "id" {
  value = azurerm_mongo_cluster.this.id
}

output "connection_uri" {
  description = "Full MONGO_URL with credentials; written to Key Vault, never to app settings."
  # vCore has no retryable writes, so the driver default (retryWrites=true) must be turned off.
  value     = "mongodb+srv://${local.admin_username}:${random_password.admin.result}@${azurerm_mongo_cluster.this.name}.global.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
  sensitive = true
}
