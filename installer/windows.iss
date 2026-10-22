#define AppName "数学建模论文评审工作台"
#define AppExe "MathModelingPaperReview.exe"

[Setup]
AppId={{D1D3F190-7E1C-4F47-B2E9-6AB3D9BC9C44}
AppName={#AppName}
AppVersion=0.1.0
AppPublisher=Evaluation of Mathematical Modeling Papers
DefaultDirName={localappdata}\Programs\MathModelingPaperReview
DefaultGroupName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename=MathModelingPaperReview-Setup-0.1.0-x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: unchecked

[Files]
Source: "..\dist\MathModelingPaperReview\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "启动{#AppName}"; Flags: nowait postinstall skipifsilent
