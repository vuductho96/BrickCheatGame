param([string]$JavaHome=$env:JAVA_HOME,[int]$Seeds=12,[int]$Start=1000,[int]$Trays=90,[int]$BudgetMs=100,[string]$Output="native-benchmark.csv")
$ErrorActionPreference='Stop'
if(-not $JavaHome){throw 'Set JAVA_HOME to a JDK 17 installation or pass -JavaHome.'}
$repo=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$classes=Join-Path $repo 'artifacts/native-benchmark-classes'
New-Item -ItemType Directory -Force -Path $classes | Out-Null
$sources=@(Get-ChildItem (Join-Path $repo 'android/app/src/main/java/com/bric/cheatgame/core') -Filter '*.java' | ForEach-Object {$_.FullName})
$sources+=@(Get-ChildItem $PSScriptRoot -Filter '*.java' | ForEach-Object {$_.FullName})
& (Join-Path $JavaHome 'bin/javac.exe') -d $classes @sources
if($LASTEXITCODE -ne 0){throw 'Java compilation failed.'}
& (Join-Path $JavaHome 'bin/java.exe') -Xmx768m '-Djava.library.path=' -cp $classes com.bric.cheatgame.benchmark.Compare $Seeds $Start $Trays $BudgetMs > $Output
if($LASTEXITCODE -ne 0){throw 'Benchmark failed.'}
Write-Output "Report: $Output"
