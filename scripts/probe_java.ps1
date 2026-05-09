$ErrorActionPreference = 'SilentlyContinue'

Write-Host '== JAVA_HOME =='
$userJh = [Environment]::GetEnvironmentVariable('JAVA_HOME','User')
$machineJh = [Environment]::GetEnvironmentVariable('JAVA_HOME','Machine')
Write-Host ("User    : " + ($userJh    -as [string]))
Write-Host ("Machine : " + ($machineJh -as [string]))
Write-Host ("Process : " + ($env:JAVA_HOME -as [string]))

Write-Host ''
Write-Host '== java on PATH =='
$javaCmd = Get-Command java -ErrorAction SilentlyContinue
if ($javaCmd) {
    Write-Host ("FOUND: " + $javaCmd.Source)
} else {
    Write-Host 'NOT FOUND'
}

Write-Host ''
Write-Host '== Candidate JDK locations =='
$candidates = @(
    'C:\Program Files\Android\Android Studio\jbr\bin\java.exe',
    'C:\Program Files\Android\Android Studio\jre\bin\java.exe',
    'C:\Program Files (x86)\Android\Android Studio\jbr\bin\java.exe'
)
foreach ($c in $candidates) {
    if (Test-Path $c) {
        Write-Host ("FOUND: " + $c)
    }
}

Write-Host ''
Write-Host '== Other JDK roots =='
$roots = @(
    'C:\Program Files\Java',
    'C:\Program Files\Eclipse Adoptium',
    'C:\Program Files\Microsoft',
    'C:\Program Files\Amazon Corretto',
    'C:\Program Files\Zulu'
)
foreach ($r in $roots) {
    if (Test-Path $r) {
        Get-ChildItem -LiteralPath $r -Directory | ForEach-Object { Write-Host $_.FullName }
    }
}

Write-Host ''
Write-Host '== Android SDK env =='
Write-Host ("ANDROID_HOME     : " + ($env:ANDROID_HOME     -as [string]))
Write-Host ("ANDROID_SDK_ROOT : " + ($env:ANDROID_SDK_ROOT -as [string]))
