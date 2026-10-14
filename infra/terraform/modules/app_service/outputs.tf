output "api_fqdn" {
  value = azurerm_linux_web_app.api.default_hostname
}
output "api_name" {
  value = azurerm_linux_web_app.api.name
}
