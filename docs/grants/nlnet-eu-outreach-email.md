# NLnet European-Dimension Outreach — Email / Letter Templates

> **Why this exists.** For a China-based solo applicant, NLnet's *European dimension* requirement is
> the single make-or-break criterion. NLnet's Office Hour is explicit: subject-matter relevance alone
> ("our standard is European / EU SMEs would benefit") is *"unlikely to fulfill the criteria unless
> there are adopters collaborating with you on the project."* The fix is **genuine EU collaboration** —
> a co-applicant (Route A) or at minimum 1–2 EU stakeholders who validate data / adopt the API / co-present
> (Route B). These templates request exactly that.
>
> Convention: English (project-facing). Replace `[brackets]` with real values. Send from the applicant's
> own address; do **not** imply NLnet has pre-approved anything.

---

## Template 1 — Collaboration letter request (Route B, or warm-up for Route A)

**Subject:** Collaboration on an open robot mechanical-interface compatibility dataset (RoboParts) — NLnet proposal

Dear [Name],

I am preparing an open-source proposal to **NLnet / NGI Zero** for *RoboParts* — an open,
vendor-neutral dataset and compatibility engine that answers "given robot part A and part B, can they
mount, and if not, what adapter is required?" Our analysis of the **ISO 9409-1** flange family (the
de-facto mounting standard for most European arms: KUKA, Universal Robots, Franka, ABB, Staubli) shows
**every pair of the 9 flange designations has a distinct pitch-circle diameter ⇒ 0 direct interfaces,
100% require an adapter plate** — yet no open, machine-readable compatibility+adapter matrix exists.

Because NLnet requires a clear *European dimension*, and because your organisation is central to the
European robot-hardware / open-source ecosystem, I would like to invite a concrete collaboration:

- **Data validation:** review/correct the ISO 9409-1 PCD matrix and adapter rules for the European
  arms you know best, so the open dataset is accurate for EU integrators.
- **Adoption / pilot:** if useful, pilot our JSON compatibility API inside [your tooling / curriculum /
  integration workflow] and tell us what breaks.
- **Co-presentation:** optionally co-present the open dataset at [FOSDEM / a ROS-Industrial or
  euRobotics event] during the grant period.

In return, the dataset and engine are released open (code MIT / data CC BY 4.0) and your organisation
is credited as a collaborating partner. If you are open to this, could you send a short **letter of
collaboration** (1 paragraph) stating the above, addressed to me, that I can attach to the NLnet
application? It need not commit funding — only that we are collaborating on the project.

Happy to jump on a call. RoboParts: https://roboparts.cc · repo: https://github.com/lm203688/roboparts

Best,
[Your name] — RoboParts

---

## Template 2 — Co-applicant invitation (Route A — recommended, highest odds)

**Subject:** Paid EU co-applicant role on an NLnet open-robotics data grant (RoboParts)

Dear [Name],

I am submitting a **NLnet / NGI Zero** grant (first-time, €25,000, ~6 months) for *RoboParts*, an open
robot mechanical-interface compatibility engine + dataset (ISO 9409-1 focus). NLnet requires that
**≥60% of the funds go to EU-based participants** for a non-EU lead — so I am looking for a European
co-applicant to lead the EU-facing work and receive that share.

The role (≈€15K of the grant, ~60% of effort on the EU side):
- Validate the ISO 9409-1 compatibility/adapter data against European arms and integrator practice.
- Lead engagement with euRobotics / ROS-Industrial and present the open dataset at a European event.
- Co-author the open methodology brief (open access).

What I deliver: the engineering (engine, dataset expansion to 1,000+ entities, API), under MIT/CC BY 4.0.
All outputs open; NLnet pays each of us our share directly as a donation.

Would you / your lab be interested? I can send the draft proposal + budget split for review. No
commitment until we both agree the MoU.

Best,
[Your name] — RoboParts

---

## Suggested targets (send Template 1 first; Template 2 to the most receptive)

- **euRobotics** — European robotics research association (dimension + validation).
- **ROS-Industrial (EU)** — open-source robotics for European industry (adoption + co-present).
- **Open Robotics / ROS 2 community (EU contacts)** — ecosystem fit.
- **European robot SMEs / integrators** — Franka, a KUKA/UR integrator, a Danish/Dutch/German cobot shop
  (real adoption letters carry the most weight).
- **A European university robotics/mechatronics lab** — strongest Route-A co-applicant source.

## What a good reply looks like (attach to proposal)

> "We are collaborating with RoboParts on the open ISO 9409-1 compatibility dataset: we will validate
> the flange PCD/adapter data for European arms and pilot the JSON API in our [integration/teaching].
> We support the NLnet proposal." — [Org], [date]

That is a *collaboration* statement (what NLnet wants), not a generic endorsement.
