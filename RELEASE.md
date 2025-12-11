# file: RELEASE.md
# Release Process

**awsctl** uses an automated, secure release pipeline.
We adhere to **Semantic Versioning** (SemVer).

---

## 1. Versioning Strategy

We use `setuptools_scm`. You do **not** need to manually edit any version files.
The source of truth for the version number is **Git tags**.

- **Major (`2.0.0`)**: Breaking changes.
- **Minor (`2.8.1`)**: New features (backwards compatible).
- **Patch (`2.8.1`)**: Bug fixes, internal improvements.

---

## 2. How to Cut a Release

### Prerequisites

1. Ensure you are on the `main` branch.
2. Ensure all tests and security scans pass:

> make test
> make security

### Step 1: Tag

Create an annotated tag for the version.
The tag must start with `v`.

Example for `v2.8.1`:

> git tag -a v2.8.1 -m "Release v2.8.1: Phase 2 Enterprise Release"

### Step 2: Push

Pushing the tag triggers the Release Workflow in GitHub Actions.

> git push origin v2.8.1

---

## 3. What Happens Next?

Once the tag is pushed:

1. **CI Pipeline:** GitHub Actions detects the new tag.
2. **Build:** The pipeline builds the Wheel (`.whl`) and Source Tarball (`.tar.gz`).
3. **Release:** A GitHub Release is created, and the built artifacts are attached automatically.

The published version is now available for installation:

> pipx install "git+https://github.com/BT-IT-Infrastructure-CloudOps/awsctl.git@v2.8.1"
