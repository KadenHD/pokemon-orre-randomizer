[Setup]
AppId={{2EDE9291-8972-4361-9A05-3CC158B9D54B}
AppName=Pokémon Orre Randomizer
AppVersion={#ReleaseVersion}
AppPublisher=Pokémon Orre Randomizer contributors
AppPublisherURL=https://github.com/KadenHD/pokemon-orre-randomizer
DefaultDirName={localappdata}\Programs\Pokémon Orre Randomizer
DefaultGroupName=Pokémon Orre Randomizer
DisableProgramGroupPage=yes
AllowNoIcons=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile=..\orre_randomizer\assets\app\icon.ico
UninstallDisplayIcon={app}\OrreRandomizer.exe
Compression=lzma2
SolidCompression=yes
OutputBaseFilename=pokemon-orre-randomizer-{#ReleaseVersion}-windows-x64-setup

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Pokémon Orre Randomizer"; Filename: "{app}\OrreRandomizer.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\OrreRandomizer.exe"; WorkingDir: "{app}"; Description: "Open Pokémon Orre Randomizer"; Flags: nowait postinstall skipifsilent
