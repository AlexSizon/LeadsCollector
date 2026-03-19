## Context

The current system is strong at discovering businesses, enriching contact data, scoring lead quality, and generating evidence-based outreach angles. It is weak at the operational layer that sits after lead generation: there is no durable concept of outreach eligibility, no separation between safe and unsafe contact channels, no approval workflow, no suppression list, and no campaign state.

This change introduces a local, operator-driven outreach layer focused on one practical go-to-market path: public business email outreach for website sales or website improvement offers. The codebase is currently file-oriented and local-first, with JSON outputs and a Streamlit viewer. That favors an implementation that remains local-first, reviewable, and reversible, instead of adding a remote SaaS dependency as the primary source of truth.

Constraints:
- Email is the only channel with enough scale and manageable risk to justify first-class outbound support.
- Guessed emails, WhatsApp, Messenger, and call workflows must not be silently treated as equivalent to scraped business inboxes.
- Any send path must preserve operator review and allow objection/suppression handling.
- Actual delivery depends on sender credentials and domain configuration that the operator must provide.

## Goals / Non-Goals

**Goals:**
- Add a deterministic eligibility layer that marks which leads are safe for email-first outreach and why.
- Add a durable local store for campaigns, suppressions, approvals, and per-lead outreach state.
- Generate email-specific outreach drafts for two offer types: `new-website` and `website-improvement`.
- Extend the viewer with an outreach workspace for review, approval, export, and send actions.
- Add a delivery abstraction that supports `dry-run`, `export-only`, and SMTP/ESP-backed sending after preflight checks pass.
- Record reply, bounce, opt-out, and suppression outcomes so outreach history affects future eligibility.
- Explicitly surface what operator-owned inputs are required before real sending is enabled.

**Non-Goals:**
- Fully autonomous cold outreach without human review.
- WhatsApp-, Messenger-, or SMS-first campaign automation.
- CRM replacement, lead nurturing, or multi-step sales automation.
- Broad legal automation that guarantees compliance in every jurisdiction without operator review.
- Inbox parsing or reply classification beyond a minimal manual/state-update workflow in the first implementation.

## Decisions

### 1. Use email-first as the only first-class outbound channel
The system will treat direct business email as the primary outbound path. Phone will remain visible, but not part of the first send engine. WhatsApp and Messenger will remain informative/contact indicators only.

Why:
- The current dataset has materially more usable email coverage than messenger coverage.
- Email is easier to batch, review, template, and audit than live calls.
- Messenger channels require stricter consent assumptions and do not have enough reach to justify being the core workflow.

Alternatives considered:
- Phone-first workflow: higher manual friction and higher compliance complexity for the first release.
- Multi-channel launch: too much policy and product complexity before basic email operations exist.

### 2. Introduce a local SQLite outreach store
Mutable outreach state will live in a local SQLite database, likely under `data/outreach.db`, rather than being embedded back into the generated leads JSON.

Why:
- Leads JSON is a generated artifact, not a reliable mutable operational datastore.
- Campaigns, suppressions, approvals, and reply states need transactional updates and queryable history.
- SQLite fits the current local-first architecture and keeps rollout simple.

Alternatives considered:
- JSON/CSV sidecar files: too fragile for concurrent or repeated state updates.
- Hosted database: unnecessary operational weight for the current product stage.

### 3. Separate lead evidence from outreach operations
Lead generation output remains the evidence layer; outreach tables reference lead identifiers plus a snapshot of the message and eligibility decision used at send time.

Why:
- Outreach must stay reproducible even if the pipeline reruns later and changes a lead.
- Auditability requires preserving what was approved and why.

Alternatives considered:
- Mutating the lead JSON in place: would blur generated data and operator actions.

### 4. Add explicit provenance and policy gating before any send
Each usable contact channel will carry provenance (`scraped`, `json_ld`, `social`, `guessed`, `manual`) and policy eligibility (`allowed`, `review_required`, `blocked`) derived from country/channel rules plus suppression state.

Why:
- The product already knows contact channels, but not whether they are equally safe to use.
- This keeps “reachable” separate from “sendable”.

Alternatives considered:
- One global boolean like `can_email`: too lossy for review and auditing.

