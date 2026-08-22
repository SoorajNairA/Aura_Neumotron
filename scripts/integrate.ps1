[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("feature/3d", "feature/verification", "feature/ui")]
    [string]$FeatureBranch
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $current = (git branch --show-current).Trim()
    if ($current -ne "hackathon-integration") {
        throw "Integration is allowed only on hackathon-integration (current: $current)."
    }
    if (git status --porcelain) { throw "Working tree must be clean before integration." }

    git fetch origin $FeatureBranch
    if ($LASTEXITCODE -ne 0) { throw "Could not fetch $FeatureBranch from origin." }
    $featureRef = "origin/$FeatureBranch"
    if (-not (git rev-parse --verify --quiet "refs/remotes/origin/$FeatureBranch")) {
        throw "$featureRef was not found after fetch."
    }

    $module = $FeatureBranch.Substring("feature/".Length)
    $changed = @(git diff --name-only "HEAD...$featureRef")
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect the feature diff." }
    if ($changed.Count -eq 0) { throw "$FeatureBranch has no changes to integrate." }

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

    Write-Host "Diff for $featureRef relative to hackathon-integration:"
    git diff --stat "HEAD...$featureRef"
    $unexpected = @($changed | Where-Object { -not (Test-AllowedPath $_ $module) })
    if ($unexpected.Count -gt 0) {
        Write-Host "Unexpected or shared-contract changes:" -ForegroundColor Red
        $unexpected | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        throw "Integration stopped for explicit review. Apply approved shared changes separately on hackathon-integration."
    }

    git diff --check "HEAD...$featureRef"
    if ($LASTEXITCODE -ne 0) { throw "Diff whitespace check failed." }
    git merge --no-ff --no-commit $featureRef
    if ($LASTEXITCODE -ne 0) {
        git merge --abort 2>$null
        throw "Merge failed and was aborted."
    }

    try {
        & (Join-Path $PSScriptRoot "test.ps1") -Module $module
        if ($LASTEXITCODE -ne 0) { throw "Module validation failed." }
        & (Join-Path $PSScriptRoot "test.ps1") -Module all
        if ($LASTEXITCODE -ne 0) { throw "Project-wide validation failed." }
    } catch {
        git merge --abort 2>$null
        throw "Validation failed; merge aborted. $($_.Exception.Message)"
    }

    git commit -m "Integrate $FeatureBranch"
    if ($LASTEXITCODE -ne 0) {
        git merge --abort 2>$null
        throw "Could not create the integration commit; merge aborted."
    }
    Write-Host "Integrated $FeatureBranch into hackathon-integration. main was not changed."
} finally {
    Pop-Location
}
