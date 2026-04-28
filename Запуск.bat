@echo off
echo Устанавливаем нейросеть (если еще не установлена)...
py -m pip install --upgrade google-generativeai pillow
echo Запускаем Chingiskhan Pro V11...
start http://127.0.0.1:5000
py app.py
pause