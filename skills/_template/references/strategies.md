# Strategies (template)

Copy the platform-neutral rules from
`skills/bilibili/references/strategies.md` and add platform-specific notes:

- **Endpoints per request kind** and the Safe/Balanced/Fast interval table for
  this platform.
- **Extra error codes** and how they map to `risk_control` / `transient` /
  `wbi_stale` / `auth_expired` / `not_found` / `protocol`.
- **Multi-part rules**: what is scoped to the parent item and what is scoped to
  a part (for Bilibili: comments per video, danmaku per part).
- **Completeness accounting**: which total the platform reports and what it
  includes.
