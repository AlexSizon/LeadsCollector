## ADDED Requirements

### Requirement: Viewer provides an outreach workspace for email-first operations
The viewer SHALL provide an outreach workspace distinct from general lead browsing. The outreach workspace SHALL focus on email-first campaign preparation and show only outreach-relevant fields such as eligibility, provenance, policy result, offer type, and approval state.

#### Scenario: Outreach workspace filters to outreach-usable subset
- **WHEN** the user opens the outreach workspace
- **THEN** the viewer SHALL display leads with outreach-related fields and controls instead of only the generic lead table

#### Scenario: Sendability reason is visible
- **WHEN** a lead is not sendable
- **THEN** the viewer SHALL display the reason such as guessed-only email, suppression, or policy block

### Requirement: Viewer exposes compliance and provenance signals during review
The viewer SHALL show contact provenance, policy decision, suppression state, and sendability state for each outreach candidate before approval.

#### Scenario: Guessed-only contact is visibly blocked
- **WHEN** a lead has only `guessed_email`
- **THEN** the viewer SHALL display a visible blocked or review-required state before approval actions are available

#### Scenario: Policy review reason is shown inline
- **WHEN** a lead requires policy review
- **THEN** the viewer SHALL show the policy reason inline in the outreach review UI

### Requirement: Viewer supports draft approval and campaign assignment
The viewer SHALL allow an operator to review generated outreach drafts, adjust offer type if permitted, approve a draft, and assign approved drafts into campaign batches.

#### Scenario: Draft can be approved from viewer
- **WHEN** a lead has a generated outreach draft and passes policy checks
- **THEN** the viewer SHALL provide an approval action that records operator approval

#### Scenario: Unapproved lead cannot be batched for send
- **WHEN** a lead has not been approved
- **THEN** the viewer SHALL prevent the lead from being added to a sendable campaign batch

### Requirement: Viewer supports export and direct-send campaign actions
The viewer SHALL allow operators to launch `dry-run`, `export-only`, and `direct-send` actions for approved campaign batches. `direct-send` SHALL only be available when sender preflight succeeds.

#### Scenario: Direct-send disabled until preflight passes
- **WHEN** sender configuration is incomplete or invalid
- **THEN** the viewer SHALL disable `direct-send` actions and surface the missing prerequisites

#### Scenario: Export-only action remains available without sender credentials
- **WHEN** sender preflight has not succeeded
- **THEN** the viewer SHALL still allow `export-only` campaign execution for approved leads
