# IEEE TNSM submission and page-budget contract

Checked on 2026-08-10 against the current IEEE Communications Society author
guidelines and the IEEE Template Selector. This file separates journal rules
from project planning decisions; the latter are not represented as IEEE
requirements.

## Official journal requirements

- Target publication: *IEEE Transactions on Network and Service Management*
  (TNSM), original research article.
- Manuscript language: English.
- Abstract: 75--200 words. The internal target is 150--180 words so that the
  final abstract remains comfortably within the journal interval.
- The manuscript must contain a related-work section that identifies the
  relationship, improvements and novelty relative to appropriate references.
- The paper must use IEEE editorial and typographical standards and the IEEE
  Transactions article template.
- The first 10 two-column printed pages are free. The count includes the title,
  abstract, figures, tables, references, biographies and author photographs.
- Accepted papers longer than 10 printed pages incur a mandatory US$220 charge
  for each additional page, with an absolute maximum of 16 pages, unless a
  requested waiver is approved. Authors at academic institutions who can show
  that no funding source is available may apply within 30 days after the
  acceptance notice; this project does not assume approval.
- Every author needs an ORCID for submission and proof review.
- TNSM is hybrid: traditional submission has no open-access charge; the listed
  2026 open-access APC is US$2,800. The project does not select either route in
  advance of an author/funding decision.

Authoritative sources:

- [TNSM Policies and Guidelines](https://www.comsoc.org/publications/journals/ieee-tnsm/policies-guidelines)
- [IEEE Article Templates](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/authoring-tools-and-templates/tools-for-ieee-authors/ieee-article-templates/)

## Exact template-selector route

The interactive IEEE Template Selector was traversed on the check date with
the following choices:

1. `Transactions, Journals and Letters`
2. `IEEE Transactions on Network and Service Management`
3. `Original research and Brief`
4. `LaTeX`

The selector then displayed: “Please use this template when writing an original
research article or brief for IEEE Transactions on Network and Service
Management in LaTeX format.” This four-item route, rather than an inferred
generic class filename, is the frozen template identity for the manuscript.
No third-party template bytes are vendored in this repository. At the start of
typesetting, the package obtained through this route must be retained locally
with its download date and SHA-256 before any project-specific edits.

## Internal ten-page allocation

The project targets the 10-page no-charge route. This is a working allocation,
not a journal limit on individual sections.

| Component | Target printed pages | Content boundary |
|---|---:|---|
| Title, abstract and index terms | 0.4 | Abstract stays result-grounded and 150--180 words |
| Introduction and Related Work | 1.3 | Motivation, gap, closest antecedents and bounded contribution |
| Model, endpoints and theory | 0.9 | Hypergraph state, routing, stopping times and theory--experiment separation |
| Topology and experimental Methods | 2.3 | Frozen construction, matching, held-out design and inference contract |
| Results and figures | 2.6 | Formal phase, independent confirmation and essential sensitivity evidence |
| Discussion, limitations and conclusion | 0.8 | Scope, censoring, external validity and concise conclusion |
| References | 1.0 | Verified IEEE-formatted references only |
| Biographies, author pictures and production buffer | 0.7 | Reserved because these items count toward the journal total |
| **Total** | **10.0** | No page charge under the checked policy |

The Methods working draft is intentionally more complete than its 2.3-page
allocation. Compression is deferred until the formal and confirmation results
identify which implementation details must remain in the main text. Audit
tables, extended algorithms and reproducibility details may move to an
explicitly linked supplement or repository artifact, but endpoint definitions,
independent units, multiplicity, phase separation and claim boundaries must
remain in the article.

## Page-overrun decision gate

No manuscript may silently adopt an 11--16 page route. If an evidence-led
layout cannot meet 10 pages without harming reproducibility or interpretation,
the project must first produce a rendered page count, identify the exact
material that causes the overrun, calculate the resulting mandatory page
charge under the no-waiver assumption, and obtain an explicit author decision
about payment or an eligible waiver application. A waiver is not budgeted as
approved in advance. Sixteen pages remains a hard cap irrespective of funding.
