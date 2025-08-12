Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\meuze\OneDrive\Рабочий стол\тг\tgshop-bot"

' Вариант 1: запуск из venv по относительному пути (рекомендуется)
cmd = "cmd /c "".\.venv\Scripts\python.exe"" bot.py"
sh.Run cmd, 0, False
