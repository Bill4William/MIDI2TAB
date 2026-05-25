; ---------------------------------------------------------------
; MIDI2TAB  —  Inno Setup installer script
; Compile with:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss
; ---------------------------------------------------------------

#define MyAppName      "MIDI2TAB"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "MIDI2TAB"
#define MyAppExeName   "MIDI2TAB.exe"

[Setup]
; Unique application identifier — do not reuse for other apps
AppId={{9F8E2D7A-4B3C-4E1F-9A2B-5C6D7E8F9A0B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Allow user to install without admin rights
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
AllowNoIcons=yes
; Output
OutputDir=..\installer_output
OutputBaseFilename=MIDI2TAB_Setup_v{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
; Compression
Compression=lzma2/ultra64
SolidCompression=yes
; Appearance
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; \
  Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"; \
  Flags: unchecked

[Files]
; All files from the PyInstaller output folder
Source: "..\dist\{#MyAppName}\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}";                    Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Optional desktop shortcut
Name: "{autodesktop}\{#MyAppName}"; \
  Filename: "{app}\{#MyAppExeName}"; \
  Tasks: desktopicon

[Run]
; Offer to launch the app after installation
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#MyAppName}}"; \
  Flags: nowait postinstall skipifsilent
