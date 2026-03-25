# 🏠 Home: awsctl Documentation Hub

Welcome to the authoritative documentation for **awsctl**. 

This system is maintained using a **docs-as-code** methodology. The source of truth resides in the `docs/wiki/` directory of the repository. Content is published to this GitHub Wiki **strictly via CI/CD pipelines**. 

> [!CAUTION]
> **Manual edits to this wiki will be overwritten.** Please submit a Pull Request to the main repository to suggest changes.

---

## 🏗️ Architecture & Design
Learn about the structural foundations and the philosophy that governs the tool.

* [[Architecture Mission|architecture-mission]] — The "Why" and the North Star.
* [[Split-Plane Architecture|split-plane-architecture]] — Understanding Control vs. Execution planes.
* [[Developer Architecture Guide|developer-architecture-guide]] — Deep dive for core maintainers.
* [[Configuration Model|configuration-model]] — How settings are resolved.
* [[Registry & Policy Model|registry-and-policy-model]] — Defining allowed intent.

---

## 🔐 Security & Trust
Our non-negotiable standards for handling identity and authority.

* [[Security Overview|security-overview]] — Posture, goals, and core properties.
* [[Security Trust Model|security-trust-model]] — Explicit definitions of who we trust.
* [[Trust & Security Boundaries|trust-and-security-boundaries]] — Where awsctl stops and AWS begins.
* [[Identity Broker Pattern|identity-broker-pattern]] — Connecting identity to authority.
* [[Threat Model|threat-model]] — Analysis of risks and mitigations.

---

## 🛠️ Operational Guides
Practical documentation for using and extending the tool.

* [[Getting Started|getting-started]] — Minimal, safe introduction.
* [[Shell Integration|shell-integration]] — Ergonomics without expanding authority.
* [[Interactive & UX Behaviour|interactive-and-ux-behaviour.md]] — Safety-oriented interface design.
* [[Break-Glass Procedures|break-glass-procedures]] — Emergency access protocols.
* [[Security Operations|Security-Operations]] — Auditing, registry management, and IR.

---

## 🧩 Extension & Development
Guidelines for contributors and developers looking to expand capabilities.

* [[Contributor Guide|contributor-guide]] — How to safely contribute code.
* [[Plugin Framework|plugin-framework]] — Extensibility without authority.
* [[Writing Plugins|writing-plugins]] — Technical implementation guide.
* [[Testing Strategy|testing-strategy]] — Ensuring correctness and idempotency.

---

## 📋 Standards & Release
Governance and process documentation.

* [[Docs-as-Code Contract|docs-as-code-contract]] — How we manage this documentation.
* [[Configuration Schema|config-schema]] — The authoritative YAML contract.
* [[Release Process|release-process]] — SemVer and safety gates.
* [[Failure Modes & Mitigation|execution-failure-modes]] — Handling the "Fail-Safe" model.

---

## 📚 Reference
* [[Concepts & Terminology|concepts-and-terminology]] — Defining our vocabulary.
* [[Diagram Standards|diagrams]] — Standards for Mermaid and AWSDAC.

***

**Would you like me to generate the `_Sidebar.md` file to match this new structure?**