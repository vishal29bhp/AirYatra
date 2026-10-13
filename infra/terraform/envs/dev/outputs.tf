output "resource_group_name" {
  value = module.platform.resource_group_name
}
output "public_url" {
  value = module.platform.public_url
}
output "frontdoor_endpoint" {
  value = module.platform.frontdoor_endpoint
}
output "api_container_app_name" {
  value = module.platform.api_container_app_name
}
output "worker_container_app_name" {
  value = module.platform.worker_container_app_name
}
output "registry_login_server" {
  value = module.platform.registry_login_server
}
output "web_storage_account_name" {
  value = module.platform.web_storage_account_name
}
output "data_storage_account_name" {
  value = module.platform.data_storage_account_name
}
output "key_vault_uri" {
  value = module.platform.key_vault_uri
}
output "github_actions_client_id" {
  value = module.platform.github_actions_client_id
}
output "custom_domain_validation_tokens" {
  value = module.platform.custom_domain_validation_tokens
}
