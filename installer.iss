#define MyAppName "Laravel Suite"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Korvexa"
#define MyAppURL "https://korvexa.app"
#define MyAppExeName "LaravelSuite.exe"

[Setup]
AppId={{6C8A9F51-7B43-4D97-9B4A-3F68C7A63A91}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

DisableProgramGroupPage=yes

OutputDir=Installer
OutputBaseFilename=LaravelSuite-Setup-v1.0.0

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

SetupIconFile=assets\app_logo.ico
UninstallDisplayIcon={app}\LaravelSuite.exe

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

PrivilegesRequired=admin

VersionInfoVersion=1.0.0
VersionInfoCompany=Korvexa
VersionInfoDescription=Laravel Development Suite
VersionInfoProductName=Laravel Suite
VersionInfoCopyright=© Korvexa

WizardImageFile=assets\wizard.bmp
WizardSmallImageFile=assets\wizard-small.bmp

LicenseFile=LICENSE.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create Desktop Shortcut"; GroupDescription: "Additional Shortcuts:"; Flags: unchecked

[Files]
Source: "dist\LaravelSuite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Laravel Suite"; Filename: "{app}\LaravelSuite.exe"
Name: "{autodesktop}\Laravel Suite"; Filename: "{app}\LaravelSuite.exe"; Tasks: desktopicon