@echo off
REM This script will:
REM 1. Check if Pipfile.lock is newer than requirements.txt (or if requirements.txt doesn't exist).
REM 2. Generate/update requirements.txt if needed.
REM 3. Stage all local changes.
REM 4. Commit changes with a user-provided message.
REM 5. Push changes to the remote Git repository.

SET "GENERATE_REQUIREMENTS=true"

REM Replace old pipenv check with a simple uv export command
echo Generating requirements.txt from uv.lock...
uv export --no-hashes --format requirements-txt > requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to generate requirements.txt. Check uv installation.
    goto :eof
)
echo requirements.txt updated!

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
git commit -m "%~1"
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