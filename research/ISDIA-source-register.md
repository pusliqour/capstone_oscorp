# ISDIA evidence register

**Research date:** 24 October 2026
**Rule:** `verified` means directly supported by the cited source. `not found` is negative evidence, not proof that something never existed.

| Claim / artifact | Status | Source or local evidence |
|---|---|---|
| Venue identity: 11th International Conference on Information System Design and Intelligent Applications | verified | https://www.isdia.org/ and `research/sources/isdia-home.*` |
| Dates: 9–10 January 2027 | verified | official home and call-for-papers snapshots |
| Theme: Trustworthy AI—Governance, Risk and Responsible Innovation | verified | official home snapshot |
| Submission phases: 15 Sep, 15 Oct, 15 Nov 2026 | verified | official important-dates snapshot |
| Camera-ready length: 10–12 pages | verified | official submission-guideline snapshot |
| Submission portal | verified | https://cmt3.research.microsoft.com/ISDIA2027 |
| Publication target: Springer LNNS | verified as organizer statement | official submission guideline; final publication remains subject to review/registration/editorial acceptance |
| Word template package | verified/downloaded | `paper/Springer-Template-word.zip` |
| LaTeX template package | verified/downloaded | `paper/Springer-Template-latex.zip` |
| Current paper compiles | verified | `paper/jiran_isdia_2027.pdf`, 10 pages |
| 2025 proceedings | verified | https://doi.org/10.1007/978-981-97-4895-2 |
| Public official best-paper/winner list | not found | official site, proceedings metadata, Springer index, and targeted searches checked on research date |
| Historical Supabase dataset | unavailable | legacy hostname returned DNS resolution failure on research date |
| Reproducible validated AI metrics | unavailable/null | existing serialized artifacts fail to load under current dependency stack and no dataset lineage was recovered |
| Frontend production build | verified | `npm --prefix frontend run build` |
| Local auth/inventory round trip | verified | local Supabase service, migration, user/profile trigger, product/variation/inventory insert-select-cleanup smoke test |
| ERP import normalizer | verified | two passing unit tests in `tests/test_resource_import.py` |

## Submission decisions still requiring the professor/team

- Confirm author order, corresponding author, emails, and whether the professor is a co-author or acknowledgements-only contributor.
- Ask the organizer to reconcile the official site's venue wording: the masthead says Sofitel Dubai Jumeirah Beach, while descriptive text says UOWD campus.
- Confirm whether the site's `svmult` package is truly the required proceedings class despite the LNNS/LNCS guideline link.
- Approve the working title and architecture/recovery emphasis.
- Supply or approve a traceable dataset and evaluation protocol before any predictive-performance claim is added.
