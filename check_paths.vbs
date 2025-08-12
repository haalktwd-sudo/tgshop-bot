Set fso = CreateObject("Scripting.FileSystemObject")
base = "C:\Users\meuze\OneDrive\Рабочий стол\тг\tgshop-bot"
venvpy = base & "\.venv\Scripts\python.exe"
bot = base & "\bot.py"

msg = ""
If fso.FolderExists(base) Then
  msg = msg & "OK folder: " & base & vbCrLf
Else
  msg = msg & "NO folder: " & base & vbCrLf
End If
If fso.FileExists(venvpy) Then
  msg = msg & "OK venv python: " & venvpy & vbCrLf
Else
  msg = msg & "NO venv python: " & venvpy & vbCrLf
End If
If fso.FileExists(bot) Then
  msg = msg & "OK bot: " & bot & vbCrLf
Else
  msg = msg & "NO bot: " & bot & vbCrLf
End If

MsgBox msg
