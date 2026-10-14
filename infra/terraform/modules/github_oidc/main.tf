# Lets GitHub Actions deploy with short-lived OIDC tokens: no long-lived Azure secret in GitHub (S.2 A08).

variable "name_prefix" {
  type = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "resource_group_id" {
  type = string
}
variable "github_repository" {
  description = "owner/repo, e.g. vishal29bhp/AirYatra."
  type        = string
}
variable "github_repository_immutable" {
  description = <<-EOT
    owner@owner_id/repo@repo_id. Repositories that use GitHub's immutable OIDC subject claims send
    "repo:owner@id/repo@id:environment:<env>" instead of "repo:owner/repo:environment:<env>". Null skips it.
  EOT
  type        = string
  default     = null
}
variable "github_environment" {
  description = "GitHub environment whose jobs may assume this identity (protect it with required reviewers for prod)."
  type        = string
}
variable "registry_id" {
  type = string
}
variable "web_storage_account_id" {
  type = string
}
variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_user_assigned_identity" "this" {
  name                = "id-${var.name_prefix}-github"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "environment" {
  name                      = "github-${var.github_environment}"
  user_assigned_identity_id = azurerm_user_assigned_identity.this.id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "repo:${var.github_repository}:environment:${var.github_environment}"
}

resource "azurerm_federated_identity_credential" "environment_immutable" {
  count                     = var.github_repository_immutable == null ? 0 : 1
  name                      = "github-${var.github_environment}-immutable"
  user_assigned_identity_id = azurerm_user_assigned_identity.this.id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "repo:${var.github_repository_immutable}:environment:${var.github_environment}"
}

resource "azurerm_role_assignment" "acr_push" {
  scope                = var.registry_id
  role_definition_name = "AcrPush"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "web_upload" {
  scope                = var.web_storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
  principal_type       = "ServicePrincipal"
}

# Rolls new container images. Scoped to this environment's resource group only.
resource "azurerm_role_assignment" "deployer" {
  scope                = var.resource_group_id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
  principal_type       = "ServicePrincipal"
}

output "client_id" {
  description = "Set as AZURE_CLIENT_ID in the GitHub environment."
  value       = azurerm_user_assigned_identity.this.client_id
}
