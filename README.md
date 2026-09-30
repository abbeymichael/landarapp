# LANDAR — Network Control & Management Platform (Phase 1)

    pip install -r requirements.txt
    python run.py            # or: python -m landar
    python -m unittest discover tests

First run creates `admin` with a random password (shown once). Data lives in `~/.landar/landar.db` (override with `LANDAR_HOME` / `LANDAR_DB`).

## Layout & rules
    landar/
      config.py        settings
      storage.py       SQLite + MIGRATIONS (append-only; add a new string for each schema change)
      core/            pure logic, no DB/UI: permissions (RBAC), security (hashing), constants
      services/        ALL business logic. Every function: require(actor, perm) -> do work -> audit.record()
      providers/       vendor/auth abstractions (base.py) + registry.py. Add RADIUS/OPNsense here
      ui/              PySide6 only. Pages call services, never SQL. registry.py lists screens
    tests/             service-level tests (no GUI needed)

**Dependency direction:** ui -> services -> (core, storage, providers). Never the reverse.

## Adding a feature (e.g. Firewall)
1. Migration: append SQL to `storage.MIGRATIONS`.
2. Permissions: add `firewall.view` / `firewall.edit` to `core/permissions.py`.
3. Service: `services/firewall.py` (guard + audit on every call) + tests.
4. Provider: interface in `providers/base.py`, implementation e.g. `providers/opnsense.py`, list in `registry.py`.
5. Page: `ui/pages/firewall.py` (subclass `TablePage`), add one `PageSpec` line to `ui/registry.py`.

## UI design system
Matches the supplied HTML design (`code.html`). Tokens live in `ui/theme.py` (colors copied from its Tailwind config); fonts (Inter, JetBrains Mono,
Material Symbols subset) are bundled in `assets/fonts` so it looks the same everywhere. Reusable pieces: `ui/components.py` (caps labels, chips, KPI cards, section cards).
Sidebar sections/icons come from `ui/registry.py`. Unbuilt modules show a placeholder page. Qt gotcha: never `setStyleSheet("background:...")` without a selector - it cascades to every child.

## Discovery (Phase 2)
Devices page -> **Scan network**. Read-only: nudges each host on your subnet so the OS learns its MAC, then reads the OS ARP table (no admin rights, no sniffing).
New MACs enter as `Unknown`; nothing is auto-approved. Approve/Block currently record state only - real enforcement needs a router/firewall provider (Phase 5).
Vendor names: drop the IEEE list (https://standards-oui.ieee.org/oui/oui.csv) into `landar/data/oui.csv`. Randomized (private) MACs are flagged.
Limits: guest/isolated Wi-Fi may hide other clients; a scan sees only devices on your own subnet. Only scan networks you own or administer.

## Topology (Phase 2)
`services/topology.py` builds a pure-data graph (internet -> default gateway -> LAN segment -> hosts) from the device inventory; `ui/pages/topology.py` draws it
(drag to pan, wheel to zoom, click a node for details, set device type, approve/block). Gateway comes from the OS routing table. Without LLDP/SNMP we cannot
see switches/APs or cabling, so the map shows only what discovery can prove. Switch/AP/VLAN views arrive with those providers.

## Networks, DHCP & DNS
`services/networks.py` (VLAN/subnet plan: validated, overlap-checked, device counts), `services/dhcp.py` (scopes, reservations, conflict detection, observed addresses),
`services/dns.py` + `core/dnswire.py` (local records, forwarders, live resolver tests over raw UDP), `services/export.py` (dnsmasq config file).
This is managed configuration: it is stored, validated and audited, and can be exported, but nothing is pushed to a router/switch until a provider exists (Phase 5/7).
"Observed addresses" come from scans, not from a real lease table. New permission: `network.configure`.

## Roadmap
Phase 2 discovery/topology · 3 RADIUS · 4 policies/VLANs · 5 firewall · 6 monitoring · 7-8 see spec.
