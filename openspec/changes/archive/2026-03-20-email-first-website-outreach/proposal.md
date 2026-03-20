## Why

The project already discovers business contact data and generates evidence-based outreach angles, but there is no operational workflow for turning those leads into compliant website sales outreach. We need an email-first system because email is currently the highest-reach, lowest-friction channel in the dataset, while phone and messenger channels require stricter handling and narrower use.

## What Changes

- Add an email-first outreach workflow that classifies leads by channel eligibility, filters out unsafe contacts, and prepares outreach-ready campaigns for website sales or website improvement offers.
- Add compliance controls for contact provenance, suppression lists, objection handling, and country/channel policy gating before any outreach is exported or sent.
- Extend outreach generation so the system can produce email-specific subject lines, opening lines, and CTA variants for two offer types: `new-website` and `website-improvement`.
- Extend the viewer with an outreach workspace for reviewing eligible leads, approving messages, inspecting compliance flags, and exporting or sending campaign batches.
- Add campaign tracking for draft, approved, sent, replied, bounced, and opted-out states, plus durable audit history for who approved and when a contact was used.
- Add sender configuration requirements and preflight checks so actual delivery only runs when mailbox/provider settings and legal prerequisites are present.

## Capabilities

### New Capabilities
- `email-outreach-workflow`: review, approve, batch, export, and send email-first campaigns against eligible leads
- `outreach-compliance`: provenance tracking, policy gating, suppression lists, objections, and channel eligibility enforcement
- `outreach-campaign-tracking`: campaign records, per-lead delivery state, reply state, bounce state, and audit history

### Modified Capabilities
- `outreach-generation`: generate email-specific outreach copy and distinguish `new-website` versus `website-improvement` offers
- `leads-viewer`: add an outreach review workspace with compliance visibility, approval flow, and campaign actions

## Impact

- Affected code: `src/pipeline.py`, `src/models.py`, `viewer/app.py`, and likely new outreach/compliance modules plus storage for campaigns and suppression data
- Affected outputs: lead records will need outreach eligibility, provenance, and campaign state fields
- New systems/dependencies: sender configuration for SMTP or ESP integration, local persistence for campaigns/suppressions, and compliance policy configuration by country/channel
- Operational impact: actual sending will require user-provided mailbox/domain setup, sender identity details, and human approval rules before outreach is executed
