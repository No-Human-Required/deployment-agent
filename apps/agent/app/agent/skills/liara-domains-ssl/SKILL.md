---
name: liara-domains-ssl
description: Default liara.run subdomain, attaching custom domains, DNS records and SSL states on Liara.
---

# Domains and SSL

- Every app gets `https://<app-name>.liara.run` with SSL. Use it for verification.
- Custom domain flow: create domain on the app, point DNS (CNAME to the given
  target or A record), then provision SSL. SSL is issued only after DNS resolves.
- Domain and DNS changes require the user's approval (the run pauses for it).
- `certificatesStatus` other than `ACTIVE` usually means DNS not propagated yet;
  wait, do not loop.
- Docs: docs.liara.ir/llms/paas/domains/*.md and /dns-management-system/*.
