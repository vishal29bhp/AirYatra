terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.81"
    }
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 2.19"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
  }

  # State lives in the storage account created by ../../bootstrap. Values come from backend.hcl
  # (terraform init -backend-config=backend.hcl) so no account names are hard-coded here.
  backend "azurerm" {
    use_azuread_auth = true
  }
}

provider "azurerm" {
  subscription_id     = var.subscription_id
  storage_use_azuread = true

  features {
    key_vault {
      purge_soft_delete_on_destroy = false
    }
    resource_group {
      # Dev only: Azure adds resources Terraform does not track (such as Application Insights smart detection
      # rules), which would otherwise block removing a dev resource group. Prod keeps this true.
      prevent_deletion_if_contains_resources = false
    }
  }
}

# Credentials from MONGODB_ATLAS_CLIENT_ID / MONGODB_ATLAS_CLIENT_SECRET (service account)
# or MONGODB_ATLAS_PUBLIC_KEY / MONGODB_ATLAS_PRIVATE_KEY. Never put them in tfvars.
# On Cosmos DB the provider manages nothing, but it still refuses to start without credentials, so it gets inert
# placeholders that are never sent anywhere.
provider "mongodbatlas" {
  public_key  = var.database_engine == "atlas" ? null : "unused"
  private_key = var.database_engine == "atlas" ? null : "unused"
}
