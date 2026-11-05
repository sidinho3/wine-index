@echo off
rem Pulls this week's Alko price list and rebuilds the Regional Wine Index site.
cd /d "%~dp0"
python wine_index.py >> data\run.log 2>&1
