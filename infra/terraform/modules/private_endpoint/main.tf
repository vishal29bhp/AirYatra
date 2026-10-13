# Private endpoint for one Azure PaaS resource, registered in its private DNS zone.
variable "name" {
  type = string
}
variable "location" {
  type = string
}
variable "resource_group_name" {
  type = string
}
variable "subnet_id" {
  type = string
}
variable "target_resource_id" {
  type = string
}
variable "subresource_names" {
  type = list(string)
}
variable "private_dns_zone_ids" {
  type = list(string)
}
variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_private_endpoint" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "${var.name}-psc"
    private_connection_resource_id = var.target_resource_id
    subresource_names              = var.subresource_names
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = var.private_dns_zone_ids
  }
}

output "id" {
  value = azurerm_private_endpoint.this.id
}

output "private_ip_address" {
  value = azurerm_private_endpoint.this.private_service_connection[0].private_ip_address
}
