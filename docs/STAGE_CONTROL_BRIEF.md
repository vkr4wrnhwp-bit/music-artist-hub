# MASTER BUILD PROMPT — STREET BANKER STAGE CONTROL + SHOW PASSPORT

> Owner's brief, received 2026-09-04, stored verbatim. An earlier version of
> this brief (2026-08-22) was lost — it existed only as a chat message, and
> when those transcripts were compacted the prose went with them, leaving a
> nine-line summary. That is why it lives in the repo now. Do not paraphrase
> this file, and do not delete it when the work ships: the acceptance criteria
> and the safety rules are the contract.
>
> Owner's design instruction, same message: *"use the highest level of design
> you have reference your remix page and more for branding."*

---

You are a senior product architect, live-audio systems engineer, full-stack
developer, realtime-systems engineer, edge-computing engineer, security
engineer, touring-production designer, and UX lead working inside the existing
Street Banker codebase.

Build Street Banker Stage Control + Show Passport as a production-ready module
within the existing Street Banker platform.

Do not create a disconnected demo or parallel application. Inspect the current
repository, authentication, tenant model, database, UI system, realtime
infrastructure, deployment configuration, and existing features before changing
anything.

Preserve all existing Street Banker functionality.

## PRODUCT OBJECTIVE

Create a secure live-show operating system connecting:

* Artists
* Touring musicians
* Tour managers
* Production managers
* Stage managers
* Monitor engineers
* Front-of-house engineers
* Venue production teams
* Authorized audio-console systems

The product has two connected layers:

1. **Show Passport** — a portable, versioned technical record for an artist or show.
2. **Stage Control** — a realtime request and engineer-control workflow for monitoring, cues, technical changes, and show execution.

The system must improve communication without allowing unsafe or unauthorized
control of live production equipment.

## CORE OPERATING PRINCIPLE

A performer request is not automatically a console command.

The default workflow is:

1. Performer submits a request.
2. Engineer receives the request.
3. Engineer reviews it.
4. Engineer accepts, modifies, rejects, or applies it.
5. The system records the result.
6. Supported console changes pass through a secured local bridge.
7. Unsupported or unsafe changes remain human-readable requests.

Direct console control may only exist for explicitly authorized, bounded,
reversible capabilities.

## NON-NEGOTIABLE SAFETY RULES

* Do not claim support for a console that has not been tested.
* Do not fabricate hardware integrations.
* Do not expose venue control networks directly to the public internet.
* Do not allow performers to change preamp gain, phantom power, patching, routing, clocking, firmware, network settings, output protection, system processing, or other safety-critical parameters.
* Do not allow uncontrolled level jumps.
* Do not automate commands without capability validation.
* Every console mutation requires authorization, bounds checking, audit history, and a confirmed device response when supported.
* Provide a request-only fallback.
* Provide an immediate engineer lockout and kill switch.
* Fail safely when realtime connectivity is lost.
* Preserve the physical console as the final source of control.
* Never present a requested change as applied until confirmation is received.
* Separate simulated, requested, approved, sent, acknowledged, applied, failed, and reverted states.
* All migrations must be reversible.
* Add automated tests for authorization, safety limits, realtime state, command handling, and offline behavior.

## PRODUCT MODES

Support three explicit modes:

**1. Passport-Only Mode** — The system stores and shares show information but
does not connect to a console.

**2. Request Mode** — Performers submit monitor or production requests.
Engineers apply changes manually and record the outcome.

**3. Connected Control Mode** — Approved engineers may send supported, bounded
commands through a secured local Stage Bridge to a tested console adapter.

The active mode must always be visible.
Never silently move from Request Mode into Connected Control Mode.

## USER ROLES

Support roles such as:

* Platform Administrator
* Organization Administrator
* Artist
* Band Member
* Tour Manager
* Production Manager
* Musical Director
* Stage Manager
* Monitor Engineer
* Front-of-House Engineer
* Venue Administrator
* Venue Technician
* Read-Only Guest

