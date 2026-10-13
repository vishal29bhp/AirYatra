output "endpoint_host_name" {
  value = azurerm_cdn_frontdoor_endpoint.this.host_name
}
output "profile_id" {
  value = azurerm_cdn_frontdoor_profile.this.id
}
output "web_storage_account_id" {
  value = azurerm_storage_account.web.id
}
output "web_storage_account_name" {
  value = azurerm_storage_account.web.name
}
output "custom_domain_validation_tokens" {
  description = "Create TXT records _dnsauth.<host> with these values to validate custom domains."
  value       = { for k, d in azurerm_cdn_frontdoor_custom_domain.this : k => d.validation_token }
}
output "profile_resource_guid" {
  description = "Sent by Front Door as X-Azure-FDID; the API trusts X-Azure-ClientIP only when it matches."
  value       = azurerm_cdn_frontdoor_profile.this.resource_guid
}
output "profile_name" {
  value = azurerm_cdn_frontdoor_profile.this.name
}
output "endpoint_name" {
  value = azurerm_cdn_frontdoor_endpoint.this.name
}
