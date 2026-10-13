output "resource_group_name" {
  value = azurerm_resource_group.this.name
}
output "public_url" {
  value = local.public_url
}
output "frontdoor_endpoint" {
  value = module.frontdoor.endpoint_host_name
}
output "api_internal_fqdn" {
  value = module.container_apps.api_fqdn
}
output "api_container_app_name" {
  value = module.container_apps.api_name
}
output "worker_container_app_name" {
  value = module.container_apps.worker_name
}
output "registry_login_server" {
  value = module.container_apps.registry_login_server
}
output "web_storage_account_name" {
  value = module.frontdoor.web_storage_account_name
}
output "data_storage_account_name" {
  value = module.storage.name
}
output "key_vault_uri" {
  value = module.keyvault.uri
}
output "github_actions_client_id" {
  description = "Put in the GitHub environment as AZURE_CLIENT_ID."
  value       = module.github_oidc.client_id
}
output "custom_domain_validation_tokens" {
  value = module.frontdoor.custom_domain_validation_tokens
}
output "atlas_project_id" {
  value = module.mongodb.project_id
}
output "github_actions_variables" {
  description = "Variables for this GitHub environment, used by .github/workflows/azure-deploy.yml (none are secrets)."
  value = {
    AZURE_CLIENT_ID       = module.github_oidc.client_id
    AZURE_TENANT_ID       = data.azurerm_client_config.current.tenant_id
    AZURE_SUBSCRIPTION_ID = data.azurerm_client_config.current.subscription_id
    AZURE_RESOURCE_GROUP  = azurerm_resource_group.this.name
    ACR_LOGIN_SERVER      = module.container_apps.registry_login_server
    API_APP_NAME          = module.container_apps.api_name
    WORKER_APP_NAME       = module.container_apps.worker_name
    WEB_STORAGE_ACCOUNT   = module.frontdoor.web_storage_account_name
    FRONTDOOR_PROFILE     = module.frontdoor.profile_name
    FRONTDOOR_ENDPOINT    = module.frontdoor.endpoint_name
    PUBLIC_URL            = local.public_url
  }
}
