resource "cloudflare_record" "tunnel" {
  for_each = toset(var.subdomains)
  
  zone_id = data.cloudflare_zone.main.id
  name = each.value
  content = "${var.tunnel_id}.cfargotunnel.com"
  type = "CNAME"
  proxied = true
  ttl = 1
}
