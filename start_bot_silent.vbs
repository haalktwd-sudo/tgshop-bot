Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\meuze\OneDrive\Рабочий стол\тг\tgshop-bot"

' Вариант 2: абсолютный путь к python.exe
cmd = "cmd /c ""C:\Users\meuze\AppData\Local\Programs\Python\Python310\python.exe"" bot.py"
sh.Run cmd, 0, False
