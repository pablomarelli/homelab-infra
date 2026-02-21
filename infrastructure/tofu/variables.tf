variable "cloudflare_api_token" {
  description = "Cloudflare API token with DNS edit permissions"
  type = string
  sensitive = true
}

variable "domain" {
  description = "Root domain"
  type = string
  default = "pablomarelli.dev"
}

variable "tunnel_id" {
  description = "Cloudflare Tunnel ID"
  type = string
  default = "e9185fce-e694-4220-8baa-97d40d84df61"
}

variable "subdomains" {
  description = "Subdomains to route through the tunnel"
  type = list(string)
  default = ["argocd", "portfolio", "finance", "home"]
}
