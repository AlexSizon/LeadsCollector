## 1. Outreach data model and storage

- [x] 1.1 Add outreach domain models for eligibility, provenance, campaign, campaign item, suppression entry, and audit event
- [x] 1.2 Introduce a local SQLite outreach store and schema bootstrap for campaigns, suppressions, approvals, and audit history
- [x] 1.3 Add config structures for sender profiles, execution mode, daily caps, and country/channel policy versioning

## 2. Eligibility and compliance gating

- [x] 2.1 Implement email eligibility classification for `allowed`, `review_required`, and `blocked`
- [x] 2.2 Record contact provenance for direct email, guessed email, social-derived contact, and manual contact sources
- [x] 2.3 Implement suppression list checks for opt-out, manual suppression, and hard-bounce cases
- [x] 2.4 Implement country/channel policy evaluation with human-readable reasons and policy version recording

## 3. Outreach generation

- [x] 3.1 Extend outreach generation to produce `offer_type`, `email_subject`, `email_opening`, `email_cta`, and `email_body_preview`
- [x] 3.2 Implement default offer-type mapping from website status with operator override support
- [x] 3.3 Add guardrails so generated email copy stays factual, low-pressure, and evidence-based

## 4. Campaign drafting and execution

- [x] 4.1 Implement campaign draft creation from approved email-eligible leads with immutable message snapshots
- [x] 4.2 Implement campaign item lifecycle states: `draft`, `approved`, `sent`, `replied`, `bounced`, `opted_out`, and `failed`
- [x] 4.3 Implement execution modes for `dry-run` and `export-only`
- [x] 4.4 Add sender preflight checks and a `direct-send` adapter boundary for SMTP or future ESP integration

## 5. Viewer outreach workspace

- [x] 5.1 Add an outreach workspace to the Streamlit viewer with sendability-focused columns and filters
- [x] 5.2 Surface compliance data in the UI: provenance, policy result, suppression state, and sendability reason
- [x] 5.3 Add draft review, approval, offer-type override, and campaign assignment controls
- [x] 5.4 Add campaign execution actions for `dry-run`, `export-only`, and gated `direct-send`

## 6. Feedback and suppression updates

- [x] 6.1 Add workflows to record replies, hard bounces, and opt-outs against campaign items
- [x] 6.2 Feed bounce and opt-out outcomes back into suppression and future eligibility checks
- [x] 6.3 Persist audit events for draft creation, approval, export, send, failure, reply update, bounce update, and opt-out update

## 7. Tests and operator readiness

- [x] 7.1 Add unit tests for eligibility classification, policy gating, provenance handling, and suppression enforcement
- [x] 7.2 Add tests for outreach draft generation and offer-type selection
- [x] 7.3 Add campaign store and lifecycle tests for approval, export, send, failure, bounce, and opt-out transitions
- [x] 7.4 Add viewer tests or smoke coverage for the outreach workspace and action gating
- [x] 7.5 Document operator prerequisites for real sending: sender mailbox/ESP, domain auth, sender identity, offer packaging, compliance choices, and daily sending limits
