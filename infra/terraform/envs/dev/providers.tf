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
      prevent_deletion_if_contains_resources = true
    }
  }
}

# Credentials from MONGODB_ATLAS_CLIENT_ID / MONGODB_ATLAS_CLIENT_SECRET (service account)
# or MONGODB_ATLAS_PUBLIC_KEY / MONGODB_ATLAS_PRIVATE_KEY. Never put them in tfvars.
provider "mongodbatlas" {}
