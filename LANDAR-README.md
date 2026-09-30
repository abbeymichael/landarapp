# LANDAR — Network Control & Management Platform

> **Master product/design specification.** Read this fully *before* writing any code.
> Implementation must not begin until the deliverables in [Section 15](#15-required-deliverables-before-coding) are produced and reviewed.

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [Core Concept & Data Flow](#2-core-concept--data-flow)
3. [Design Principles & Security Boundaries](#3-design-principles--security-boundaries)
4. [Modules](#4-modules)
5. [Architecture](#5-architecture)
6. [Policy Engine](#6-policy-engine)
7. [Data Model](#7-data-model)
8. [RBAC, Audit & Credentials](#8-rbac-audit--credentials)
9. [Desktop UI & Navigation](#9-desktop-ui--navigation)
10. [Deployment Sizes](#10-deployment-sizes)
11. [Example: School Network](#11-example-school-network)
12. [Development Phases](#12-development-phases)
13. [Critical Architectural Requirement](#13-critical-architectural-requirement)
14. [Product Goal](#14-product-goal)
15. [Required Deliverables Before Coding](#15-required-deliverables-before-coding)

---

## 1. Product Vision

LANDAR is a professional **centralized control plane** for network access and management. It is **not** just a LAN scanner or monitoring dashboard.

**Target environments:** homes, schools, universities, offices, small businesses, hotels, community networks, managed Wi-Fi.

**Control plane responsibilities:**

1. Network access
2. User authentication
3. Device management
4. Network policies
5. Firewall management
6. Bandwidth / rate limiting
7. VLAN / segmentation
8. DHCP / DNS / network services
9. Monitoring
10. Alerts
11. Reporting
12. Administrative auditing

The desktop app gives authorized administrators one interface to configure, manage, monitor and troubleshoot. The architecture **must be modular** so new network technologies and hardware can be added later.

---

## 2. Core Concept & Data Flow

```
PERSON
   ├── Account
   ├── Devices
   └── Groups/Roles
          │
          ▼
       POLICIES
     ┌────┼─────────┐
     ▼    ▼         ▼
   AUTH FIREWALL   QOS
     └────┼─────────┘
          ▼
       NETWORK
      ┌───┴────┐
      ▼        ▼
     LAN    INTERNET
```

**The system must answer:**

- Who is connected? Which device are they using? Are they authorized?
- What network should they enter? What can they access?
- How much bandwidth can they use? When can they access the network?
- What traffic is blocked/allowed?
- What is happening now? What happened previously? Who changed the configuration?

---

## 3. Design Principles & Security Boundaries

### Priorities (in order)

1. Security 2. Reliability 3. Clear administration 4. Least privilege 5. Auditability
6. Modularity 7. Vendor independence 8. Good UX 9. Safe defaults 10. Scalability

- Never hide important network behavior from the administrator.
- Dangerous/disruptive operations **require confirmation**.

### Security boundaries

The system must distinguish four levels — **discovery does not grant control**:

```
DISCOVERY → MONITORING → CONFIGURATION → CONTROL
```

### The application MUST NOT

- Capture credentials from network traffic
- Perform unauthorized interception
- Bypass authentication or circumvent network security
- Access devices without authorization
- Expose stored secrets unnecessarily

All administrative operations must be **authenticated and audited**. Only authorized integrations and administrators may modify infrastructure.

---

## 4. Modules

### 4.1 Dashboard

Real-time overview: internet status, gateway status, connected users/devices, bandwidth, auth activity, firewall activity, alerts, network health, offline/unknown devices, active sessions.

```
NETWORK STATUS
Internet       ONLINE          Authentication failures     31
Gateway        ONLINE          Firewall blocks         12,481
Users          482             Unknown devices              4
Devices        637             Active alerts                7
Bandwidth      2.4 Gbps
```

### 4.2 User Management

Users are first-class objects. **Types:** students, teachers, staff, administrators, guests, family members, contractors, custom.

```
User
├── ID, Name, Username, Password credential
├── Email, Phone, Department
├── Group, Role
├── Account status, Expiration
├── Assigned devices
├── Network policies, Bandwidth policy, Access schedule
└── Audit history
```

**Account states:** `Active` · `Disabled` · `Suspended` · `Expired` · `Pending` · `Locked`

### 4.3 Authentication

Design the auth layer **independently from the UI**. Do not hard-code one mechanism.

```
AuthenticationProvider
├── Local
├── RADIUS (802.1X)
├── LDAP
├── Active Directory
└── External Provider / IdP
```

**Record:** login, logout, auth failure, account lockout, session start/end, authentication source.
**Never store passwords in plaintext.**

### 4.4 Device Management

```
Device
├── Device ID, Hostname, IP, MAC
├── Manufacturer, Device type, OS
├── Owner, First seen, Last seen, Status
├── Network/VLAN, Assigned policies
└── Notes/tags
```

**Categories:** laptop, desktop, phone, tablet, server, printer, router, switch, access point, IoT, camera, unknown.
**Support:** auto discovery, manual registration, approval, blocking, ownership, grouping, history.

### 4.5 Network Discovery

Discover authorized infrastructure and clients: IP, MAC, hostname, DHCP info, interfaces, topology, availability.

**Device states:** `Known` · `Approved` · `Unknown` · `Blocked` · `Offline`
Discovery never implies permission to access or control a device.

### 4.6 Network Topology

Interactive graphical map; clicking a node opens device details.

```
              INTERNET
                  │
              FIREWALL
                  │
               ROUTER
                  │
             CORE SWITCH
        ┌─────────┼─────────┐
      SERVER      AP      SWITCH
                 /  \
          Student    Teacher
            PCs        PCs
```

### 4.7 Network Segmentation

VLANs, subnets, SSIDs, guest/student/teacher/admin/IoT/management networks. Policies govern inter-segment communication.

| VLAN | Purpose |
|------|---------|
| 10 | Administration |
| 20 | Teachers |
| 30 | Students |
| 40 | Guests |
| 50 | IoT |
| 99 | Network Management |

### 4.8 Firewall Management

Visual rule manager. Rule model:

```
SOURCE → DESTINATION → SERVICE/PORT → PROTOCOL → ACTION → LOGGING
```

**Must support:** Allow / Deny / Reject, logging, source & destination network, source user/group (where supported), port, protocol, schedule, priority/order.
**The UI must clearly show rule ordering** (order affects behavior).

```
ALLOW  Students → Internet → HTTPS
DENY   Students → Administration VLAN
ALLOW  Teachers → School LMS
ALLOW  IT Admin → Network Devices → SSH
DENY   Guests   → Internal LAN
```

### 4.9 Bandwidth Management / Rate Limiting

**Targets:** user, device, group, VLAN, network, application/service, time period.

| Role | Download | Upload |
|------|----------|--------|
| Administrator | Unlimited | Unlimited |
| Teacher | 100 Mbps | 50 Mbps |
| Student | 20 Mbps | 5 Mbps |
| Guest | 5 Mbps | 2 Mbps |

**Future QoS:** traffic priority, guaranteed bandwidth, max bandwidth, burst limits, time-based policies, application classes.

### 4.10 Access Scheduling

Time ranges, days of week, dates, holidays, exceptions, group schedules, user overrides.

```
Students   Mon–Fri 08:00–18:00
Guests     Max session: 8 hours
Child      Internet 07:00–21:00
```

### 4.11 Captive Portal (optional)

```
Connect Wi-Fi → Open browser → Portal → Username/password
   → Authentication → Policy assignment → Internet access
```

**Customizable:** org name, logo, terms of service, login fields, guest registration, notices, account recovery.

### 4.12 DHCP Management (where supported)

Scopes, address pools, reservations, leases, static mappings, hostnames, expiration, conflict detection.

```
Network: 192.168.10.0/24   Gateway: 192.168.10.1   DHCP: .50–.200
Reserved: .10 → Server, .20 → Printer
```

### 4.13 DNS Management (where supported)

Configuration, local hostnames, records, forwarders, resolution monitoring, internal names, block/allow policies.

### 4.14 Monitoring

*Important, but not the primary purpose.*

| Area | Metrics |
|------|---------|
| Network | latency, packet loss, bandwidth, interface utilization, internet & gateway availability |
| Devices | online/offline, CPU, RAM, disk, interfaces, services |
| Authentication | successful/failed logins, active sessions, expired accounts |
| Firewall | allowed/blocked traffic, rule activity, abnormal patterns |
| Infrastructure | routers, switches, APs, servers, DHCP, DNS |

### 4.15 Alerts

**Examples:** unknown device, auth failure threshold, gateway offline, internet unavailable, server offline, bandwidth threshold, device repeatedly disconnecting, account expired, certificate expiring, high packet loss.
**Fields:** severity (`INFO` / `WARNING` / `CRITICAL`), timestamp, source, description, status, acknowledgement, resolution, notifications.

### 4.16 Sessions

Track active sessions: user, device, IP, MAC, auth time, duration, download, upload, network/VLAN, assigned policy.

| User | Device | IP | Status |
|------|--------|----|--------|
| John Doe | Laptop | 10.0.20.41 | Online |
| Sarah Smith | Phone | 10.0.20.42 | Online |
| Admin | Desktop | 10.0.10.10 | Online |

### 4.17 Reports & Notifications

- **Reports:** users, devices, network usage, bandwidth, authentication, firewall activity, security events, unknown devices, account expiration, device inventory, admin actions. **Export:** CSV, PDF, JSON; Excel later.
- **Notifications** (via provider abstraction): email, desktop, webhook, future messaging. Configurable by event type and severity.

---

## 5. Architecture

### 5.1 Layered view

```
┌─────────────────────────────────────────────┐
│             DESKTOP APPLICATION              │
│ Dashboard / Users / Devices / Firewall /     │
│ Policies / Monitoring / Reports / Settings   │
└──────────────────────┬──────────────────────┘
                 APPLICATION API
      ┌────────────────┼────────────────┐
 Policy Engine     Auth Engine      Monitoring
      ├────────────────┼────────────────┤
   Firewall          RADIUS         Discovery
      └────────────────┼────────────────┘
                NETWORK SERVICES
      ┌────────────────┼────────────────┐
    Router          Switches            APs
      └────────────────┼────────────────┘
                  END DEVICES
```

### 5.2 Hardware / vendor abstraction

Do **not** hard-code any router, switch, or AP vendor. Use provider interfaces:

```
NetworkProvider:         MikroTik | OpenWrt | pfSense | OPNsense | Cisco | Ubiquiti | Generic/SNMP
AuthenticationProvider:  Local | RADIUS | LDAP | Active Directory
MonitoringProvider:      SNMP | Agent | API | ICMP
```

**Replaceability rule:** swapping RADIUS must not affect User Management, Policy Engine or Desktop UI. Swapping MikroTik for OpenWrt/OPNsense/Cisco/Ubiquiti must not require rewriting the app.

---

## 6. Policy Engine

One of the most important components.

```
USER + DEVICE + GROUP + NETWORK + TIME + POLICY = ACCESS DECISION
```

**Example:**

```
John + Student + Laptop + Student VLAN + 10:00 + Student Policy
  → Allow Internet
  → 20 Mbps down / 5 Mbps up
  → Block Administration VLAN
```

Policies have **priorities and explicit overrides**.

---

## 7. Data Model

Use a **relational database** with foreign keys and proper normalization. Encrypt sensitive data.

| Domain | Tables |
|--------|--------|
| Identity | `users`, `groups`, `roles`, `permissions` |
| Devices | `devices`, `device_types`, `device_assignments` |
| Network | `networks`, `subnets`, `vlans`, `interfaces` |
| Access | `authentication_providers`, `sessions`, `policies`, `firewall_rules`, `bandwidth_policies`, `schedules` |
| Secrets | `credentials`, `credential_access` |
| Observability | `alerts`, `audit_logs`, `network_events`, `monitoring_metrics` |
| Integration | `notifications`, `integrations` |

---

## 8. RBAC, Audit & Credentials

### 8.1 Roles & permissions

**Roles:** Super Administrator, Network Administrator, IT Administrator, Help Desk, Auditor, Read Only.

**Granular permissions:**

```
users.view / create / edit / delete
devices.view / manage
firewall.view / edit
network.view / configure
credentials.view / manage
monitoring.view   reports.view   audit.view
```

Highly sensitive operations require elevated permissions.

### 8.2 Audit logging

Every important admin action is recorded:

```
Timestamp | Administrator | Action | Target | Old value | New value | Result | Source
```

Examples: created user, disabled account, changed firewall rule, changed bandwidth policy, viewed credential, modified VLAN, blocked device.
**Never store passwords or secrets in audit logs.**

### 8.3 Credential vault

**Types:** network, device, service, SSH keys, API, certificates, Wi-Fi, VPN.

**Security requirements:**

- Encryption at rest
- OS secure storage/keychain where available
- Master authentication, optional MFA
- Automatic vault locking
- Access auditing
- Secret rotation reminders
- Never log secrets; never display by default

LANDAR must **never** capture, sniff or collect users' passwords without explicit authorization.

---

## 9. Desktop UI & Navigation

```
Dashboard
Network      → Topology, Networks, VLANs, DHCP, DNS
People       → Users, Groups, Roles, Sessions
Devices      → All Devices, Unknown, Approved, Offline
Access       → Authentication, Policies, Firewall, Rate Limits, Schedules
Monitoring   → Live, Bandwidth, Devices, Authentication, Alerts
Credentials  → Vault
Reports
Audit
Settings
```

---

## 10. Deployment Sizes

The UI and DB model must **not** need rewriting as the network grows.

| Size | Profile |
|------|---------|
| Home | 1 router, 1–3 APs, 5–50 devices |
| Small organization | 1 firewall, multiple switches & APs, 50–500 devices |
| School | Multiple VLANs, hundreds–thousands of users, multiple APs/switches, central auth, bandwidth policies, student/teacher separation |

---

## 11. Example: School Network

**Student account**

```
Student ID: STU20260045   Username: john.doe   Group: Students
```

| | Student Policy | Teacher Policy |
|---|---|---|
| Internet | Allowed | Allowed |
| Internal school LAN | Restricted | School systems: Allowed |
| Teacher network / resources | Denied | Allowed |
| Administration | Denied | Restricted |
| Max devices | 2 | 5 |
| Download / Upload | 20 / 5 Mbps | 100 / 50 Mbps |
| Schedule | Mon–Fri 08:00–18:00 | — |

Administrators have broader access.

---

## 12. Development Phases

Do **not** build everything at once.

| Phase | Name | Scope |
|-------|------|-------|
| 1 | Foundation | Desktop shell, database, users, devices, groups, roles, basic dashboard, audit system |
| 2 | Network Discovery | LAN discovery, device inventory, status, topology |
| 3 | Authentication | Local auth, RADIUS integration, user sessions, account policies |
| 4 | Network Policies | Groups, VLAN concepts, access schedules, device policies, bandwidth policies |
| 5 | Firewall | Provider abstraction, rule management, visualization, logging |
| 6 | Monitoring | Network/device monitoring, bandwidth, alerts, historical metrics |
| 7 | Administration | Remote administration, device & configuration management, advanced integrations |
| 8 | Advanced Platform | Captive portal, DHCP/DNS management, multi-vendor, automation, advanced reporting, plugins, high availability |

---

## 13. Critical Architectural Requirement

Establish the **central data model and policy model first**. Everything integrates into this chain:

```
USER → GROUP → DEVICE → NETWORK → POLICY → FIREWALL → QOS → ACCESS → MONITORING → AUDIT
```

**Do not build unrelated screens independently.**

---

## 14. Product Goal

LANDAR should feel like a centralized **Network Control Center**. From one application an admin can answer:

```
WHO IS CONNECTED?              WHAT IS THE FIREWALL DOING?
WHAT DEVICES ARE CONNECTED?    IS THE NETWORK HEALTHY?
WHERE ARE THEY CONNECTED?      WHAT PROBLEMS EXIST?
ARE THEY AUTHORIZED?           WHAT HAPPENED PREVIOUSLY?
WHAT CAN THEY ACCESS?          WHO CHANGED THE CONFIGURATION?
HOW MUCH BANDWIDTH DO THEY HAVE?
```

…and, where authorized, change network behavior.

---

## 15. Required Deliverables Before Coding

**Do not start by writing UI screens.** First produce and get reviewed:

- [ ] 1. System architecture
- [ ] 2. Component diagram
- [ ] 3. Data model (ERD)
- [ ] 4. Authentication architecture
- [ ] 5. Policy engine design
- [ ] 6. Network integration architecture
- [ ] 7. Security model
- [ ] 8. API contracts
- [ ] 9. Deployment architecture
- [ ] 10. MVP scope

Only then begin implementation. Every component must be replaceable without rewriting the whole application. The goal is a **network-management platform**, not an app tightly coupled to one piece of hardware.

**Suggested next artifact:** a technical architecture document derived from this README (ERD, services, APIs, auth flow, firewall/RADIUS architecture, recommended tech stack).
