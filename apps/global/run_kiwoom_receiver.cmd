@echo off
echo The global dashboard no longer uses Kiwoom quotes.
echo Starting the separate Bloomberg web receiver instead.
call "%~dp0..\..\run_global_bloomberg_web_receiver.cmd"
