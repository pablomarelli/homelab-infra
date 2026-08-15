# Roadmap

This roadmap tracks direction rather than detailed implementation. Actionable work
belongs in GitHub Issues and should be linked from here when useful.

## Now

- Complete and validate the public dotfiles bootstrap rollout.
- Add availability monitoring for `dotfiles.pablomarelli.dev`.
- Protect the `main` branch with required validation checks.

## Next

- Regularly test backup restoration procedures.
- Improve infrastructure health checks and alerting.
- Document disaster recovery procedures.
- Configure Forgejo repositories to use SSH for Git operations.

## Later

- Automate node provisioning and rebuilds.
- Evaluate high-availability options where they provide practical value.

## Completed

- Migrate OpenTofu remote state to Cloudflare R2.
- Inject OpenTofu and Cloudflare credentials through 1Password.

## Versioning

Known-good infrastructure checkpoints use calendar tags such as `2026.08`.
Create a tag only after the configuration has been deployed and validated. Git
history remains the detailed changelog; GitHub Releases are optional summaries
for significant checkpoints.
