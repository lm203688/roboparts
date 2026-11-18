# Literature Notes — verbatim quote and intended use per entry

Order: Tola 2022 first (spec §5 mandate), then the remaining entries in the same order as references_verified.md.
Section tags: **2.1** system configuration / integration; **2.2** information models; **2.3** marketplace & catalogue audits; **2.4** partial-constraint / three-valued / placeholder reasoning; **2.5** what the literature still lacks.
Quotes are verbatim from the opened source; where only the title page was reachable, the quoted line is the title-page wording and this is noted.

---

## 1. Tola2022 [MANDATED, lead-off]
> "To our knowledge, no mature public robot system configurators exist, leaving the task of configuration up to experienced system integrators."
- Use: **2.1 / 2.5** — anchors the gap statement: configuration practice rests on integrator experience, not on public tooling; our audit quantifies why (interface fields absent).
- Also usable: "Currently, only the robot flange is standardised in ISO 9409-1" → **2.2** (scope of the only mechanical standard).

## 2. Zamalloa2018 (HRIM)
> "in robotics there is currently no leading candidate for a global plug-and-play standard."
- Use: **2.2** — HRIM is the closest published information model; our audit (21 class models, 0 mechanical-mating fields, 0 connector-level electrical fields) shows it operates at message level, not at connector level.

## 3. Siltala2019
> "Interface matchmaking method evaluates if the proposed set of resources can be connected physically together. It utilizes the formalized interface information provided by the resource descriptions."
> Also from the same paper: "At first, coarse level matching analyses only the interface identifier (ID) and the gender information. The second level is fine level matching, which uses additionally the interface characteristics information and associated rules"
- Use: **2.2 / 2.3** — the capability-matchmaking line presumes formalized interface descriptions exist as input; our corpus shows that premise fails on 528/553 unknown electrical ports. The two-level coarse/fine matching is the nearest prior ladder; its levels both assume the description is declared, whereas ours measures how decidability degrades when it is not.

## 4. Zheng2019
> Title-page wording: "Interface Model-Based Configuration Design of Mechatronic Systems for Industrial Manufacturing Applications." (full text closed; quote is title-page verbatim)
- Use: **2.2** — prior interface-model configuration work in RCIM; contrast: it models interface types for design configuration, not catalogue-level decidability of off-the-shelf end arms.

## 5. Chaumet2023
> "Creating a design from modular components necessitates three steps: Acquiring knowledge about available components, conceiving an abstract design concept, and implementing that concept in a concrete design."
- Use: **2.1 / 2.2** — knowledge-driven synthesis treats component knowledge acquisition as a solved input; we measure what happens when that knowledge is structurally incomplete.

## 6. Tola2024thesis
> "In the first area, related to acquisition, a constraint-based configurator is demonstrated that resolves compatibility challenges between robot devices"
- Use: **2.1 / 2.4** — the thesis's own URDF analysis shows the dominant robot description format carries kinematics/visuals, not connector mating; the configurator route still needs declared ports.

## 7. Tola2021RoboCIM
> "We formalise the model within a defeasible reasoning framework, in order to explicitly capture cases where information is missing or is obtained from the system integrators' experience."
- Use: **2.4** — defeasible/ASP handling of missing information is the reasoning counterpart to our ELEC:UNKNOWN placeholder treatment.

## 8. Sanneman2020
> "Robot programming interfaces and communication protocols are not currently standardized, and this—along with robot hardware and specifications that differ between companies—adds to the integration challenges."
- Use: **2.1** — corroborates from the industry side (interviews with manufacturers, integrators, OEMs) that missing hardware standardisation is the field's own stated challenge.

## 9. Jarvenpaa2018
> "Capability-based matchmaking aims to support rapid design and reconfiguration of modular plug-and-produce type production systems."
- Use: **2.2** — the ontology side of the Tampere line; pairs with Siltala2019 as the formal-description baseline our catalogue audit benchmarks against.

## 10. Mital2019
> "Such matchmaking is currently time consuming and heavily dependent upon designer's experience."
- Use: **2.3** — prior work itself admits the bottleneck; our audit shows why automation stalls at the electrical axis.

## 11. Siltala2016
> "These descriptions are source of formal information for (automatic) production system design and (re-)configuration."
> Also from the same paper: "The objective of ARD is to enable compatibility, interchangeability and connectivity between different production resources, through harmonisation and grouping of interfaces specifications across different types of resources."
- Use: **2.2** — earliest Tampere formal-resource-model anchor (ARD/RD/RID three levels); cite as the lineage root of entries 9–13. The quoted objective is exactly the "harmonisation of interface specifications" our audit finds undeclared in public catalogues.

