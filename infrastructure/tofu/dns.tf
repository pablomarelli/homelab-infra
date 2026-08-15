resource "cloudflare_record" "tunnel" {
  for_each = toset(var.subdomains)

  zone_id = data.cloudflare_zone.main.id
  name    = each.value
  content = "${var.tunnel_id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
  ttl     = 1

  timeouts {
    create = "5m"
    update = "5m"
  }
}

moved {
  from = cloudflare_record.tunnel["dotfiles"]
  to   = cloudflare_record.dotfiles_redirect
}

resource "cloudflare_record" "dotfiles_redirect" {
  zone_id = data.cloudflare_zone.main.id
  name    = "dotfiles"
  content = "192.0.2.1"
  type    = "A"
  proxied = true
  ttl     = 1
}

resource "cloudflare_ruleset" "dotfiles_redirect" {
  zone_id     = data.cloudflare_zone.main.id
  name        = "Dotfiles installer redirect"
  description = "Redirect the public dotfiles bootstrap URL to the installer source"
  kind        = "zone"
  phase       = "http_request_dynamic_redirect"

  rules {
    action      = "redirect"
    expression  = "(http.host eq \"dotfiles.${var.domain}\" and http.request.uri.path eq \"/\")"
    description = "Redirect dotfiles bootstrap requests"
    enabled     = true

    action_parameters {
      from_value {
        status_code           = 302
        preserve_query_string = false

        target_url {
          value = "https://raw.githubusercontent.com/pablomarelli/dotfiles/main/install.sh"
        }
      }
    }
  }
}
