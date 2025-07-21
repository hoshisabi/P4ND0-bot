@echo off
REM This script will:
REM 1. Check if Pipfile.lock is newer than requirements.txt (or if requirements.txt doesn't exist).
REM 2. Generate/update requirements.txt if needed.
REM 3. Stage all local changes.
REM 4. Commit changes with a user-provided message.
REM 5. Push changes to the remote Git repository.

SET "GENERATE_REQUIREMENTS=true"

REM Check if requirements.txt exists first
IF NOT EXIST requirements.txt (
    echo requirements.txt not found. Will generate a new one.
) ELSE (
    REM Use PowerShell to compare modification times of Pipfile.lock and requirements.txt
    REM Returns 'True' if Pipfile.lock is newer, 'False' otherwise
    FOR /F "usebackq tokens=*" %%A IN (`powershell -Command "(Get-Item 'Pipfile.lock').LastWriteTime -gt (Get-Item 'requirements.txt').LastWriteTime"`) DO (
        IF "%%A"=="True" (
            echo Pipfile.lock is newer than requirements.txt. Will generate new requirements.txt.
        ) ELSE (
            echo requirements.txt is up-to-date with Pipfile.lock. Skipping generation.
            SET "GENERATE_REQUIREMENTS=false"
        )
    )
)

IF "%GENERATE_REQUIREMENTS%"=="true" (
    echo Generating requirements.txt from Pipfile.lock...
    pipenv requirements > requirements.txt
    if %errorlevel% neq 0 (
        echo ERROR: Failed to generate requirements.txt. Check Pipenv installation and Pipfile.
        goto :eof
    )
    echo requirements.txt updated.
) ELSE (
    echo No changes to requirements.txt needed at this time.
)

REM Stage all changes
echo Staging all changes for commit...
git add .
if %errorlevel% neq 0 (
    echo ERROR: Failed to stage changes.
    goto :eof
)
echo All relevant changes staged.

REM Commit changes with the provided message
echo Committing changes...
if "%~1" == "" (
    echo ERROR: No commit message provided.
    echo Usage: %~nx0 "Your commit message here"
    goto :eof
)
git commit -m "%*"
if %errorlevel% neq 0 (
    echo ERROR: Git commit failed.
    goto :eof
)
echo Changes committed.

REM Push to remote repository
echo Pushing to remote repository...
git push
if %errorlevel% neq 0 (
    echo ERROR: Git push failed.
    goto :eof
)
echo Push complete!

:eof