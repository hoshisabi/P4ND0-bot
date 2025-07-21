@echo off
REM Generate requirements.txt from Pipfile.lock
echo Generating requirements.txt...
pipenv requirements > requirements.txt
if %errorlevel% neq 0 (
    echo Error generating requirements.txt. Exiting.
    goto :eof
)
echo requirements.txt updated.

REM Stage all changes
echo Staging changes...
git add .
if %errorlevel% neq 0 (
    echo Error staging changes. Exiting.
    goto :eof
)
echo Changes staged.

REM Commit changes with the provided message
REM %* captures all arguments passed to the batch file, enclosed in quotes for multi-word messages
echo Committing changes...
if "%~1" == "" (
    echo No commit message provided. Please run like: your_script.bat "Your commit message here"
    goto :eof
)
git commit -m "%*"
if %errorlevel% neq 0 (
    echo Error committing changes. Exiting.
    goto :eof
)
echo Changes committed.

REM Push to remote repository
echo Pushing to remote...
git push
if %errorlevel% neq 0 (
    echo Error pushing changes. Exiting.
    goto :eof
)
echo Push complete!

:eof
