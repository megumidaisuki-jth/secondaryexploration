# Methods citation claims

This ledger separates a citation's bibliographic identity from the exact claim
it is allowed to support. It is intentionally narrower than a general related-
work bibliography.

| ID | Manuscript claim | Preferred source | Support boundary |
|---|---|---|---|
| M001 | The uploaded study introduced HPNs and the NCH/FHS constructions used as paper-2 baselines. | Kotzer et al., 2025, `10.1109/TNSM.2025.3542960` | Strong support for provenance and published definitions; it does not validate paper-2's corrected closed-neighborhood NCH or new reliability conclusions. |
| M002 | The frozen NCH cover routine belongs to the local-ratio vertex-cover tradition. | Bar-Yehuda and Even, 1985, `10.1016/S0304-0208(08)73101-3` | Strong support for the local-ratio approximation method; the canonical ordering and closed-neighborhood transformation are study-specific. |
| M003 | Fixed-edge ER-GNM is a standard random-graph ensemble. | Erdos and Renyi, 1959, *On Random Graphs I* | Original support for the fixed-edge random-graph model; connectivity conditioning, equal edge counts and rejection replay are study-specific. |
| M004 | Preferential attachment motivates the BA structural stratum. | Barabasi and Albert, 1999, `10.1126/science.286.5439.509` | Strong support for growth with preferential attachment; the star initialization and `m=3` freeze are study-specific. |
| M005 | A stochastic block model represents block-dependent connection structure. | Holland, Laskey and Leinhardt, 1983, `10.1016/0378-8733(83)90021-7` | Strong support for stochastic block modelling; the fixed-count construction and exact block totals are study-specific. |
| M006 | Right-censored event records can define a nonparametric survival curve. | Kaplan and Meier, 1958, `10.1080/01621459.1958.10501452` | Strong support for the product-limit estimator; the formal primary analysis does not currently estimate a Kaplan-Meier curve. |
| M007 | Restricted mean survival time is an interpretable time-to-event functional under a fixed horizon. | Royston and Parmar, 2013, `10.1186/1471-2288-13-152` | Method background only: paper-2's primary normalized restricted no-path time is a paired discrete endpoint, not a clinical-trial RMST analysis. |
| M008 | Nonparametric bootstrap resampling supplies an empirical sampling distribution. | Efron, 1979, `10.1214/AOS/1176344552` | Foundational bootstrap support; resampling parents within model strata, shared contrast indices and Bonferroni tails are paper-2's frozen design. |

## Insertion rule

Use M001-M005 in the topology-construction and synthetic-parent subsections.
Use M006-M008 only where the manuscript discusses derived survival summaries
or the bootstrap. Never cite M006 or M007 as evidence that the registered
lower quantile is numerically estimable: that quantile remains an
identifiability-only diagnostic.