### 5. Keep actual sending behind adapter + preflight
The system will support three sender modes:
- `dry-run`: render and validate without delivery
- `export-only`: produce CSV/JSON payloads for external mailing tools
- `smtp` or future ESP adapter: send directly after configuration and preflight succeed

Why:
- Not every operator will be ready to send directly from the tool on day one.
- Export-only mode provides immediate value without forcing a mail provider integration first.

Alternatives considered:
- SMTP-only: too coupled to credentials and domain setup.
- Export-only forever: useful, but leaves no path to integrated delivery.

### 6. Make human approval a hard requirement before send
Every outbound email draft will require explicit approval before entering a sendable batch. Approval captures approver identity, timestamp, offer type, and rendered copy.

Why:
- This protects against low-quality or non-compliant messaging.
- It matches the user’s current stage: assisted outreach, not autonomous outreach.

Alternatives considered:
- Auto-send for high-score leads: too risky and hard to unwind.

### 7. Extend outreach generation with offer-aware email copy
`outreach_generation` will produce not just `outreach_angle` and `short_pitch`, but also:
- `offer_type`
- `email_subject`
- `email_opening`
- `email_cta`
- `email_body_preview`

The offer type defaults from evidence:
- `new-website` for `NO_WEBSITE` / `SOCIAL_ONLY`
- `website-improvement` for `HAS_WEBSITE` / `BROKEN_WEBSITE`

Why:
- The current copy primitives are useful but not enough for real email review and export.

Alternatives considered:
- Let the operator write every email manually: too slow for batching and inconsistent across leads.

### 8. Extend the viewer instead of creating a separate app
The Streamlit viewer will gain an outreach workspace rather than introducing another UI.

Why:
- Operators already review leads there.
- Eligibility, compliance flags, and message review belong close to the lead evidence.

Alternatives considered:
- Separate outreach dashboard: more code, duplicate filtering, and split operator context.

## Risks / Trade-offs

- [Policy complexity across countries] -> Start with a conservative ruleset and require explicit operator review for ambiguous contact classes.
- [False confidence from public data] -> Show provenance and policy reasons in the UI and block guessed-email sending by default.
- [SQLite state drift after reruns] -> Store lead identifiers plus message snapshots and avoid mutating historical campaign rows from new pipeline runs.
- [Inbox/delivery reputation risk] -> Require sender preflight, daily caps, and export-only mode before integrated sending is enabled.
- [Operator confusion between reachable and sendable] -> Use separate labels and filters in the viewer for `contactable`, `email-eligible`, and `send-approved`.
- [Legal uncertainty] -> Treat compliance helpers as decision support, not automatic legal sign-off; log the policy version used for every send.

## Migration Plan

1. Add the outreach SQLite schema and policy config without changing existing lead generation outputs.
2. Extend lead models and pipeline outputs with non-breaking eligibility/provenance fields.
3. Add email-copy generation and campaign draft creation.
4. Add viewer workspace for review and approval.
5. Add export-only batch flow.
6. Add SMTP/ESP send adapter behind explicit configuration and preflight.
7. Add suppression, opt-out, and campaign result update paths.

Rollback:
- Disable the outreach workspace and send adapter while keeping lead generation intact.
- Campaign/suppression history remains in the local outreach store for later re-enable.

## Open Questions

- Should country policy be strict-common-denominator first, or a per-country matrix from day one?
- Should guessed emails ever be sendable with manual override, or remain permanently blocked?
- Is manual reply-state entry enough for phase one, or is mailbox sync needed immediately?
- Should send throttling be stored per campaign, per sender mailbox, or globally?

## Required From Operator

Before actual email delivery can happen, the operator will need to provide:
- A sender mailbox or ESP account to use for outreach
- Authentication setup for the sender domain or mailbox
  - SMTP credentials or ESP API key
  - SPF / DKIM / ideally DMARC configured for the sender domain
- Sender identity details
  - company name
  - sender display name
  - reply-to address
  - company website / landing page
- Offer packaging
  - what exactly is being sold: `new site`, `site refresh`, `conversion fix`, `booking flow`, etc.
  - pricing or pricing approach
  - CTA destination: booking link, contact form, calendar link, reply CTA
- Compliance decisions
  - which countries are allowed in the first wave
  - whether guessed emails are forbidden or reviewable
  - suppression/opt-out policy owner
- Operating rules
  - daily send limit
  - approval owner(s)
  - bounce / reply / objection handling process
