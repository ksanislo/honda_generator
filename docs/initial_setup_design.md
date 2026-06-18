# Initial Setup Design (deferred)

**Status:** Not implemented. This note captures the intended design so first-time
Bluetooth provisioning can be built consistently and safely later.

Today the integration assumes a generator that has **already been provisioned**.
Its connect path performs only authentication and reads, and never writes to the
generator's persistent configuration.

## Background: what "setup" means

A factory-fresh Bluetooth module is generic and not yet bound to a specific
generator. Provisioning involves at least three things:

- **Activation.** A never-set-up generator appears to ship with Bluetooth access
  **inactive** and rejects connections until a first-time setup activates it.
  Evidence: a user whose generator had no PIN, and who set the PIN to the default
  `0000` (i.e. made no real credential change), could only connect *after*
  completing first-time setup — indicating that setup **activates access**, not
  merely sets a password. First-time setup is currently performed in the
  manufacturer's app; this integration does not perform it.
- **Frame serial number** (`066B0005`): the 12-character identifier
  (`LLLL-DDDDDDD`) for the specific generator. On a fresh unit this may be blank.
- **Control sequence** (`066B0004`): the model-specific engine-control profile.
  Its first byte is a profile ID that must match the detected model; the remaining
  bytes configure control behavior.

The integration detects the **model** independently from the BLE advertised name
(the 4-letter serial prefix), so it always knows which generator family it is
talking to before reading any of the above.

## Current behavior (read-only connect)

On every connect the integration:

1. Authenticates (priming frame + owner unlock frame) — transient, not persisted.
2. Reads the frame serial (`066B0005`) for identity/model.
3. Reads the control sequence (`066B0004`); on a profile-ID mismatch it **logs a
   warning and does not write**.
4. Reads firmware version.

It deliberately does **not** write the serial or the control sequence, because:

- Rewriting the same value on every connect is unnecessary and consumes flash
  write cycles over the unit's life.
- It is unknown whether `066B0004` / `066B0005` are write-once or have side effects
  when rewritten on an already-provisioned unit. A wrong or mistimed write to a
  misidentified unit could be unrecoverable.

## Deferred: first-time setup flow

The gating prerequisite is **activation**, not PIN-setting: until a unit has been
activated it will not connect at all, so a full first-time-setup flow must
reproduce whatever activation does before serial registration or control-sequence
configuration is even reachable. The exact activation step is not yet identified.

Provisioning a fresh unit from the integration must be a deliberate, one-time
action with these guarantees:

### 1. Serial registration — write once, user-confirmed

- Detect a blank/invalid serial on connect (empty, or not matching
  `LLLL-DDDDDDD`).
- If blank, prompt the user for the 12-character frame serial (scanned or typed),
  validated as `^[A-Z]{4}-\d{7}$` and required to match the model prefix the
  advertised name reports — so a serial from a different model cannot be bound.
- Write the user-confirmed serial to `066B0005` **once**, in this explicit setup
  step, never on routine reconnects. Read back to confirm.

### 2. Control-sequence write — identity-guarded

- On a profile-ID mismatch, do **not** write blindly.
- First verify the unit's identity independently — read the engine/ECU machine
  code via the diagnostic channel and confirm it matches the expected value for
  the detected model. Only write the model's control sequence if that check
  passes; otherwise treat the unit as misidentified and abort without writing.
- This guards against writing the wrong engine-control profile to a unit that is
  not what we believe it to be.

### 3. PIN setting — remains inert

- Setting an owner/guest PIN stays disabled. In practice a lost PIN is
  unrecoverable without physically disassembling the generator to read an internal
  identifier, so we do not expose PIN setting until that risk is acceptable and the
  flow is validated on hardware. The protocol-level capability exists in the API
  (`change_password`) but is not reachable by users.

## Open questions

- **Activation step.** What first-time setup does to activate Bluetooth access is
  not identified. This is the prerequisite for any integration-owned setup flow and
  needs to be determined (ideally from logs of a genuinely un-activated unit) before
  the rest is worth building.
- **Blank-serial wire form.** The exact bytes a fresh `066B0005` returns (empty vs.
  null/space padding vs. prefix-only) should be confirmed from real logs of an
  un-provisioned unit before finalizing blank detection.
- **Expected machine codes.** The identity guard in (2) needs the expected
  engine/ECU machine code per model; these must be determined and stored.
- **Write-once uncertainty.** Whether `066B0004` / `066B0005` are genuinely
  write-once is unknown. The design avoids depending on the answer by writing only
  once, deliberately, with verification and read-back.
