@echo off
rem Offline check only. No Python install, account traffic, certificate or proxy writes.
start "" /wait "%~dp0pipeRun.exe" --diagnose
