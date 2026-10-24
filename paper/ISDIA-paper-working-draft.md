# Jiran: An Evidence-Aware Decision-Support Architecture for Resource Allocation and Inventory Redistribution

**Paper status:** 10-page Springer-style working draft compiled; author order/contact and experiments require confirmation
**Evidence freeze:** 24 October 2026
**Authors from the submitted capstone report:** Asmaa Fatima; Dania Nadeem; Hamdan Khan; Muhammad Abdul Mohsin; Yaasir Bin Muneer; Youssef Sami Mansi
**Academic advisor:** Dr. Farhad Oroumchian, University of Wollongong in Dubai

> This draft separates implemented software, intended architecture, and unverified AI claims. Bracketed `TODO` fields require author or experimental confirmation before submission.

## Abstract

Organizations operating across multiple locations often hold fragmented resource data in point-of-sale systems, spreadsheets, and local records. This fragmentation limits visibility and can produce simultaneous surplus and shortage across locations. Jiran is a web-based decision-support and exchange platform that consolidates inventory observations, classifies resource condition, and coordinates redistribution between participating operators. The graduation implementation combines a React interface, a PostgreSQL-compatible Supabase data layer, an optional point-of-sale import path, and a Python service designed for stock-state prediction and transfer or restock recommendations. This paper reframes the original small-retailer use case as a broader resource-allocation problem while retaining the implemented inventory workflow and marketplace. We describe the system architecture, source-neutral import contract, explainable allocation workflow, and a recovery design that replaces expired hosted dependencies with self-hosted open-source infrastructure. Historical hosted data were unavailable during recovery; therefore, model quality, operational savings, and prediction results are intentionally reported as null pending a reproducible evaluation dataset. The resulting artifact establishes a traceable foundation for evaluating whether cross-location redistribution can reduce avoidable shortages and surplus without overstating the current evidence.

**Keywords:** resource allocation; inventory redistribution; decision support; self-hosted information systems; demand forecasting; multi-location operations

## 1. Introduction

Resource imbalance is common in decentralized operations: one location may hold excess units while another experiences a shortage. The original Jiran capstone focused on UAE and Gulf-region retailers that lack integrated enterprise systems. Its core technical problem is more general: observations are fragmented across operational systems, local spreadsheets, and manual records, while allocation decisions require a consolidated view of quantity, location, demand, and availability.

Jiran addresses this problem through four linked capabilities: (1) consolidation of inventory observations, (2) stock-health analytics, (3) AI-assisted recommendation interfaces, and (4) a marketplace-style coordination mechanism through which participants can expose surplus and request resources. The contribution is not a new prediction algorithm in isolation. It is the integration of data ingestion, decision support, human review, and resource exchange in one workflow accessible to organizations that cannot deploy a large ERP implementation.

The recovered project also exposes an important engineering lesson. A prototype tied to free hosted services can stop functioning even when its source architecture remains intact. This paper therefore distinguishes the graduation prototype from a reproducible recovery architecture based on local/self-hosted Supabase and source-neutral ERP/CSV imports.

### 1.1 Research questions

- **RQ1:** How can fragmented multi-location inventory observations be normalized into a common resource-allocation model?
- **RQ2:** How can shortage, optimum, slow-moving, and surplus conditions be surfaced in an explainable operator workflow?
- **RQ3:** How can redistribution recommendations be coordinated through a human-controlled exchange mechanism?
- **RQ4:** What evidence is required before AI-generated recommendations can be claimed as reliable?

### 1.2 Contributions

1. A unified workflow joining inventory ingestion, condition monitoring, recommendations, and redistribution.
2. A source-neutral import contract that supports manual CSV and exports from open-source ERP platforms in addition to the original Square concept.
3. A self-hosted recovery architecture retaining the Supabase API contract while removing dependence on an expired free hosted instance.
4. An evidence boundary that leaves AI outcomes null until dataset lineage, training, and evaluation are reproduced.

## 2. Background and Related Systems

The capstone compared Jiran with Zoho Inventory, Oracle NetSuite, and SAP Business One, emphasizing accessibility, implementation complexity, analytics, and cross-organization redistribution. That analysis must be refreshed with peer-reviewed and current vendor sources before submission.

For the recovered implementation, self-hosted Supabase retains PostgreSQL, authentication, storage, and REST semantics used by the frontend. ERPNext and Odoo are relevant open-source operational systems that can provide inventory exports without making Jiran itself a replacement ERP. Jiran's role is the cross-location intelligence and coordination layer above those sources.

**TODO:** Complete systematic related-work search on multi-echelon inventory, lateral transshipment, dead-stock detection, explainable demand forecasting, and inter-organizational resource sharing.

## 3. System Definition

### 3.1 Actors and boundary

- **Operator/retailer:** owns operational inventory and decides whether to publish or request resources.
- **Location:** a store, warehouse, branch, lab, clinic, or other resource-holding unit.
- **Resource:** an item identified by SKU/category with quantity, price or valuation, and location.
- **Jiran:** consolidates observations, presents analytics, and coordinates proposed transfers.
- **External source:** Square, ERPNext, Odoo, or a spreadsheet/CSV export.

The original retail vocabulary remains the implemented reference domain. Generalization is limited to the conceptual resource and location model; it does not claim validated deployment in healthcare, manufacturing, or other domains.

### 3.2 Functional workflow

1. Register an organization and one or more locations.
2. Import inventory manually or through an external data source.
3. Display consolidated stock and sales observations.
4. Classify condition as low, optimum, excess, slow, or dead stock.
5. Generate candidate transfer/restock recommendations when a validated model is available.
6. Allow an operator to publish surplus or request stock.
7. Coordinate an exchange and maintain status history.

