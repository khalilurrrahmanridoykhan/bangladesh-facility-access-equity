# Public facility-access system and mobile app

## Recommendation

Build it, but release it in stages. The strongest public value is not merely displaying a map; it is helping someone find an appropriate facility, understand realistic travel constraints, and navigate there using current, trustworthy information.

## Intended users

1. Residents and caregivers looking for nearby care
2. Community health workers making referrals
3. Ambulance and emergency coordinators
4. Health planners identifying underserved populations
5. Facility managers correcting service information

## Phase 1 — trustworthy public web map

- Bangla-first responsive web application with English support
- Current-location and manual place search
- Nearby facilities ranked by modeled access time
- Filters for facility type, emergency care, opening status, and services
- Route preview with separate walking/first-mile and driving estimates
- Clear data date, source, uncertainty, and “report incorrect information” controls
- Low-bandwidth mode and shareable facility links
- Aggregate equity layer for planners; no individual movement data

Success gate: validate a sample of facilities and routes with local partners in at least one urban and one remote district.

## Phase 2 — installable offline-first mobile app

- Progressive Web App first, then Android packaging if field testing demonstrates a need
- Downloadable district maps and facility directory
- GPS location when offline
- Cached search and last-known facility details
- One-tap call and share-location actions
- Community health worker referral workflow
- Background synchronization when connectivity returns

Starting with a PWA avoids maintaining separate web and mobile codebases while requirements are still changing. A native Android app becomes worthwhile when offline navigation, background location, or device integrations cannot be delivered reliably by the PWA.

## Safety and governance requirements

- Never describe modeled travel time as a guarantee
- Display emergency guidance and official contact information
- Do not collect identifiable health conditions or location histories by default
- Obtain explicit consent before using or sharing live location
- Apply retention limits, encryption, access controls, and audit logs to any operational data
- Establish a verified facility-update workflow; public edits must be reviewed
- Separate public routing from planning analytics and administrative functions
- Test accessibility, Bangla typography, older Android devices, and intermittent 2G/3G connectivity

## Technical shape

- Shared API for facility search, routing, feedback, and versioned datasets
- PostGIS for facilities, boundaries, service metadata, and aggregate access results
- OSRM for road routing plus an explicit first-mile model
- MapLibre for web/mobile maps with offline-compatible vector tiles
- Scheduled HDX/OSM imports with validation, provenance, and rollback
- Privacy-preserving telemetry limited to reliability and aggregate product usage

## Go/no-go criteria for a public launch

- Facility existence and coordinates verified for the launch area
- Service and opening-status fields have a named owner and update process
- Route and first-mile estimates field-tested in urban and remote settings
- Incorrect-data reporting has a response workflow
- Security and privacy review completed
- The interface works in Bangla on low-cost Android devices and poor connections
