locals {
  # /23 for the Container Apps environment (workload-profile environments need >= /27,
  # a /23 leaves headroom for 20K-user scale), /24 for private endpoints.
  aca_subnet_cidr = cidrsubnet(var.address_space, 7, 0) # x.x.0.0/23
  pe_subnet_cidr  = cidrsubnet(var.address_space, 8, 2) # x.x.2.0/24

  private_dns_zones = {
    blob     = "privatelink.blob.core.windows.net"
    keyvault = "privatelink.vaultcore.azure.net"
    redis    = "privatelink.redis.azure.net"
    openai   = "privatelink.openai.azure.com"
    mongo    = "privatelink.mongocluster.cosmos.azure.com"
  }
}

resource "azurerm_virtual_network" "this" {
  name                = "vnet-${var.name_prefix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = [var.address_space]
  tags                = var.tags
}

resource "azurerm_subnet" "aca" {
  name                 = "snet-aca"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [local.aca_subnet_cidr]

  delegation {
    name = "aca"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# Container Apps manages its own load balancer rules; the NSG keeps the platform defaults and
# is the place to add egress restrictions to integration hosts (S.2 A10).
resource "azurerm_network_security_group" "aca" {
  name                = "nsg-${var.name_prefix}-aca"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_subnet_network_security_group_association" "aca" {
  subnet_id                 = azurerm_subnet.aca.id
  network_security_group_id = azurerm_network_security_group.aca.id
}

resource "azurerm_subnet" "private_endpoints" {
  name                              = "snet-private-endpoints"
  resource_group_name               = var.resource_group_name
  virtual_network_name              = azurerm_virtual_network.this.name
  address_prefixes                  = [local.pe_subnet_cidr]
  private_endpoint_network_policies = "Enabled"
}

# Least-privilege NSG for the private endpoint subnet: only the app subnet may reach data services.
resource "azurerm_network_security_group" "private_endpoints" {
  name                = "nsg-${var.name_prefix}-pe"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags

  security_rule {
    name                       = "allow-aca-to-data"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = local.aca_subnet_cidr
    source_port_range          = "*"
    destination_address_prefix = local.pe_subnet_cidr
    # Blob/Key Vault/OpenAI use 443, Managed Redis 10000, Atlas Private Link maps one port per node.
    destination_port_range = "*"
  }

  security_rule {
    name                       = "deny-other-vnet-inbound"
    priority                   = 4000
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_address_prefix      = "VirtualNetwork"
    source_port_range          = "*"
    destination_address_prefix = "*"
    destination_port_range     = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "private_endpoints" {
  subnet_id                 = azurerm_subnet.private_endpoints.id
  network_security_group_id = azurerm_network_security_group.private_endpoints.id
}

resource "azurerm_private_dns_zone" "this" {
  for_each            = local.private_dns_zones
  name                = each.value
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "this" {
  for_each              = local.private_dns_zones
  name                  = "link-${each.key}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.this[each.key].name
  virtual_network_id    = azurerm_virtual_network.this.id
  registration_enabled  = false
  tags                  = var.tags
}
