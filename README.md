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

## Discovery (Phase 2)
Devices page -> **Scan network**. Read-only: nudges each host on your subnet so the OS learns its MAC, then reads the OS ARP table (no admin rights, no sniffing).
New MACs enter as `Unknown`; nothing is auto-approved. Approve/Block currently record state only - real enforcement needs a router/firewall provider (Phase 5).
Vendor names: drop the IEEE list (https://standards-oui.ieee.org/oui/oui.csv) into `landar/data/oui.csv`. Randomized (private) MACs are flagged.
Limits: guest/isolated Wi-Fi may hide other clients; a scan sees only devices on your own subnet. Only scan networks you own or administer.

## Roadmap
Phase 2 discovery/topology · 3 RADIUS · 4 policies/VLANs · 5 firewall · 6 monitoring · 7-8 see spec.