Permissions should include:

* Manage artist passport
* View passport
* Publish passport version
* Create show
* Invite crew
* Assign stage role
* View stage plot
* Edit input list
* Edit patch list
* Configure monitor mixes
* Submit performer request
* Review requests
* Apply manual change
* Operate connected control
* Configure Stage Bridge
* Configure console adapter
* Arm show
* Lock show
* Trigger emergency lockout
* Export production documents
* View audit history

Enforce all permissions server-side.

## SHOW PASSPORT

Build a reusable, versioned technical profile for each artist or production.

### Artist and Production Identity

* Artist name
* Production name
* Tour name
* Production contacts
* Emergency production contact
* Current passport version
* Last verified date
* Applicable territories
* Venue-size or show-format variants

### Personnel

* Performers
* Instruments
* Touring crew
* Production roles
* Contact visibility controls
* Show-specific assignments

### Stage Plot

* Stage dimensions
* Performer positions
* Instrument positions
* Microphone positions
* DI positions
* Monitor wedges
* In-ear systems
* Risers
* Playback positions
* Power requirements
* Backline
* Special scenic or staging elements
* Access requirements

Provide a structured editor and an exportable production view.

### Input List

For every input:

* Channel number
* Source
* Performer
* Microphone or DI
* Stand or mount
* Phantom-power requirement
* Patch destination
* Subsnake or stagebox
* Monitor-mix relevance
* Notes
* Required or optional status

### Output and Monitor List

* Monitor-mix name
* Performer
* Wedge or IEM
* Transmitter and receiver information
* Stereo or mono
* Output patch
* Talkback destination
* Safe starting state
* Notes

### Playback and Timecode

* Playback system
* Primary and redundant devices
* Output format
* Sample rate
* Bit depth
* Channel map
* Click
* Cues
* Timecode type
* Timecode frame rate
* MIDI or OSC requirements
* Redundancy procedure
* Failure procedure

### Backline and Equipment

* Artist-provided equipment
* Venue-provided equipment
* Rental requirements
* Acceptable substitutions
* Power requirements
* Network requirements
* Setup notes

### Show Cues

* Song
* Cue number
* Cue type
* Responsible operator
* Trigger method
* Required confirmation
* Fallback instruction
* Notes

### Documents

Allow controlled attachment of:

* Technical rider
* Stage plot
* Input list
* Patch list
* Lighting notes
* Playback guide
* Set list
* Venue advance
* Safety documentation
* Approved reference files

Scan and validate uploads. Do not execute embedded content.

## PASSPORT VERSIONING

Every published passport must be immutable.

Support:

* Draft version
* Review state
* Published version
* Superseded version
* Archived version
* Show-specific snapshot
* Comparison between versions
* Change log
* Publisher identity
* Publication timestamp

A booked show should retain the specific passport version used during
advancement. Later passport edits must not silently change historical shows.

## SHOW CREATION AND ADVANCEMENT

A show record should include:

* Artist
* Venue
* Room
* Date and local timezone
* Load-in
* Soundcheck
* Doors
* Set time
* Curfew
* Production contacts
* Assigned crew
* Passport version
* Console information
* Stage Bridge status
* Operating mode
* Advancement status
* Open questions
* Technical conflicts
* Notes

Suggested advancement states:

* Draft
* Invited
* Reviewing
* Questions Open
* Changes Requested
* Approved
* Locked
* Show Active
* Completed
* Archived

## SECURE SHOW ACCESS

Create show-specific QR and link access.

Requirements:

* Use opaque signed tokens.
* Tokens must be revocable.
* Tokens must expire.
* Tokens must be scoped to one show and role.
* Do not place private show information directly in the QR payload.
* Support read-only access.
* Support invited authenticated access.
* Allow the show administrator to revoke all active guest links.
* Log access and revocation.
* Never use predictable show IDs as security credentials.

## PERFORMER INTERFACE

Create a low-friction mobile interface suitable for dark stages and
high-pressure environments.