## 12. Jarvenpaa2017
> Title-page wording: "Capability matchmaking procedure to support rapid configuration and re-configuration of production systems." (title-page verbatim)
- Use: **2.2** — the procedure layer between ontology (2018) and web tool (2019).

## 13. Siltala2018interfaces (IPAS)
> "It also proposes an interface matchmaking method, which uses this information to judge if two resources can be physically connected with each other."
- Use: **2.2** — the IPAS-tagged record mandated by spec §5; most explicit prior claim that hardware-interface descriptions drive physical-connection judgement. Its two coarse/fine levels (interface ID + gender, then interface characteristics) are the nearest prior ladder — again premised on declared descriptions, which our corpus shows missing.

## 14. ISO9409-1:2004
> "It is intended to ensure the exchangeability and to keep the orientation of hand-mounted end effectors. It does not define other requirements of the end effector coupling device."
- Use: **2.2 / 2.3** — the standard itself declares its own boundary: plates only, no electrical/connector content; this is the textual basis for "flange is mechanical-only".

## 15. URplus2026
> "Explore our ecosystem of trusted UR Partners and find the products you need to complete your cobot solution."
- Use: **2.3** — the marketplace landing page exists; our audit of 528 products finds 0 interface fields, i.e. the ecosystem page does not expose what compatibility needs.

## 16. Ulrich1995
> "Product architecture is the scheme by which the function of a product is allocated to physical components."
- Use: **2.1** — vocabulary for why flange/port allocation is an architecture decision, not a datasheet accident; supports the suite-attribute argument.

## 17. Mehrabi2002
> "RMS (which can provide exactly the capacity and functionality needed, exactly when needed) is a desirable next step in the evolution of production systems."
- Use: **2.1** — reconfigurability as the demand-side motivation; contrast: reconfiguration literature assumes the interface layer that our audit finds undeclared.

## 18. OnRobotQC2024
> "Quick Changer combines fast manual tool changes, low weight and a secure ISO 9409-1 interface for compatible robot and tool setups."
- Use: **2.3** — vendor page confirms the changer, not the device, carries the ISO 9409-1 interface; evidence for "flange as suite attribute".

## 19. SabinFreuder1996 [MANDATED, corrected 2026-11-09]
> Title-page wording: "Configuration as Composite Constraint Satisfaction." (verbatim citation line from the AAAI workshop reference index; paper body not opened)
- Use: **2.4** — configuration formalised as a composite (hierarchical + dynamic + meta) CSP; the formal counterpart to our device-level variable that only activates once a port is declared. [Earlier draft mis-recorded this entry as an IEEE Expert paper title that no open record supports; corrected to the workshop paper.]

## 20. CiucciDubois2013 [MANDATED]
> "Here, we focus on the case where the third truth-value means unknown, as suggested by Kleene."
- Use: **2.4** — formal grounding for the unknown/unknown placeholder pairing (ELEC:UNKNOWN × ELEC:UNKNOWN) as a third truth value, not as a missing data point.

## 21. MittalFalkenhainer1990 [MANDATED]
> "However, for many synthesis tasks such as configuration and design, the set of variables that are relevant to a solution may change dynamically over the course of problem solving."
- Use: **2.4** — dynamic CSP / activity constraints as the formal model for devices that only become relevant once a port is declared.

## 22. FreuderWallace1992
> Title-page wording: "Partial Constraint Satisfaction." (title-page verbatim; no abstract deposited)
- Use: **2.4** — the founding partial-constraint reference; cite when framing decidability as a thresholded, not binary, notion.

## 23. Schiex1995
> "In this paper, we consider a simple algebraic framework, related to Partial Constraint Satisfaction, which subsumes most of these proposals and use it to characterize existing proposals in terms of rationality and computational complexity."
- Use: **2.4** — soft/valued constraints as the formal counterpart to our graded evidence thresholds D0–D3; the paper itself frames its VCSP as equivalent to Freuder & Wallace's partial consistency view.

## 24. Dubois1996
> "In a Fuzzy Constraint Satisfaction Problem (FCSP), a constraint is satisfied to a degree (rather than satisfied or not satisfied) and the acceptability of a potential solution becomes a gradual notion."
- Use: **2.4** — degree-satisfaction language matches the ladder: compatibility is graded by evidence threshold, not yes/no.

## 25. Brewka2011
> "The motivation and key concepts behind answer set programming—a promising approach to declarative problem solving."
- Use: **2.4** — ASP as the default-reasoning tool Tola2022/2021 already prototype; cite for the formal route to placeholder handling.

