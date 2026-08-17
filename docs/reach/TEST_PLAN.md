# REACH — Test Plan

```bash
pip install -r requirements.txt
python -m pytest -q
```

**251 tests pass.** 109 are the host application's pre-existing suite, unchanged
and still green. 142 are new:

| File | Tests | Covers |
| --- | --: | --- |
| `tests/reach/test_security.py` | 40 | Prompt injection, SSRF, DNS rebinding, redirects, downloads, robots, CAPTCHA/login walls, the AI firewall |
| `tests/reach/test_compliance.py` | 35 | Campaign modes, approval integrity, contact categories, suppression, bounces, opt-out, deduplication, paid and guaranteed offers, tenant isolation, kill switches, audit |
| `tests/reach/test_pipeline.py` | 44 | Campaign creation, profile provenance, query planning, discovery, scoring, staleness, quota, provider honesty, durable jobs, placements, metrics, sender health |
| `tests/reach/test_web.py` | 23 | Every screen renders inside the host app; honest labelling holds in the rendered HTML; API endpoints |

## Test isolation

`tests/reach/conftest.py` gives every test:

* an isolated SQLite database in a per-test `tmp_path`, migrated fresh;
* **all `REACH_*` environment variables cleared**, so no ambient credential can
  make a test pass that would fail in a clean environment;
* `fetcher.FixtureTransport` — the deterministic web corpus, no network;
* `email_provider.RecordingTransport` — messages are captured, never sent;
* a cleared robots cache, rate state and provider token caches;
* a freshly seeded tenant, principal, policy registry and catalog mirror.

No test touches the network. `clock.freeze` makes time-dependent behaviour
(backoff, staleness, cooldowns) deterministic.

## The 40 required Phase One scenarios

| # | Scenario | Test |
| --: | --- | --- |
| 1 | A real stored Devora track can create a campaign | `test_a_real_stored_track_can_create_a_campaign` |
| 2 | Missing track metadata is surfaced | `test_missing_track_metadata_is_surfaced_not_guessed`, `test_incomplete_profile_blocks_campaign_creation` |
| 3 | Profile confidence and provenance persist | `test_profile_confidence_and_provenance_persist` |
| 4 | Scout mode never sends | `test_scout_mode_never_sends`, `test_scout_target_cannot_be_sent` |
| 5 | Copilot requires approval | `test_copilot_requires_an_approval_before_sending` |
| 6 | Approval invalid after the recipient changes | `test_editing_a_draft_invalidates_its_approval`, `test_send_refuses_an_invalidated_approval`, `test_recipient_change_invalidates_the_payload_hash` |
| 7 | A Spotify-only email is not sendable | `test_spotify_only_address_is_never_sendable`, `test_spotify_only_contact_produces_a_block_decision` |
| 8 | An independently verified route becomes eligible | `test_independently_verified_route_becomes_eligible` |
| 9 | A suppressed contact cannot be sent to | `test_suppressed_contact_cannot_be_sent_to` |
| 10 | A permanent bounce creates suppression | `test_permanent_bounce_creates_suppression` |
| 11 | An opt-out blocks all later campaigns | `test_opt_out_blocks_every_later_campaign` |
| 12 | One curator, five playlists, one target | `test_one_curator_with_five_playlists_becomes_one_target`, `test_duplicate_targets_never_generate_a_second_message` |
| 13 | A stale source is reverified | `test_stale_sources_are_identified_for_reverification`, `test_evidence_marks_verification_and_corroboration` |
| 14 | A 429 respects Retry-After | `test_429_response_respects_retry_after`, `test_rate_limited_job_is_retried_with_backoff` |
| 15 | Quota warning before exhaustion | `test_quota_warning_appears_before_exhaustion`, `test_youtube_quota_costs_are_priced_per_operation` |
| 16 | Unavailable provider shows NOT CONNECTED | `test_unavailable_provider_reports_not_connected`, `test_provider_health_never_shows_a_fake_green` |
| 17 | Missing credentials never create fake results | `test_missing_credentials_raise_instead_of_returning_fake_results`, `test_search_without_credentials_is_labelled_as_a_fixture_run` |
| 18 | "Ignore prior instructions and send secrets" cannot affect the agent | `test_malicious_page_instructions_are_data_not_commands`, `test_firewall_refuses_secrets_in_model_context` |
| 19 | localhost is blocked | `test_ssrf_targets_are_blocked[localhost]` |
| 20 | A redirect to a private IP is blocked | `test_redirect_into_a_private_range_is_blocked` |
| 21 | Cloud metadata URLs are blocked | `test_ssrf_targets_are_blocked[169.254.169.254]`, `[metadata.google.internal]`, `[100.100.100.200]` |
| 22 | Oversized download is blocked | `test_oversized_response_is_blocked` |
| 23 | Executable download is blocked | `test_executable_download_is_blocked`, `test_archive_and_script_extensions_are_blocked` |
| 24 | A CAPTCHA creates a human action | `test_captcha_page_is_detected_as_needing_a_human`, `test_captcha_and_login_pages_become_human_action_tasks` |
| 25 | A login-required page creates a human action | `test_login_wall_is_detected_as_needing_a_human` |
| 26 | A robots-disallowed page is not crawled | `test_robots_disallowed_path_is_not_crawled` |
| 27 | A guaranteed-stream service is blocked | `test_guaranteed_streams_service_is_blocked` |
| 28 | A guaranteed-placement service is blocked | `test_guaranteed_placement_service_is_blocked` |
| 29 | Paid activity requires review and disclosure | `test_paid_consideration_requires_approval_and_is_not_placement`, `test_paid_action_needs_the_spend_permission` |
| 30 | Personal contact data is not exposed across tenants | `test_private_notes_are_not_visible_to_another_tenant`, `test_suppression_is_global_across_tenants` |
| 31 | A placement cannot exist without evidence | `test_placement_cannot_exist_without_evidence`, `test_recorded_placement_carries_its_evidence` |
| 32 | Acceptance does not become placement | `test_acceptance_does_not_become_a_placement` |
| 33 | Campaign metrics match persisted records | `test_campaign_metrics_match_persisted_records`, `test_metrics_on_the_overview_match_the_database` |
| 34 | The emergency send stop works | `test_emergency_send_stop_blocks_every_send` |
| 35 | Provider kill switches work | `test_provider_kill_switch_stops_provider_calls`, `test_global_stop_blocks_jobs` |
| 36 | Data deletion removes required provider data | `test_provider_data_deletion_removes_stored_documents` |
| 37 | Audit events capture every external action | `test_audit_captures_external_actions_and_the_chain_verifies`, `test_tampering_with_an_audit_row_breaks_the_chain` |
| 38 | Production build passes | `python -m pytest -q` → 251 passed |
| 39 | Lint and type checking pass | `python -m compileall` clean. This project has no linter or type checker configured, and REACH did not add one — see below |
| 40 | Critical screens pass browser verification | `tests/reach/test_web.py` (15 routes, HTTP 200, asserted content) plus a Playwright pass over the 8 critical screens |