A performer should be able to:

* Select their authorized monitor mix.
* Request more or less of an approved source.
* Request mute or unmute review for an approved source.
* Request talkback assistance.
* Report distortion.
* Report no signal.
* Report excessive level.
* Report feedback.
* Report an equipment problem.
* Send a short note.
* Cancel a pending request.
* See whether the request is pending, acknowledged, applied, rejected, or failed.

Requirements:

* Large touch targets.
* Minimal navigation.
* Strong contrast.
* No accidental horizontal sliders that can jump levels.
* Prefer bounded step controls.
* Clearly identify the selected mix and show.
* Require confirmation for unusual requests.
* Provide vibration or visible confirmation when supported.
* Continue showing the last known state when offline, clearly marked as stale.
* Do not claim that a change was applied without engineer or device confirmation.

## ENGINEER DESK

Build a desktop and tablet interface for the monitor engineer.

The Engineer Desk should show:

* Current show
* Operating mode
* Stage Bridge health
* Console-adapter health
* Active performers
* Monitor mixes
* Incoming requests
* Request priority
* Current request state
* Recent changes
* Console acknowledgements
* Failed commands
* Safety warnings
* Talkback requests
* Device connectivity
* Complete audit timeline

Engineers must be able to:

* Acknowledge a request.
* Accept it.
* Modify the requested amount.
* Apply it manually.
* Send an approved connected command.
* Reject it with a reason.
* Revert a supported command.
* Lock a performer's controls.
* Lock a mix.
* Lock the complete show.
* Switch to Request Mode.
* Trigger emergency lockout.
* Add notes.
* Group duplicate requests.
* Mark an equipment issue.
* Escalate to production management.

## REQUEST MODEL

Each request must include:

* Show
* Requesting user
* Performer
* Authorized monitor mix
* Requested source
* Request type
* Requested direction
* Requested step size
* Performer note
* Created time
* Priority
* Current state
* Reviewing engineer
* Engineer response
* Approved value or delta
* Console command reference when applicable
* Device acknowledgement
* Applied time
* Failure reason
* Revert reference
* Audit events

Request states should include:

* Pending
* Acknowledged
* Modified
* Approved
* Applied Manually
* Queued for Device
* Sent
* Device Acknowledged
* Applied
* Rejected
* Failed
* Reverted
* Cancelled
* Expired

## REALTIME ARCHITECTURE

Use the existing realtime infrastructure where suitable.

Requirements:

* Authenticated realtime connections
* Tenant and show authorization
* Server-generated event IDs
* Ordered processing where required
* Idempotent command handling
* Reconnect support
* State resynchronization
* Duplicate-event protection
* Heartbeats
* Presence
* Clear stale-state behavior
* Server timestamps
* Local-show timezone display
* Audit persistence separate from transient socket state

Do not depend on realtime messages as the only durable record.

## CONSOLE-ADAPTER ARCHITECTURE

Create a capability-based adapter interface.

A console adapter must declare:

* Manufacturer
* Product family
* Tested model
* Tested firmware
* Protocol
* Supported commands
* Read capabilities
* Write capabilities
* Acknowledgement support
* Revert support
* Connection requirements
* Safety limits
* Known limitations
* Adapter version

Possible commands may include only tested, authorized operations such as:

* Read mix membership
* Read supported send level
* Apply a bounded send-level delta
* Read mute state
* Request an approved mute-state change
* Read device health

Do not generically claim support for Yamaha, DiGiCo, Avid, Allen & Heath,
Midas, Behringer, SSL, or any manufacturer without implementing and testing the
specific adapter.

Create a simulator adapter for development and automated tests. Clearly label
it as simulated.

## STAGE BRIDGE

Build a secure local edge service called Stage Bridge.

Stage Bridge runs on an approved computer or appliance on the venue's
production network.

Its responsibilities are:

