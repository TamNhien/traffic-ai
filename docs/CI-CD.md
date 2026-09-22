# Traffic AI CI/CD and GitHub Release

Project root on Windows:

```powershell
cd D:\LienThongDH\DoAn\traffic-ai
```

## Local automated tests

```powershell
.\scripts\test.ps1
```

The test suite validates Python syntax, runs Backend and AI Service unit tests, builds the React frontend, validates Docker Compose, and builds the application Docker images.

## One-time GitHub setup

Install GitHub CLI if needed, then authenticate:

```powershell
gh auth login
```

Configure the remote repository once:

```powershell
.\scripts\github-init.ps1 -RepositoryUrl "https://github.com/<OWNER>/<REPO>.git"
```

## Automated release

```powershell
.\scripts\release.ps1 -Version 0.1.2
```

The release command:

1. Runs the local automated test suite.
2. Updates `VERSION` and the frontend package version.
3. Commits pending release changes.
4. Creates an annotated `vX.Y.Z` Git tag.
5. Pushes `main` and the tag to GitHub.
6. GitHub Actions reruns release verification.
7. GitHub Actions creates the GitHub Release automatically with ZIP, TAR.GZ, and SHA256SUMS assets.

Check recent GitHub Actions runs:

```powershell
.\scripts\ci-status.ps1
```
