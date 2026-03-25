# contributer-guide.md

# 🤝 Contributor Guide

This document defines **how to contribute to `awsctl`**. 

`awsctl` is a security-sensitive control-plane tool. Contributions are welcome, but they must preserve explicit trust boundaries, failure semantics, and architectural constraints. Drive-by changes without architectural context are discouraged.

This document is authoritative.

---

## 🏛️ Contribution Philosophy

`awsctl` values **correctness over convenience** and **safety over ergonomics**. We prioritize explicit behavior over "magic" shortcuts. If a change makes `awsctl` easier to misuse, it is likely unacceptable.



---

## 🚦 Before You Start

Before opening a pull request, you must read and understand the following authoritative documents:
* [[Developer Architecture Guide|Developer-Architecture-Guide]]
* [[Security Overview|Security-Overview]]
* [[Trust and Security Boundaries|Trust-and-Security-Boundaries]]
* [[Failure Modes & Mitigation|Failure-Modes-and-Mitigation]]
* [[Docs-as-Code Contract|Docs-as-Code-Contract]]

---

## 🔍 Types of Contributions

### 1. Bug Fixes
Must include a regression test and preserve failure semantics. If a fix changes user-visible behavior, documentation **must** be updated simultaneously.

### 2. New Features
Requires a clearly stated problem, identified trust boundaries, and defined failure modes. Features that blur the responsibility between `awsctl` and AWS/IAM will be rejected.

### 3. Documentation Changes
Documentation changes are treated as code changes. They must be accurate, reviewed, and match current behavior. **Do not "document the future."**

### 4. Plugins
The preferred extension mechanism. Plugins must be optional, fail safely, and never bypass registry guardrails. See the [[Plugin Framework|Plugin-Framework]].

---

## 🛠️ Development Setup

**Install Dependencies and Run Tests:**
```bash
make setup
make check
```
> [!IMPORTANT]
> **Happy-path tests alone are insufficient.** Contributions must include tests for edge cases, failure behavior, and guardrail enforcement.

---

## 🛡️ Security & Documentation Requirements

### Security Expectations
Contributors must **never**:
* Introduce implicit defaults or store credentials.
* Mask AWS denial errors or add silent retries.
* Bypass confirmation prompts for sensitive actions.



### Documentation Drift
If your change affects behavior, security posture, or architecture, you must update the corresponding documentation. Documentation drift is a "hard block" for merges.

---

## 📝 Commit & PR Guidelines

### Pull Requests must include:
* **The "What" and "Why":** Logic behind the change.
* **Risk Assessment:** How does this affect the security model?
* **Documentation Impact:** Which wiki pages were updated?

### Review Process
Reviews focus on **safety, explicitness, and determinism**. Code style is secondary to architectural alignment. Changes that hide complexity or reduce user awareness will be rejected.

---

## 🚨 Responsible Disclosure

**Security issues must be reported privately.** Do not open public issues for:
* Credential exposure.
* Privilege escalation paths.
* Guardrail bypasses.

Follow the repository’s specific `SECURITY.md` policy for private reporting.

---

## ✅ Summary

As a contributor, your role is to preserve invariants and protect users. If a change feels "nice" but weakens clarity or safety, it does not belong in `awsctl`. This guide exists to keep the tool trustworthy.
