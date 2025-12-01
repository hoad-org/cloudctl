# Release Process

**awsctl** uses an automated, secure release pipeline.  
We adhere to **Semantic Versioning** (SemVer).

---

## 1. Versioning Strategy

We use `setuptools_scm`. You do **not** need to manually edit any version files.  
The source of truth for the version number is **Git tags**.

- **Major (`2.0.0`)**: Breaking changes.
- **Minor (`2.1.0`)**: New features (backwards compatible).
- **Patch (`2.0.1`)**: Bug fixes, internal improvements.

---

## 2. How to Cut a Release

### Prerequisites

Before cutting a release:

1. Ensure you are on the `main` branch.
2. Ensure local git is up to date:

       git pull origin main

3. Ensure all tests pass:

       make test

### Step 1: Tag

Create an annotated tag for the version.  
The tag must start with `v`.

Example for `v2.0.0`:

    git tag -a v2.0.0 -m "Release v2.0.0: Enterprise Ready"

### Step 2: Push

Pushing the tag triggers the Release Workflow in GitHub Actions.

    git push origin v2.0.0

---

## 3. What Happens Next?

Once the tag is pushed:

1. **CI Pipeline:** GitHub Actions detects the new tag.
2. **Build:** The pipeline builds:
   - Python Wheel (`.whl`)
   - Source Tarball (`.tar.gz`)
3. **Release:** A GitHub Release is created, and the built artifacts are attached automatically.

The published version is now available for installation via your configured distribution channel, for example:

    pipx install "git+https://github.com/your-org/awsctl.git@v2.0.0"
