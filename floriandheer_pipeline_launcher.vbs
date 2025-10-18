' InvisibleLauncher.vbs - Launches Python script invisibly
' Get the directory where this .vbs file is located
strScriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
' Define path to your Python script (relative to this .vbs file)
strPythonScript = strScriptDir & "\floriandheer_pipeline.py"

' Create a shell object
Set objShell = CreateObject("WScript.Shell")

' Run the Python script invisibly using pythonw.exe to ensure no terminal window
' The 0 parameter makes it completely hidden
' The False parameter makes it not wait for completion
objShell.Run "pythonw.exe """ & strPythonScript & """", 0, False

' Clean up
Set objShell = Nothing