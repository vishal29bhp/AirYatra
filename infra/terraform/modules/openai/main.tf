# Azure OpenAI replaces emergentintegrations/LlmChat behind the existing ai_service interface.
# Keyless: the app calls it with its managed identity (Cognitive Services OpenAI User).

variable "name" {
  type = string
}
variable "location" {
  description = "Azure OpenAI region with the needed model. India regions first (S.4 data residency)."
  type        = string
}
variable "vnet_location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "deployments" {
  description = "Model deployments keyed by deployment name."
  type = map(object({
    model_name    = string
    model_version = string
    sku_name      = string
    capacity      = number
  }))
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

resource "azurerm_cognitive_account" "this" {
  #checkov:skip=CKV_AZURE_247:outbound_network_access_restricted = true with no allowed FQDNs is set below; Checkov does not read it.
  #checkov:skip=CKV2_AZURE_22:Microsoft-managed keys; no KYC or payment data is ever sent to the model (S.3 AI features).
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = var.name
  local_auth_enabled            = false
  public_network_access_enabled = false
  # The model cannot be pointed at outside URLs (data loss prevention).
  outbound_network_access_restricted = true
  fqdns                              = []
  tags                               = var.tags

  identity {
    type = "SystemAssigned"
  }

  network_acls {
    default_action = "Deny"
  }
}

resource "azurerm_cognitive_deployment" "this" {
  for_each             = var.deployments
  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.this.id

  model {
    format  = "OpenAI"
    name    = each.value.model_name
    version = each.value.model_version
  }

  sku {
    name     = each.value.sku_name
    capacity = each.value.capacity
  }
}

module "private_endpoint" {
  source               = "../private_endpoint"
  name                 = "pe-${var.name}"
  location             = var.vnet_location
  resource_group_name  = var.resource_group_name
  subnet_id            = var.private_endpoint_subnet_id
  target_resource_id   = azurerm_cognitive_account.this.id
  subresource_names    = ["account"]
  private_dns_zone_ids = [var.private_dns_zone_id]
  tags                 = var.tags
}

output "id" {
  value = azurerm_cognitive_account.this.id
}
output "endpoint" {
  value = azurerm_cognitive_account.this.endpoint
}
