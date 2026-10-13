output "environment_id" {
  value = azurerm_container_app_environment.this.id
}
output "environment_location" {
  value = azurerm_container_app_environment.this.location
}
output "api_fqdn" {
  value = azurerm_container_app.api.ingress[0].fqdn
}
output "api_name" {
  value = azurerm_container_app.api.name
}
output "worker_name" {
  value = azurerm_container_app.worker.name
}
output "registry_id" {
  value = azurerm_container_registry.this.id
}
output "registry_login_server" {
  value = azurerm_container_registry.this.login_server
}
