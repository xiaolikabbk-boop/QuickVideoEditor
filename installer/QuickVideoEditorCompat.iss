#define MyAppVersion GetEnv("APP_VERSION")
#define MySourceDir GetEnv("APP_SOURCE_DIR")
#define MyOutputDir GetEnv("INSTALLER_OUTPUT_DIR")

[Setup]
AppId={{D203C581-E435-49DD-946E-FC9074FB7A44}
AppName=批量配乐工具
AppVersion={#MyAppVersion}
AppVerName=批量配乐工具 {#MyAppVersion}
AppPublisher=xiaolikabbk-boop
AppPublisherURL=https://github.com/xiaolikabbk-boop/QuickVideoEditor
AppSupportURL=https://github.com/xiaolikabbk-boop/QuickVideoEditor/issues
DefaultDirName={localappdata}\Programs\QuickVideoEditor
DefaultGroupName=批量配乐工具
UninstallDisplayIcon={app}\批量配乐工具.exe
OutputDir={#MyOutputDir}
OutputBaseFilename=Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
SetupLogging=yes
UseSetupLdr=no

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\批量配乐工具"; Filename: "{app}\批量配乐工具.exe"
Name: "{autodesktop}\批量配乐工具"; Filename: "{app}\批量配乐工具.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\批量配乐工具.exe"; Description: "启动批量配乐工具"; Flags: nowait postinstall skipifsilent
