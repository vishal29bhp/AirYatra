output "environment_id" {
  value = var.environment_enabled ? azurerm_container_app_environment.this[0].id : null
}
output "environment_location" {
  value = var.environment_enabled ? azurerm_container_app_environment.this[0].location : null
}
output "api_fqdn" {
  value = var.environment_enabled ? azurerm_container_app.api[0].ingress[0].fqdn : null
}
output "api_name" {
  value = var.environment_enabled ? azurerm_container_app.api[0].name : null
}
output "worker_name" {
  value = var.environment_enabled ? azurerm_container_app.worker[0].name : null
}
output "registry_id" {
  value = azurerm_container_registry.this.id
}
output "registry_login_server" {
  value = azurerm_container_registry.this.login_server
}
