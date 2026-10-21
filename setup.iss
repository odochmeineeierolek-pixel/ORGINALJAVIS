[Setup]
AppName=YAVIS
AppVersion=1.0.0
AppPublisher=YAVIS
DefaultDirName={autopf}\YAVIS
DefaultGroupName=YAVIS
OutputDir=installer
OutputBaseFilename=YAVIS-Setup
Compression=lzma2/fast
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\YAVIS.exe

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"
Name: "autostart"; Description: "YAVIS beim Windows-Start automatisch starten"; Flags: unchecked

[Files]
Source: "dist\YAVIS\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autodesktop}\YAVIS"; Filename: "{app}\YAVIS.exe"; Tasks: desktopicon
Name: "{group}\YAVIS"; Filename: "{app}\YAVIS.exe"
Name: "{userstartup}\YAVIS"; Filename: "{app}\YAVIS.exe"; Tasks: autostart

[Run]
Filename: "{app}\YAVIS.exe"; Description: "YAVIS jetzt starten"; Flags: nowait postinstall skipifsilent