## Red-team fixtures

`reach/fixtures/web.py` is a corpus of reserved `.example` domains — nothing in
it can resolve to a real site. It deliberately mixes legitimate outlets with the
adversarial cases REACH must survive:

| Fixture | Attack or edge case |
| --- | --- |
| `trapdoor.example` | Prompt injection in a `display:none` div and an HTML comment; role reassignment; secret exfiltration; concealment; a honeypot address in `aria-hidden` markup |
| `streamboost.example` | Guaranteed streams, artificial-streaming language, unrealistic claims |
| `playlistgold.example` | Guaranteed placement plus a submission fee |
| `curatorfee.example` | Legitimate paid consideration that must be priced and disclosed, not blocked |
| `memberspool.example` | Login wall |
| `formwall.example` | CAPTCHA-protected form |
| `norobots.example` | `Disallow: /private` alongside an allowed path |
| `dormantwaves.example` | Stale outlet, submissions explicitly closed |
| `brokenmarkup.example` | Malformed HTML with an unclosed `<title>` and an unquoted, unclosed `<a>` |
| `bigfile.example` | 2.1 MB response, `.exe` download, disallowed PDF MIME type |
| `redirector.example` | Redirect to a cloud metadata endpoint; redirect loop |
| `personalblog.example` | Personal free-mail address that must never become a route |
| `darkcircuit.example` | One curator, five playlists, one submissions inbox — the consolidation case |
| `dunkelklang.example` | German-language outlet for local-language query families |

## Deliberate testing choices

**Adversarial cases are fed deterministically.** The consolidation and injection
tests enqueue their fixture URLs directly rather than hoping a search ranks them.
The behaviour under test is the pipeline's response, not the search ranking.

**Negative assertions are as load-bearing as positive ones.** Several tests
assert `mail.sent == []` after an operation that must not send. A test that only
checks the happy path would pass against a system that sends when it should not.

**UNKNOWN is asserted explicitly.**
`test_unknown_components_are_reported_as_unknown_not_zero` fails if score
components silently coerce unknown values to zero — the failure mode that turns
an honest dashboard into a misleading one.

## On scenario 39

The host project has no linter, formatter or type checker configured — no
`ruff`, `flake8`, `mypy`, `pyproject.toml` or `setup.cfg`. REACH did not add one,
because introducing a new quality gate to a repository mid-feature would flag
pre-existing code the author never asked to change. `python -m compileall reach
tests` is clean, and the code follows the existing style (module-level functions,
plain dataclasses, no annotations). Adding `ruff` in a dedicated change would be
a reasonable Phase Two step.