* Maintain an outbound authenticated connection to Street Banker.
* Connect locally to supported console systems.
* Advertise adapter capabilities.
* Receive signed, authorized commands.
* Validate show, user, role, mix, source, command, bounds, and expiration.
* Reject replayed commands.
* Send the command to the local adapter.
* Return acknowledgement or failure.
* Report heartbeat and health.
* Maintain a local audit queue during temporary internet loss.
* Reconcile events after reconnect.
* Support immediate local lockout.
* Never expose the console directly to the internet.

Security requirements:

* Device registration
* Rotatable device credentials
* Mutual authentication when supported
* Signed commands
* Nonces
* Short command expiration
* Replay protection
* Command allowlist
* Rate limiting
* Bounds validation
* Encrypted transport
* Secret redaction
* Local secure storage
* Remote revocation
* Automatic Request Mode fallback
* Local kill switch

## STAGE RACK

Design the software architecture so Stage Bridge can later run on a dedicated
Street Banker Stage Rack appliance.

The software should expose:

* Device identity
* Venue or tour ownership
* Network health
* Console connection
* Adapter status
* Software version
* Last update
* Last heartbeat
* Armed or disarmed state
* Emergency lockout
* Diagnostic export
* Remote-revocation state

Do not invent finished hardware capabilities. Treat the Stage Rack as a
deployable edge-computing target requiring separate hardware validation.

## SAFETY ENGINE

Create a centralized safety-policy service.

It must evaluate:

* Show mode
* User permission
* Engineer authorization
* Device state
* Adapter capability
* Mix ownership
* Source allowlist
* Command type
* Requested delta
* Rate of repeated changes
* Command age
* Current lock state
* Revert capability
* Show armed state

Default protections:

* Bounded incremental changes only
* Configurable maximum delta
* Rate limit per performer
* Rate limit per mix
* Rate limit per source
* No direct master-output changes
* No preamp changes
* No phantom-power changes
* No patch changes
* No routing-topology changes
* No system-processing changes
* No firmware or network changes
* No command when the show is disarmed
* No command after expiration
* No command when device state is stale
* Automatic Request Mode fallback

All safety rejections must be visible to the engineer and audited.

## DATA MODEL

Create or extend entities for:

* Artist
* Production
* Show Passport
* Passport version
* Passport document
* Personnel
* Production role
* Stage plot
* Stage-plot element
* Input
* Output
* Monitor mix
* Monitor source
* Equipment requirement
* Playback configuration
* Show cue
* Venue
* Room
* Show
* Show assignment
* Advance question
* Advance conflict
* Show-access token
* Stage request
* Request event
* Console manufacturer
* Console adapter
* Adapter capability
* Stage Bridge device
* Device registration
* Device heartbeat
* Device command
* Device acknowledgement
* Safety policy
* Lockout event
* Audit event

Use the existing tenant and membership models.

## API AND SERVICE LAYER

Create secure services for:

* Passport creation
* Passport editing
* Passport publication
* Passport comparison
* Show creation
* Show advancement
* Crew invitations
* QR access
* Stage plots
* Inputs and outputs
* Monitor mixes
* Performer requests
* Engineer review
* Connected commands
* Command acknowledgement
* Reversion
* Stage Bridge registration
* Device heartbeat
* Adapter capabilities
* Safety policies
* Lockout
* Audit history
* Production-document export

Add authentication, authorization, validation, pagination, filtering,
idempotency, and consistent errors.

## OFFLINE AND FAILURE BEHAVIOR

The show must remain understandable when connectivity fails.

Requirements:

* Stage Bridge may continue local health monitoring.
* New cloud commands must stop when authorization cannot be verified.
* The performer interface must show offline state.
* The engineer interface must show stale state.
* Pending requests must not be falsely marked applied.
* Duplicate commands must not be sent after reconnect.
* Locally queued audit events must reconcile safely.
* The engineer must be able to continue using the physical console.
* The application must automatically fall back to Request Mode when connected control is unreliable.

## EXPORTS

Generate clean production-ready exports for:

