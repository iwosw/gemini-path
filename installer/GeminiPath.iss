#define AppName "GeminiPath"
#define AppVersion "0.2.0"

[Setup]
AppId={{1ddde26a-ab76-43cd-beb7-2ab15856ad25}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=iwosw
AppPublisherURL=https://github.com/iwosw/gemini-path
AppSupportURL=https://github.com/iwosw/gemini-path/issues
DefaultDirName={localappdata}\Programs\GeminiPath
DefaultGroupName=GeminiPath
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
WizardStyle=modern
SetupIconFile=..\dist\GeminiPath.ico
UninstallDisplayIcon={app}\GeminiPath.exe
OutputDir=..\dist
OutputBaseFilename=GeminiPath-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\GeminiPath.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\GeminiPath.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\GeminiPath"; Filename: "{app}\GeminiPath.exe"
Name: "{autodesktop}\GeminiPath"; Filename: "{app}\GeminiPath.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GeminiPath.exe"; Description: "{cm:LaunchProgram,GeminiPath}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeUninstall(): Boolean;
var
  Prompt: String;
begin
  Result := True;
  if FileExists(ExpandConstant('{localappdata}\GeminiPath\patches\antigravity.json')) then begin
    if ActiveLanguage() = 'russian' then
      Prompt := 'Обнаружен активный патч Antigravity. Лучше сначала открыть GeminiPath и нажать «Откатить». Если продолжить удаление, резервная копия останется в AppData: после повторной установки GeminiPath можно выполнить откат. Продолжить?'
    else
      Prompt := 'An Antigravity patch is still recorded. Restore it in GeminiPath before uninstalling. If you continue, the backup stays in AppData so you can reinstall and restore later. Continue?';
    Result := MsgBox(Prompt, mbConfirmation, MB_YESNO) = IDYES;
  end;
end;
