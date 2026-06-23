# Windows 방화벽에서 HTTP(80) / HTTPS(443) 인바운드 허용
# 관리자 권한으로 실행 필요: 마우스 우클릭 → "관리자 권한으로 실행"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "관리자 권한이 필요합니다. PowerShell을 관리자 권한으로 실행하세요."
    exit 1
}

$rules = @(
    @{ Name = "Legal-RAG HTTP";  Port = 80;  Protocol = "TCP" },
    @{ Name = "Legal-RAG HTTPS"; Port = 443; Protocol = "TCP" },
    @{ Name = "Legal-RAG HTTP3"; Port = 443; Protocol = "UDP" }
)

foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "이미 존재: $($rule.Name)" -ForegroundColor Yellow
    } else {
        New-NetFirewallRule `
            -DisplayName $rule.Name `
            -Direction Inbound `
            -Protocol $rule.Protocol `
            -LocalPort $rule.Port `
            -Action Allow `
            -Profile Any | Out-Null
        Write-Host "추가됨: $($rule.Name) (포트 $($rule.Port)/$($rule.Protocol))" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "완료. 공유기에서도 80/443 포트를 이 PC로 포트포워딩해야 합니다." -ForegroundColor Cyan