* Technical rider
* Show Passport
* Stage plot
* Input list
* Output list
* Monitor list
* Patch list
* Playback specification
* Show cues
* Venue advance
* Change report

Exports must include:

* Artist
* Show or passport version
* Publication date
* Last verified date
* Contact scope
* Page numbering
* Clear revision identifier

Do not expose private internal notes in external production exports.

## USER INTERFACE

Use the existing Street Banker design language.

The product should feel like serious touring infrastructure:

* Fast
* Dark-stage readable
* High contrast
* Minimal distraction
* Strong state visibility
* Clear human authority
* Clear device status
* Clear safety warnings
* Responsive on mobile, tablet, and desktop
* Accessible
* Operational rather than decorative

Do not use fake console meters or decorative audio visualizations.

## TESTING

Add automated tests for:

* Tenant isolation
* Role permissions
* Passport version immutability
* Show snapshot preservation
* QR expiration
* QR revocation
* Request authorization
* Mix ownership
* Realtime reconnect
* Duplicate-event handling
* Command idempotency
* Expired commands
* Replay attacks
* Safety bounds
* Rate limits
* Lockout
* Offline fallback
* Stage Bridge revocation
* Adapter capability enforcement
* Device acknowledgement
* Failed commands
* Reversion
* Audit history
* Simulator adapter
* Critical performer and engineer workflows

## IMPLEMENTATION PHASES

**Phase 1 — Repository and System Audit.** Inspect and document: stack,
authentication, tenant model, database, realtime infrastructure, existing
artist and show entities, UI system, background jobs, deployment, security
risks, reusable components. Continue implementation unless a destructive
decision or unavoidable conflict requires clarification.

**Phase 2 — Show Passport Foundation.** Passports, versioning, personnel,
stage plots, inputs, outputs, monitor mixes, playback, cues, documents,
production exports.

**Phase 3 — Show Advancement.** Shows, passport snapshots, crew assignments,
venue review, questions, conflicts, approvals, QR access.

**Phase 4 — Request Mode.** Performer interface, Engineer Desk, realtime
requests, manual application, status tracking, audit history, offline states.

**Phase 5 — Stage Bridge and Simulator.** Device registration, outbound secure
connection, capability registry, simulator adapter, signed commands,
acknowledgements, heartbeats, revocation, local audit reconciliation.

**Phase 6 — Connected Control Safety.** Safety-policy service, bounds, rate
limits, lockouts, arming, command expiration, replay protection, revert
workflow, automatic Request Mode fallback.

**Phase 7 — Production Hardening.** Security review, live-audio safety review,
performance review, accessibility review, tests, monitoring, documentation,
deployment validation, operational runbook.

Do not enable production console control until a specific adapter is
implemented and validated.

## ACCEPTANCE CRITERIA

The build is complete only when:

* A production team can create and publish a versioned Show Passport.
* A show retains its assigned passport version.
* A performer can submit a request from a mobile device.
* The request appears in realtime at the Engineer Desk.
* The engineer can acknowledge, modify, apply manually, reject, or approve it.
* Request states remain accurate.
* The simulator adapter can process supported bounded commands.
* Unsupported commands are rejected.
* Replayed and expired commands are rejected.
* Stage Bridge can be revoked.
* Emergency lockout immediately prevents connected commands.
* Internet loss does not falsely report successful changes.
* Request Mode remains usable without console integration.
* Tenant isolation and role authorization are tested.
* Existing Street Banker features continue working.
* Setup, security, deployment, and operating documentation are complete.

## REQUIRED FINAL HANDOFF

Provide: architecture summary; files created and changed; database migrations;
environment variables; realtime configuration; Stage Bridge setup; simulator
instructions; console-adapter contract; safety-policy documentation; test
commands and results; deployment steps; operational runbook; known limitations;
hardware or console validation still required; recommended next production
milestone.

Build the human workflow first, the safety system second, and connected
control only where real hardware support has been verified.

Show Passport carries the production memory. Stage Control turns requests into
accountable action.
