import os

def patch_app():
    path = 'app.py'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Проверяем, есть ли уже такой роут, чтобы не дублировать
    if '/api/get_local_icons' in content:
        print("Маршрут уже существует.")
        return

    # Код нового маршрута
    new_route = """
@app.route('/api/get_local_icons')
def get_local_icons():
    # Используем абсолютный путь для надежности
    folder = os.path.join(app.static_folder, 'category_icons')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # Получаем список файлов и фильтруем только картинки
    icons = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.svg', '.jpg', '.webp'))]
    return jsonify(icons)
"""

    # Вставляем перед запуском приложения
    if "if __name__ == '__main__':" in content:
        content = content.replace("if __name__ == '__main__':", new_route + "\nif __name__ == '__main__':")
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Маршрут /api/get_local_icons успешно добавлен в app.py")
    else:
        print("❌ Не удалось найти точку входа в app.py")

if __name__ == "__main__":
    patch_app()