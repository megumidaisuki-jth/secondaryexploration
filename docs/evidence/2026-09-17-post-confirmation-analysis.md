# Post-confirmation analysis handoff — 2026-09-17

The Confirmation simulation has completed all 240 blocks. On 2026-09-16 the
frozen scheduler completion replay returned exit code 0. The streaming
finalizer subsequently published the Confirmation summary and finalization
witness. This document records the next analysis launch, not completion of the
paper's reporting gate or an independent audit.

## Verified inputs

On 2026-09-17 the supervisor preflight rehashed all 480 Formal/Confirmation
raw block files and matched them to their respective finalization byte
registries. Both summaries passed the frozen summary loader; witness content
fingerprints, manifest identities, summary identities, execution revision and
analysis revision agreed. Both output directories had empty/absent block locks
and temporary directories. No active global simulation lease or analysis
process existed before launch. The fixed Python runtime reports 3.12.13 and
environment fingerprint
`0a499b6a1334446fa6bf02a02b25e80934a22689168d6282a2ccb067ac6216c3`.

| Saved input | SHA-256 |
| --- | --- |
| Confirmation summary | `01b3be66ea92f81fbd1ae5733409bd044a76d0919ce51f0279a86d1c8b90bb3b` |
| Confirmation finalization witness | `8a654d920f849c0ad5a52153a00ba2b7b14d194509c0bae79f854c1f989621fb` |
| Formal summary | `eec741b362cd86b3c3678bfe9b5f5b2ff8d6a5b731671567957091dadc26236d` |
| Formal phase evidence (bytes only) | `853ea5fb14a16ce246285acaa011582cde324deabfcac528941a51343aae6d9e` |

The scientific package still matches revision
`425710a418b1b28e6c5cd813dff18aeeaa6303c3`; inference tooling matches
`9ecaadec84f8bebe799fb507969de8e0a0947b66`; projection tooling matches
`a85c952afa120f86a9ace96a031819c0d131d2b4`. No scientific endpoint was displayed
to perform this preflight.

## Execution sequence and records

`tools/post_confirmation_pipeline.py` supervises the four unchanged commands
from section 8 of
`docs/plans/2026-08-11-formal-to-confirmation-transition-runbook.md`, in order:

1. Confirmation phase evidence: `results/inference/confirmation-phase-evidence.json`.
2. Formal descriptive projection: `results/inference/formal-descriptive-mechanism-v1.json`.
3. Confirmation descriptive projection: `results/inference/confirmation-descriptive-mechanism-v1.json`.
4. Cross-phase replication evidence: `results/inference/formal-confirmation-replication-evidence.json`.

The supervisor records full commands, child PIDs, start/end timestamps, exit
codes, stdout/stderr hashes, source-context hashes and output sizes/hashes in
`results/diagnostics/post-confirmation/20260917-v1/`. It stops on any failed
command. An operating-system lock prevents simultaneous supervisor instances.
On a later supervised resume it skips a successful stage only if the command,
input context and output hash agree with its saved receipt. After an abnormal
supervisor exit, inspect child processes before attempting a resume; a child
may still be running. Do not remove files or receipts to force a resume.

The Windows task `SecondaryExploration-PostConfirmation-20260917` is on-demand,
with no scheduled trigger and no execution time limit. It runs the supervisor
through `tools/launch_post_confirmation.ps1`, using a hidden process with
separate timestamped startup stdout/stderr logs. The first direct task attempt
ended during preflight with Windows status `0xC000013A` (interrupted); no
analysis child was launched in that attempt. The hidden launcher is the second
attempt, after checking that the first process had exited.

This decouples analysis execution from the chat's terminal lifetime.
`status.json` describes current
execution only; it is not a scientific validation certificate. Completion of
all four commands is labelled `generated-pending-independent-replay`.

The saved small summaries are indexes into raw block evidence. Later frozen
analyses still replay raw blocks and may take substantial time; generation
does not rerun the original simulated experiments. Cumulative I/O alone does
not establish which internal validation stage is running or its percentage
complete.

## Remaining reporting gate

Generation receipts are operational evidence, not independent reviews. Before
scientific interpretation or manuscript population, independently replay both
summaries, phase evidence, descriptive projections and replication evidence as
required by the frozen runbook. Then produce the complete Source Data export,
including all registered contrasts, coverage/activity cells and 13 descriptive
metrics. Preserve exact fractions and both phases without pooling.

Archive and push the generated files and endpoint-free receipts using an exact
path list after verification. The prior 240-block Confirmation LFS archive
remains at commit `dc20a92851f8f1ff9729ed4ede93bcee9be4e146`; this analysis
launch does not imply that the future derived outputs already exist remotely.
