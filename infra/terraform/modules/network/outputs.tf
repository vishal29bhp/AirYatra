output "vnet_id" {
  value = azurerm_virtual_network.this.id
}
output "aca_subnet_id" {
  value = azurerm_subnet.aca.id
}
output "private_endpoint_subnet_id" {
  value = azurerm_subnet.private_endpoints.id
}
output "private_dns_zone_ids" {
  description = "Map of zone key (blob, keyvault, redis, openai) to private DNS zone id."
  value       = { for k, z in azurerm_private_dns_zone.this : k => z.id }
}
