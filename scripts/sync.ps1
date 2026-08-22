[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$branch = (git branch --show-current).Trim()

if ($LASTEXITCODE -ne 0 -or -not $branch) { throw "Unable to determine the current branch." }
if ($branch -notin @("feature/3d", "feature/verification", "feature/ui")) {
    throw "sync.ps1 must run from feature/3d, feature/verification, or feature/ui (current: $branch)."
}
if (git status --porcelain) { throw "Working tree must be clean before syncing." }

git fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed." }

$integrationRef = if (git rev-parse --verify --quiet refs/remotes/origin/hackathon-integration) {
    "origin/hackathon-integration"
} elseif (git rev-parse --verify --quiet refs/heads/hackathon-integration) {
    "hackathon-integration"
} else {
    throw "hackathon-integration was not found locally or on origin. Ask the integration owner to publish it."
}

git merge --no-edit $integrationRef
if ($LASTEXITCODE -ne 0) { throw "Sync merge failed. Resolve or abort the merge before continuing." }

Write-Host "$branch is synchronized with $integrationRef."
