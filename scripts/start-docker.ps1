param(
  [ValidateSet("local", "dev", "production", "prod")]
  [string] $Mode = "local",

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $ComposeArgs
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$normalizedMode = switch ($Mode) {
  "dev" { "local" }
  "prod" { "production" }
  default { $Mode }
}

if ($normalizedMode -eq "production") {
  $envFile = ".env.production"
  $composeFile = "docker-compose.production.yml"
  $missingMessage = "Missing .env.production. Create it with production values before starting the production Docker stack."
} else {
  $envFile = ".env.local"
  $composeFile = "docker-compose.yml"
  $missingMessage = "Missing .env.local. Create it from .env.example before starting the local Docker stack."
}

if (-not (Test-Path $envFile)) {
  Write-Error $missingMessage
}

$env:DOCKER_BUILDKIT = if ($env:DOCKER_BUILDKIT) { $env:DOCKER_BUILDKIT } else { "0" }
$env:COMPOSE_BAKE = if ($env:COMPOSE_BAKE) { $env:COMPOSE_BAKE } else { "false" }

if ($ComposeArgs.Count -eq 0) {
  $ComposeArgs = @("up", "--build")
}

docker compose --env-file $envFile -f $composeFile @ComposeArgs
