What I found (quick)

Your wiki docs already embed Mermaid diagrams directly. 

tenant-bootstrap_manifest_20260…

None of the wiki pages currently reference rendered AWSDAC PNGs (the images/diag-arch-*.png pattern). 

tenant-bootstrap_manifest_20260…

Your tooling expects AWS diagrams to be YAML in diagrams-src/, rendered to docs/wiki/images/diag-arch-<yaml-stem>.png, and it enforces YAML↔PNG parity. 

awsctl_manifest_20260209T202245Z

Also: docs/wiki/diagrams.md still talks about docs/diagrams/src/*.yaml, which doesn’t match the actual/enforced diagrams-src/ location. 

tenant-bootstrap_manifest_20260…

 

awsctl_manifest_20260209T202245Z

1) ALL AWSDAC diagrams required + where they should appear (AWS-only)

You already have the right 5 AWS architecture YAMLs in diagrams-src/ (good coverage of the major AWS topology themes). 

awsctl_manifest_20260209T202245Z

Here’s the “take every AWS-architecture opportunity” mapping (add the rendered PNGs into these pages):

Core AWS topology (hub / boundaries / trust)

diagrams-src/aws-identity-hub.yaml → images/diag-arch-aws-identity-hub.png
Place in: split-plane-architecture.md, security-overview.md, developer-architecture-guide.md

diagrams-src/awsctl-boundary.yaml → images/diag-arch-awsctl-boundary.png
Place in: split-plane-architecture.md, trust-and-security-boundaries.md, arch-awsctl-mission.md (and/or architecture-mission.md)

diagrams-src/identity-broker-trust.yaml → images/diag-arch-identity-broker-trust.png
Place in: trust-and-security-boundaries.md, security-trust-model.md, identity-broker-pattern.md

Auth path inside AWS (Identity Center → STS)

diagrams-src/awsctl-oidc-flow.yaml → images/diag-arch-awsctl-oidc-flow.png
Place in: identity-broker-pattern.md, security-overview.md, getting-started.md (as “AWS-side architecture”; token flow stays Mermaid)

Safety / idempotency as AWS components

diagrams-src/idempotency-safety.yaml → images/diag-arch-idempotency-safety.png
Place in: execution-failure-modes.md (keep the existing Mermaid flow too)

How to reference them in wiki pages (standard)

![<Caption>](images/diag-arch-<yaml-stem>.png)


That “rendered output in docs/wiki/images/” pattern is explicitly how your docs describe it. 

tenant-bootstrap_manifest_20260…


And the linter enforces the exact diag-arch-<yaml-stem>.png naming. 

awsctl_manifest_20260209T202245Z

2) Ensure ONLY AWS architecture uses AWSDAC (everything else = Mermaid)

Rule of thumb that matches your doc intent:

AWSDAC: diagrams whose primary purpose is showing AWS accounts/services + trust boundaries/topology (Identity Center, STS, roles, hub/spoke accounts, logging, storage, etc.). 

tenant-bootstrap_manifest_20260…

Mermaid: everything else—process flows, UX flows, contributor/release/testing workflows, schemas, threat scenarios involving non-AWS actors, etc. 

tenant-bootstrap_manifest_20260…

3–4) Mermaid diagram opportunities (what’s missing today)

These wiki pages currently have no diagrams and should get Mermaid:

getting-started.md (✅ must add token flow)

release-process.md

testing-strategy.md

Security-Operations.md

configuration-model.md

config-schema.md

contributor-guide.md

concepts-and-terminology.md (optional, but useful as a “glossary map”)

home.md (optional)

(Your linter only requires diagrams on certain prefixes like arch- / security- / lifecycle- / compliance-, but you explicitly asked to take all opportunities. 

awsctl_manifest_20260209T202245Z

)

5) Business-friendly “token flow” Mermaid diagram (paste into getting-started.md)

This stays Mermaid because it’s an explanatory flow, not an AWS topology diagram.

sequenceDiagram
    autonumber
    actor User as User (Engineer)
    participant CLI as awsctl (CLI)
    participant Cache as AWS SSO Token Cache (local)
    participant AWSCLI as aws cli sso login
    participant Browser as Browser / IdP Login
    participant IC as AWS IAM Identity Center
    participant STS as AWS STS
    participant Acct as Target AWS Account (Role)

    User->>CLI: awsctl use <context>
    CLI->>Cache: Check for valid SSO token
    alt Token valid
        Cache-->>CLI: Access token (cached)
    else Token missing/expired
        CLI->>AWSCLI: Run "aws sso login"
        AWSCLI->>Browser: Open login URL
        User->>Browser: Authenticate (SSO)
        Browser->>IC: Complete SSO auth
        IC-->>Cache: Store refreshed token locally
        Cache-->>CLI: Access token (cached)
    end

    CLI->>STS: AssumeRole / Get temp credentials
    STS-->>CLI: AccessKey/Secret/SessionToken (temp)
    CLI-->>User: Exports creds / sets shell env for session
    User->>Acct: Uses AWS CLI/SDK with temp creds


This matches your documented behavior: calling aws sso login (browser-based), then using cached tokens/credentials behind the scenes. 

awsctl_manifest_20260209T222818Z

Two small doc/tooling fixes you should do while you’re here

Update docs/wiki/diagrams.md to say YAML lives in diagrams-src/ (not docs/diagrams/src/). 

tenant-bootstrap_manifest_20260…

 

awsctl_manifest_20260209T202245Z

If you add any new YAMLs, make sure your render step produces the corresponding PNGs, otherwise the linter will fail on YAML↔PNG parity. 

awsctl_manifest_20260209T202245Z