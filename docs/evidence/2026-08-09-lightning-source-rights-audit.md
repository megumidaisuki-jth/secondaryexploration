# Lightning source rights and redistribution audit

**Checked:** 2026-08-09
**Contract:**
[`configs/lightning/source-rights-v1.json`](../../configs/lightning/source-rights-v1.json)

## Decision

Public accessibility is not treated as permission to redistribute a source.
The project keeps the 2020, 2022 and 2023 panels reproducible through stable
upstream identifiers, immutable hashes and strict readers, while raw
third-party files remain outside this repository. The 2026 capture is exactly
identified by retrieval metadata and SHA-256 but is not independently
obtainable after RGS cache rotation; it is therefore diagnostic-only under the
gate below.

| Panels | Rights evidence | Access route | Project policy |
|---|---|---|---|
| 2020 and 2023 | Harvard Dataverse dataset version 1.1 and DataCite both identify CC BY 4.0; file id 12510549 is unrestricted | Reused public dataset | Cite and attribute the versioned dataset; readers download the 562 MB archive from Dataverse |
| 2022 | Neither the frozen commit root nor the repository's current licence endpoint contains an explicit licence | Reused public third-party source without an explicit licence | Do not redistribute the topology archive or trace; point readers to the frozen upstream commit and verify both SHA-256 hashes |
| 2026 | The RGS server repository is dual MIT/Apache-2.0, but no explicit licence was found for the generated snapshot payload | Dynamic public service output without a persistent historical-capture URL | Do not redistribute the captured payload without permission; keep this panel diagnostic-only until the exact capture can be lawfully preserved or remove it from publication claims |

The 2022 and 2026 decisions are conservative provenance policies, not legal
conclusions about whether individual public graph facts are copyrightable.
They prevent the manuscript from silently extending a software licence to
third-party data or equating download access with redistribution permission.

## Evidence checked

### Harvard Dataverse

The version-specific Dataverse API reports version 1.1, release time
`2026-02-15T00:02:00Z`, licence `CC BY 4.0`, and unrestricted status for
`snapshots.geo.zip` (file id `12510549`). DataCite independently reports
`CC-BY-4.0`, dataset version 1.1, publication year 2025, and creators Danila
Valko and Jorge Marx Gómez. The exact archive MD5 and independently computed
SHA-256 remain frozen in the source manifest.

### Uploaded-paper repository

GitHub's commit and contents APIs resolve commit
`2c4ffc92d704fa1b043fac395c1e5f662990d497` and its two used files. The root
listing contains no `LICENSE`, `COPYING` or `NOTICE` file, and the repository
licence endpoint does not identify a licence. The paper itself remains cited
through DOI `10.1109/TNSM.2025.3542960`; that article citation does not create
a data-redistribution licence for the companion repository.

### Lightning Dev Kit RGS

LDK documents Rapid Gossip Sync as a semi-trusted server protocol that
preprocesses public Lightning gossip. The server repository licenses its
software under MIT or Apache-2.0. Because the licence text applies to files in
the software repository and does not state terms for produced snapshot
payloads, this audit does not extrapolate it to the captured binary response.

The server implementation also shows that it keeps a bounded set of current
scope snapshots, rebuilds the finalized snapshot directory, and maps the
zero-timestamp link to the then-current full snapshot. Consequently,
`/snapshot/v2/0` is not a persistent link to the bytes captured on 7 August
2026. Retrieval metadata and a SHA-256 digest prove what this project used but
do not make the historical bytes independently obtainable. A fresh retrieval
at `2026-08-09T15:32:57Z` produced 3,549,749 bytes with SHA-256
`31216098c18febe9d04a8d3f95266fac602d6f19ef76bf599912feb7c0132a51`,
which differs from the frozen capture.

## Manuscript boundary

The structural-panel Methods may state where every source came from, the
version or capture time, and the deterministic sampling contract. The Data
Availability statement must distinguish the CC BY Dataverse source from the
two no-explicit-data-licence routes. It must not promise that this repository
will redistribute all four raw panels. Until the RGS capture is lawfully
preserved under an explicit permission or data licence, the 2026 panel is
diagnostic-only and cannot support a submission claim requiring independent
reproduction from available data.

## Remaining publication action

Before submission, archive the project's own code, compact derived registries,
processed analysis tables and figure source data in a DOI-bearing repository
under an explicit project licence. The repository DOI and project-output
licence are not yet assigned and must not be invented in the manuscript.

Separately, obtain written permission or an explicit data licence allowing the
exact 2026 RGS capture to be deposited, or remove that panel from publication
claims. A current response from the dynamic RGS endpoint is not a substitute
for the frozen capture.
