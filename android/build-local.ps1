$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$workspaceRoot=Split-Path $projectRoot -Parent
$toolRoot=Join-Path $workspaceRoot 'tools/android-dev'
$jdkPath=(Get-ChildItem (Join-Path $toolRoot 'jdk') -Directory | Select-Object -First 1).FullName
if(-not $jdkPath){throw 'Run tools/setup_android_toolchain.py first, or build with Android Studio.'}
$env:JAVA_HOME=$jdkPath
$env:Path=(Join-Path $jdkPath 'bin')+';'+(Join-Path $env:SystemRoot 'System32')+';'+$env:SystemRoot
$env:GRADLE_USER_HOME=Join-Path $toolRoot 'gradle-home'
& (Join-Path $projectRoot 'gradlew.bat') -p $projectRoot testDebugUnitTest assembleDebug --console plain
if($LASTEXITCODE -ne 0){throw 'Android build failed'}
$releaseFolder=Join-Path $workspaceRoot 'releases'
New-Item -ItemType Directory -Force $releaseFolder | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot 'app/build/outputs/apk/debug/app-debug.apk') -Destination (Join-Path $releaseFolder 'BrickCheatGame-debug.apk') -Force
