@echo off
title DocGuru development
cd /d "%~dp0"
npm run dev:all
exit /b %ERRORLEVEL%
