[app]

# (str) Title of your application
title = FitWorks AI

# (str) Package name
package.name = fitworksai

# (str) Package domain (needed for android/ios packaging)
package.domain = org.tigerhacks

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (leave empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,db,env,json,txt,md

# (list) List of inclusion patterns using pattern matching
source.include_patterns = assets/*,images/*,.env

# (list) List of directory to exclude
source.exclude_dirs = tests, bin, .venv, kivy_venv, .vscode, .git, __pycache__, backend/ai/__pycache__, backend/database/__pycache__

# (list) List of exclusions using pattern matching
source.exclude_patterns = license,Makefile,*.pyc,*.pyo

# (str) Application versioning
version = 0.1.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,google-genai,pydantic,python-dotenv,urllib3,certifi,charset-normalizer,idna,requests

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen
fullscreen = 0

#
# Android specific
#

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE

# (int) Target Android API
android.api = 34

# (int) Minimum API your APK will support
android.minapi = 24

# (int) Android NDK API to use
android.ndk_api = 24

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (bool) If True, automatically accept SDK license agreements
android.accept_sdk_license = True

# (str) The Android arch to build for
android.archs = arm64-v8a, armeabi-v7a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (str) The format used to package the app for debug mode
android.debug_artifact = apk

# (str) The format used to package the app for release mode
android.release_artifact = apk

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
