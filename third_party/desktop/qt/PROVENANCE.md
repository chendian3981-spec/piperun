# Qt / PySide / Shiboken 6.11.2

Copyright (C) The Qt Company Ltd. and other Qt/PySide contributors.
Qt, PySide and Shiboken are separate, unmodified third-party libraries, not relicensed under LRL-1.0.
The selected runtime modules are used under LGPL-3.0-only. See LGPL-3.0-only.txt and GPL-3.0-only.txt.
Upstream individual third-party copyright and license notices are retained in UPSTREAM-NOTICES.txt;
the consolidated file also includes notices for source components not used by this application.

Wheel versions: PySide6-Essentials==6.11.2, shiboken6==6.11.2, from official Qt maintainers on PyPI.
Runtime modules: Core, Gui, Widgets (native file picker), Network, Qml, Quick, QuickControls2,
their Basic/Templates/Layouts/Shapes dependencies and the Windows platform/basic image plugins.
No Qt WebEngine, WebView, Charts, multimedia, virtual keyboard, browser or external UI service is required.
The private PyInstaller hook scans the local QML dependency graph instead of collecting all QML modules.

Official sources, direct URLs and verified SHA-256 digests are in SOURCE-ARCHIVES.json.
The corresponding unmodified source archives are provided alongside the binary as
pipeRun-qt-sources-6.11.2.zip (Qt Base, Declarative, SVG, ShaderTools, PySide/Shiboken).
These are for component modification/rebuilding, NOT required to run the application.
Qt source: https://download.qt.io/archive/qt/6.11/6.11.2/submodules/
Bindings source: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/

The binary ZIP also includes editable corresponding application code under source/.
To recombine with modified, interface-compatible Qt/PySide libraries, use a Python 3.14 x64
build environment with Tcl/Tk, install PyInstaller 6.22.2, PyCryptodome 3.23.0, Brotli 1.2.0,
cffi 2.0.0 and the above Qt bindings (or compatible modified builds), then replace the
Qt/PySide library files in that build environment and run tools/build_desktop.py from source/.
Qt's own source archives contain their CMake/build instructions. This is a maintainer workflow;
ordinary users do not install any build tools, libraries or language runtime.
Application code/data needed by the packager are included, not user configurations or credentials.
There is no signature, DRM, anti-tamper check or installation key preventing a modified rebuild.

Notwithstanding other application terms, modification/replacement of the LGPL libraries
and reverse engineering to debug those modifications are not prohibited. The upstream
Qt/PySide terms and individual third-party licenses govern those components.
