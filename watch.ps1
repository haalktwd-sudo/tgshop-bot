# watch.ps1 — авто add/commit/push при изменениях
param(
  [string]$Path = ".",
  [int]$DebounceSeconds = 20
)

# 1) Гарантируем доступность git
$gitCandidates = @(
  "$env:ProgramFiles\Git\cmd\git.exe",
  "$env:ProgramFiles\Git\bin\git.exe",
  "${env:ProgramFiles(x86)}\Git\cmd\git.exe",
  "git"  # вдруг уже в PATH
)
$gitPath = $gitCandidates | Where-Object {
  try { & $_ --version *> $null; $true } catch { $false }
} | Select-Object -First 1

if (-not $gitPath) {
  Write-Host "Git не найден. Установите Git и перезапустите." -ForegroundColor Red
  Start-Sleep -Seconds 10
  exit 1
}
if ($gitPath -ne "git") { Set-Alias git $gitPath }

Write-Host "Git: $gitPath" -ForegroundColor Gray
Write-Host "Watching $Path ... (debounce $DebounceSeconds s)" -ForegroundColor Cyan

# 2) Watcher
$ignore = @('\.git\\', '\\__pycache__\\', '\\.venv\\', '\.pyc$', '\.log$')

$fsw = New-Object System.IO.FileSystemWatcher
$fsw.Path = (Resolve-Path $Path)
$fsw.IncludeSubdirectories = $true
$fsw.EnableRaisingEvents = $true

$changed = $false
Register-ObjectEvent $fsw Changed -SourceIdentifier FSChanged -Action {
  $full = $Event.SourceEventArgs.FullPath
  foreach($pat in $using:ignore){ if($full -match $pat){ return } }
  $global:changed = $true
} | Out-Null
Register-ObjectEvent $fsw Created -SourceIdentifier FSCreated -Action { $global:changed = $true } | Out-Null
Register-ObjectEvent $fsw Deleted -SourceIdentifier FSDeleted -Action { $global:changed = $true } | Out-Null
Register-ObjectEvent $fsw Renamed -SourceIdentifier FSRenamed -Action { $global:changed = $true } | Out-Null

# 3) Основной цикл
try {
  while ($true) {
    if ($changed) {
      $changed = $false
      Start-Sleep -Seconds $DebounceSeconds

      $status = git status --porcelain
      if (-not [string]::IsNullOrWhiteSpace($status)) {
        $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        git add .
        git commit -m "auto: $ts"
        git push
        Write-Host "Pushed at $ts" -ForegroundColor Green
      }
    }
    Start-Sleep -Milliseconds 500
  }
}
finally {
  Unregister-Event FSChanged,FSCreated,FSDeleted,FSRenamed -ErrorAction SilentlyContinue
  $fsw.Dispose()
}