### 3.3 Current implementation status

| Capability | Repository evidence | Current recovery status |
|---|---|---|
| React interface and routes | Implemented | Builds successfully; lint debt remains |
| Authentication/profile calls | Supabase client calls implemented | Local self-hosted schema prepared |
| Inventory views and CSV import | Implemented | Available as non-AI recovery path |
| Square OAuth concept | UI/code references exist | Historical credentials unavailable; optional |
| ERPNext/Odoo import | New normalized adapter | Implemented and unit tested |
| Exchange/marketplace | Frontend and table contracts implemented | Local schema prepared; integration QA pending |
| ML API and saved artifacts | Repository artifacts exist | Legacy/unverified; not valid experimental evidence |
| Historical Supabase data | Hosted hostname does not resolve | Unrecovered |
| AI evaluation metrics | No reproducible evaluation identified | **null** |

## 4. Architecture

The interface is a React/Vite single-page application. A Supabase-compatible service supplies authentication, PostgreSQL storage, object storage, and REST access. A Python/FastAPI service contains stock-state and recommendation logic. Operational inputs arrive through manual upload or adapters. An exchange module exposes operator-approved surplus and requests to other participants.

The recovery deployment runs Supabase locally through its official self-hosting tooling, preserving the application's client library and minimizing changes. ERPNext/Odoo exports are converted into a stable factual contract (`sku`, `name`, `category`, `quantity`, `price`, `currency`, `location`). AI fields are excluded from that adapter.

See `architecture/jiran-high-level-architecture.html` for current and target-state diagrams.

## 5. Methodology

### 5.1 Dataset protocol

The original hosted database is unavailable. A replacement evaluation dataset must be accepted only with:

- provenance and usage rights;
- location and time coverage;
- documented missing-value treatment;
- separation of train, validation, and test periods;
- leakage checks across product and location identifiers;
- a non-AI baseline.

Until this protocol is met, dataset counts, prediction accuracy, forecast error, and business impact remain null.

### 5.2 Proposed evaluation

- **Prediction:** macro-F1 and per-class precision/recall for stock-state classification.
- **Forecasting:** MAE, RMSE, and MAPE where denominator conditions are documented.
- **Allocation:** units of shortage resolved, surplus units moved, holding-time reduction, and transfer distance/cost.
- **System:** import success rate, API latency, failed synchronization rate, and operator task completion.
- **Human factors:** explanation usefulness and recommendation acceptance under a defined study protocol.

Baselines should include reorder-point logic, recent-sales moving average, and no-transfer operation.

## 6. Results

| Measure | Value | Status |
|---|---:|---|
| Historical records recovered | 0 | Original host unreachable |
| Reproducible training dataset | null | Awaiting authorized source data |
| Classification macro-F1 | null | Not evaluated |
| Forecast MAE/RMSE/MAPE | null | Not evaluated |
| Allocation improvement | null | Not evaluated |
| Operational user study | null | Not conducted |

The absence of results is deliberate. Existing serialized model files and JSON outputs demonstrate prior implementation work but do not establish reproducible quality without lineage, training configuration, held-out data, and evaluation logs.

## 7. Discussion

Jiran's strongest defensible contribution is the integration pattern between fragmented operational data, transparent resource condition, and human-approved redistribution. The marketplace is not merely a sales feature: it is a coordination layer for moving resources from surplus to need. This framing generalizes the problem without discarding the project's implemented retail workflows.

The recovery also shows that portability is a research-quality requirement. Keeping the Supabase protocol while shifting from an expired hosted project to a local open-source deployment reduces code churn. A source-neutral import adapter similarly prevents Square from becoming the only path to operational data.

## 8. Limitations and Threats to Validity

- The original hosted database is unavailable; prior record counts cannot be verified.
- Repository model artifacts lack sufficient experiment lineage for paper claims.
- The initial implementation is retail-oriented; broader-domain applicability is conceptual, not experimentally validated.
- Local recovery does not yet demonstrate production security, scale, or multi-tenant governance.
- External POS/ERP behavior has not been tested against live production accounts.
- The author list, affiliation format, ethics requirements, and venue template remain subject to official ISDIA confirmation.

## 9. Conclusion and Next Steps

Jiran combines consolidated inventory visibility, AI-ready decision support, and participant-controlled redistribution. The project has been reframed as a general resource-allocation system while preserving the original capstone's inventory and marketplace design. Recovery work removes hard dependence on expired hosted services and creates a source-neutral ingestion path. The immediate research priority is not to claim model success, but to establish a traceable dataset, reproduce training, compare against simple baselines, and evaluate allocation outcomes. Only then should the null result fields in this draft be replaced.

## Acknowledgment

The authors acknowledge the guidance of Dr. Farhad Oroumchian and the University of Wollongong in Dubai capstone program. **TODO:** confirm exact institutional wording and funding/conflict declarations.

## References — working list

1. Team Oscorp, *CSCI321 Capstone Project Final Report: Jiran*, University of Wollongong in Dubai, Apr. 2026. [Primary project artifact.]
2. Supabase, “Self-Hosting,” official documentation. https://supabase.com/docs/guides/self-hosting
3. Supabase, “supabase/supabase,” official source repository. https://github.com/supabase/supabase
4. Frappe Technologies, “ERPNext,” official source repository. https://github.com/frappe/erpnext
5. Odoo S.A., “Odoo,” official source repository. https://github.com/odoo/odoo

**TODO:** Replace/extend this working list with peer-reviewed related work and format it according to the verified ISDIA template.
