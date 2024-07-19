del /s /q build
del /s /q dist
rmdir /s /q build
rmdir /s /q dist
@rem .env\Scripts\pyinstaller HHResumeUpdater.py --version-file HHResumeUpdater.version
.env\Scripts\pyinstaller HHResumeUpdater.spec
pause