# One-time: creates the storage account that holds Terraform state for every AirYatra environment.
# Run with local state, then keep its terraform.tfstate somewhere safe (it only holds these three resources).

terraform {
  required_version = ">= 1.9.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.81"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
  }
}

variable "subscription_id" {
  type = string
}
variable "location" {
  type    = string
  default = "centralindia"
}

provider "azurerm" {
  subscription_id     = var.subscription_id
  storage_use_azuread = true
  features {}
}

data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 4
  upper   = false
  special = false
}

resource "azurerm_resource_group" "state" {
  name     = "rg-airyatra-tfstate-cin"
  location = var.location
  tags = {
    application = "AirYatra"
    purpose     = "terraform-state"
  }
}

resource "azurerm_storage_account" "state" {
  #checkov:skip=CKV2_AZURE_1:State is protected by Entra RBAC, versioning and soft delete; CMK not needed.
  #checkov:skip=CKV2_AZURE_33:Reached from operator laptops and CI runners; protected by Entra-only auth.
  #checkov:skip=CKV_AZURE_59:Same as above; no anonymous access is possible (shared keys and public blobs off).
  #checkov:skip=CKV_AZURE_33:Queue service is not used.
  #checkov:skip=CKV2_AZURE_21:Low-volume account; Entra sign-in logs cover access.
  #checkov:skip=CKV_AZURE_206:GRS is used.
  name                            = "stairyatratfstate${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.state.name
  location                        = azurerm_resource_group.state.location
  account_tier                    = "Standard"
  account_replication_type        = "GRS"
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = false
  tags                            = azurerm_resource_group.state.tags

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
    container_delete_retention_policy {
      days = 30
    }
  }
}

resource "azurerm_storage_container" "state" {
  #checkov:skip=CKV2_AZURE_21:See storage account.
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
}

# The person running bootstrap can read/write state with Entra auth.
resource "azurerm_role_assignment" "state_owner" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

output "backend_config" {
  value = <<-EOT
    resource_group_name  = "${azurerm_resource_group.state.name}"
    storage_account_name = "${azurerm_storage_account.state.name}"
    container_name       = "tfstate"
  EOT
}
