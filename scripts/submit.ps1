[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $branch = (git branch --show-current).Trim()
    $moduleByBranch = @{
        "feature/3d" = "3d"
        "feature/verification" = "verification"
        "feature/ui" = "ui"
    }
    if (-not $moduleByBranch.ContainsKey($branch)) {
        throw "Submit only from feature/3d, feature/verification, or feature/ui (current: $branch)."
    }
    if (git status --porcelain) { throw "Commit or stash all changes before submitting." }

    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw "Fetch failed." }
    $baseRef = if (git rev-parse --verify --quiet refs/remotes/origin/hackathon-integration) {
        "origin/hackathon-integration"
    } elseif (git rev-parse --verify --quiet refs/heads/hackathon-integration) {
        "hackathon-integration"
    } else { throw "hackathon-integration was not found." }

    $changed = @(git diff --name-only "$baseRef...HEAD")
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect feature changes." }
    if ($changed.Count -eq 0) { throw "There are no committed changes to submit." }

    function Test-AllowedPath([string]$Path, [string]$Module) {
        if ($Module -eq "3d") {
            return $Path -in @(
                "src/aura/workspace/representations.py", "src/aura/workspace/representation_service.py",
                "src/aura/workspace/prototype.py", "tests/test_representations.py",
                "tests/test_physical_assembly.py", "tests/test_connected_physical_assembly.py",
                "tests/test_generic_interface_compilers.py", "tests/test_cold_project_compilation.py"
            ) -or $Path.StartsWith("src/aura/workspace/web/representation/") -or
                $Path.StartsWith("src/aura/workspace/web/frontend/generators/")
        }
        if ($Module -eq "verification") {
            return $Path.StartsWith("src/aura/verification/") -or $Path -eq "tests/test_goal8_verification.py"
        }
        return $Path.StartsWith("src/aura/workspace/web/frontend/src/") -or
            $Path.StartsWith("src/aura/workspace/web/frontend/electron/") -or
            $Path.StartsWith("src/aura/workspace/web/frontend/e2e/") -or
            ($Path.StartsWith("src/aura/workspace/web/frontend/") -and
                -not $Path.StartsWith("src/aura/workspace/web/frontend/generators/")) -or
            $Path.StartsWith("src/aura/legacy/ui/") -or $Path -in @(
                "src/aura/workspace/web/app.js", "src/aura/workspace/web/styles.css",
                "src/aura/workspace/web/index.html"
            )
    }

    $unexpected = @($changed | Where-Object { -not (Test-AllowedPath $_ $moduleByBranch[$branch]) })
    Write-Host "Changed files relative to ${baseRef}:"
    $changed | ForEach-Object { Write-Host "  $_" }
    if ($unexpected.Count -gt 0) {
        Write-Host "Unexpected or integration-owned files:" -ForegroundColor Red
        $unexpected | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        throw "Submission rejected. Coordinate shared changes with the integration owner."
    }

    & (Join-Path $PSScriptRoot "test.ps1") -Module $moduleByBranch[$branch]
    if ($LASTEXITCODE -ne 0) { throw "Relevant tests failed; nothing was pushed." }
    git diff --check $baseRef...HEAD
    if ($LASTEXITCODE -ne 0) { throw "Diff whitespace check failed; nothing was pushed." }
    git diff --stat $baseRef...HEAD
    git push -u origin $branch
    if ($LASTEXITCODE -ne 0) { throw "Push failed." }
    Write-Host "Pushed $branch. No merge was performed."
} finally {
    Pop-Location
}