## 26. Felfernig2014
> "Knowledge-based Configuration incorporates knowledge representation formalisms to capture complex product models and reasoning methods to provide intelligent interactive behavior with the user."
- Use: **2.1 / 2.5** — the field's consolidated configuration-engineering baseline; its scope is product models, not catalogue-level interface decidability.

## 27. ConfWS2024 [MANDATED]
> "14 papers were selected for publication in the workshop proceedings after a review by three independent reviewers per paper."
- Use: **2.5** — state of the configuration-research frontier (2024): LLM-assisted, green, learning-based configuration; no paper in the TOC audits interface-field completeness of a marketplace.

## 28. WangStrong1996
> "their improvement efforts tend to focus narrowly on accuracy."
- Use: **2.3** — data-quality dimensions (intrinsic/contextual/representational/accessibility) as the audit vocabulary for why "accuracy" alone misses incompleteness of interface declarations.

## 29. Redman1998
> Title-page wording: "The impact of poor data quality on the typical enterprise." (title-page verbatim; ACM DL opened, abstract not rendered)
- Use: **2.3** — cost-of-poor-data framing for why undeclared interface fields are an enterprise-level loss, not a cosmetic gap.

## 30. Jarvenpaa2019implementation
> Title-page wording: "Implementation of capability matchmaking software facilitating faster production system design and reconfiguration planning." (publisher record opened; abstract not rendered)
- Use: **2.2** — the software-implementation layer of the Tampere matchmaking line; shows the method is operationalised, not just modelled — strengthening the contrast that its input (formal resource descriptions) does not exist in public catalogues.

## 31. Jarvenpaa2019ontologyJIM
> Title-page wording: "The development of an ontology for describing the capabilities of manufacturing resources." (publisher record opened; abstract not rendered)
- Use: **2.2** — the MaRCO ontology baseline; cite as the formal-description ideal our catalogue audit benchmarks against.

## 32. TolaCorke2024urdf
> "Despite URDF being an important and ubiquitous file format, it lacks the rigour of a formal standard."
- Use: **2.2 / 2.3** — the closest methodological precedent to ours: an audit-style dataset study (322 URDF files, 195 unique models) exposing description-quality problems in the de-facto robot format; ours performs the same audit on interface declarations, where the gap is structural rather than stylistic.

## 33. TolaCorke2023urdfsurvey
> Title-page wording: "Understanding URDF: A Survey Based on User Experience." (OpenAIRE record opened)
- Use: **2.3** — user-side evidence that description formats are already known to be inconsistent before connectors are even considered.

## 34. ISO11593_2022
> "Automatic exchange systems for end effectors increase in importance for handling devices." (ISO/DIS 11593:2019 scope)
- Use: **2.2 / 2.3** — the tool-changer standard defines vocabulary and presentation of characteristics (forces, moments, exchange times) and explicitly "does not contain any details for the development and design" of the systems: evidence that the standards boundary stops at the changer, never reaching device-side connector pinouts.

## 35. OnRobotHEXmanual
> "sensor cable (4 pin M8 - 4 pin M8, 5 m)" (Scope of Delivery); mounting section lists adapters A2/B2/C2 for ISO 9409-1-50-4-M6, ISO 9409-1-31.5-7-M5 and ISO 9409-1-40-4-M6.
- Use: **2.3 / §3** — vendor-primary evidence for "flange is a suite attribute": the sensor itself ships no flange; three separate adapter plates cover three ISO flange sizes, and the connecting cable is a 4-pin M8 (correcting 5-pin mis-readings).

## 36. UReseriesDatasheet
> "Tool flange interface: M8 8-pin female, EN ISO-9409-1-50-4-M6"; I/O table: Digital In 2, Digital Out 2, Analog In 2; tool I/O supply 12/24 V.
- Use: **2.3 / §3** — the host-side empirical anchor for p(h): one physical tool connector, two DI / two DO / two AI channels on UR e-Series; this is the measured premise of the port-budget upper bound P1.

## 37. Siltala2021interface
> Title-page wording: "Resource Interface Matchmaking as a Part of Automatic Capability Matchmaking." (publisher reference list opened)
- Use: **2.2** — the explicit successor line on interface matchmaking; cite when positioning our ladder against the only prior graded interface-compatibility method.

## 38. CiucciDubois2012jelia
> Title-page wording: "Three-valued logics for incomplete information and epistemic logic." (JELIA 2012, LNAI 7519; conference version of entry 20)
- Use: **2.4** — conference-primary reference for the unknown third truth value; pair with entry 20 for the journal extension.
