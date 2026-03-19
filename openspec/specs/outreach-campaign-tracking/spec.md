## ADDED Requirements

### Requirement: System persists outreach campaigns and per-lead campaign items
The system SHALL persist outreach campaigns and per-lead campaign items in a durable local store. A campaign SHALL have a unique identifier, execution mode, sender profile reference, creation timestamp, and operator metadata.

Each campaign item SHALL reference the lead, rendered message snapshot, approval state, send state, and result metadata.

#### Scenario: Campaign stores immutable message snapshot
- **WHEN** a lead is added to a campaign
- **THEN** the campaign item SHALL store the exact rendered outreach message used for that campaign item

#### Scenario: Campaign can contain multiple approved leads
- **WHEN** an operator batches multiple approved leads into one campaign
- **THEN** the system SHALL persist separate campaign items linked to one campaign identifier

### Requirement: System tracks campaign item lifecycle states
The system SHALL track campaign item lifecycle states at minimum:
- `draft`
- `approved`
- `sent`
- `replied`
- `bounced`
- `opted_out`
- `failed`

State changes SHALL be timestamped and auditable.

#### Scenario: Approved item transitions to sent
- **WHEN** an approved campaign item is successfully transmitted by the selected delivery mode
- **THEN** the item SHALL transition to `sent` with a send timestamp

#### Scenario: Delivery failure records failed state
- **WHEN** delivery fails before the message is accepted by the sender transport
- **THEN** the campaign item SHALL transition to `failed` with an error reason

#### Scenario: Reply state can be recorded after send
- **WHEN** an operator records that a recipient replied
- **THEN** the campaign item SHALL transition to `replied` while preserving prior send metadata

### Requirement: System records bounce and opt-out outcomes
The system SHALL record bounce and opt-out outcomes at campaign-item level and feed those outcomes back into suppression enforcement.

#### Scenario: Hard bounce updates campaign item and suppression
- **WHEN** a campaign item is marked as a hard bounce
- **THEN** the item SHALL transition to `bounced` and the corresponding email address SHALL be suppressed for future outreach

#### Scenario: Opt-out updates campaign item and suppression
- **WHEN** a recipient opts out after a campaign item was sent
- **THEN** the item SHALL transition to `opted_out` and future eligibility checks SHALL block that contact

### Requirement: System provides campaign audit history
The system SHALL retain an audit history for campaign actions including draft creation, approval, export, send, failure, reply update, bounce update, and opt-out update.

Audit history SHALL include the acting operator identity, timestamp, action type, and the campaign or lead item affected.

#### Scenario: Approval action is auditable
- **WHEN** an operator approves a draft
- **THEN** the system SHALL create an audit record showing who approved it and when

#### Scenario: Export action is auditable
- **WHEN** an operator exports a campaign batch
- **THEN** the system SHALL record the export action in audit history
