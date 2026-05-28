
# Brainstorm: Distributed Signalbox & Taskbar Integration

## Vision
Enable Signalbox to monitor and control scripts across multiple computers, aggregating status and control into a unified taskbar/tray interface for the user.

## Use Cases
- **Server Monitoring:** Signalbox runs on a server, managing scripts. A user links their local Signalbox to the server, viewing remote results alongside local ones.
- **Multi-device User:** A user with several laptops/desktops wants a single dashboard (taskbar/tray) to see and control all their Signalbox instances.
- **Swarm/Cluster:** Admin monitors a fleet of machines, each running Signalbox, with a central overview and control panel.

## Key Challenges
- **Linking:** How do Signalbox instances discover and authenticate with each other?
- **Data Transfer:** How is status, logs, and control data securely exchanged?
- **Security:** Prevent unauthorized access, ensure data integrity/confidentiality.

## Technical Approaches

### 1. Linking/Discovery
- **Manual Linking:** User provides address/token of remote Signalbox to link.
- **LAN Discovery:** Use mDNS/zeroconf for auto-discovery on local network.
- **Cloud Relay:** Optional relay server for NAT traversal or remote access.

### 2. Authentication & Authorization
- **API Tokens:** Each Signalbox instance exposes an API secured by a unique token.
- **Mutual TLS:** For advanced setups, use client/server certificates for mutual authentication.
- **User Approval:** Linking requires approval on both ends (e.g., via code or prompt).

### 3. Data Transfer Protocols
- **REST API:** Each instance exposes a REST API for status, logs, and control commands.
- **WebSocket:** For real-time updates (e.g., status changes, alerts), use WebSocket connections.
- **gRPC:** For efficient, typed communication (optional, advanced).

### 4. Data Model
- **Status:** Each instance reports script/group status, last run, next run, errors, etc.
- **Logs:** Optionally stream or fetch logs on demand.
- **Control:** Allow remote start/stop of scripts/groups (with permissions).

### 5. Aggregation/UI
- **Taskbar/Tray App:** Aggregates status from all linked Signalbox instances, shows summary (green/red), and details per host.
- **Configurable:** User can select which hosts to show, set alerting preferences, etc.

### 6. Security Considerations
- **Encryption:** All communication over TLS (even on LAN).
- **Access Control:** Only authorized users/hosts can link and control.
- **Audit Logging:** Log all remote actions/commands for traceability.

## Example Workflow
1. User installs Signalbox on multiple machines.
2. User links remote instances via API token or approval prompt.
3. Taskbar app queries all linked instances for status, aggregates results.
4. User sees unified status in tray, can drill down or trigger actions.

## Open Questions
- How to handle version mismatches between instances?
- Should there be a central relay/cloud option for remote access?
- How to handle network partitions or offline hosts gracefully?

## Next Steps
- Prototype REST API for status/control.
- Design linking/approval flow.
- Build minimal tray app that aggregates from multiple sources.

---
See also: `taskbar.md` for tray UI/UX and platform notes.