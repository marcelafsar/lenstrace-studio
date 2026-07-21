# Run the Discord bot from source. Requires DISCORD_BOT_TOKEN in the
# environment or in a .env file at the repository root.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (Test-Path (Join-Path $root '.venv\Scripts\Activate.ps1')) {
    . (Join-Path $root '.venv\Scripts\Activate.ps1')
}

python -m bots.discord_bot.main
