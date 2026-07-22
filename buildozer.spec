[app]
title = ULTRAPARKOUR
package.name = ultraparkour
package.domain = hsmr.ultraparkour.apps
version = 1.0

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,mp3,wav

# main.py, GitHub reposunun kök klasöründe olmalı (ULTRAPARKOUR_mobile.py'nin
# kopyası/yeniden adlandırılmış hali)
source.main = main.py

requirements = python3,pygame

orientation = landscape
fullscreen = 1

# Multiplayer için internet izni şart
android.permissions = INTERNET

android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
