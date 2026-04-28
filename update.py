import os
import re
import shutil

print("🛠️ Запуск исправления дизайна и модуля категорий...")

files_to_patch = {
    'base': 'templates/base.html',
    'app': 'app.py',
    'categories': 'templates/categories.html'
}

# 1. Бэкап
for f in files_to_patch.values():
    if os.path.exists(f):
        shutil.copy2(f, f + '.bak_v2')

# 2. ИСПРАВЛЕНИЕ ДИЗАЙНА (Modern Industrial)
if os.path.exists(files_to_patch['base']):
    with open(files_to_patch['base'], 'r', encoding='utf-8') as f:
        content = f.read()

    # Заменяем старый патч редизайна на новый, более мягкий и современный
    modern_css = """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --slate-900: #0f172a;
            --slate-200: #e2e8f0;
            --accent: #2563eb;
        }
        
        body { font-family: 'Inter', sans-serif !important; background-color: #f1f5f9 !important; color: var(--slate-900) !important; }

        /* МЯГКИЕ СОВРЕМЕННЫЕ КНОПКИ */
        button, .btn, [class*="bg-blue-"] {
            border-radius: 10px !important;
            border: 1px solid rgba(15, 23, 42, 0.1) !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06) !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important; /* Плавные переходы */
            text-transform: none !important;
            font-weight: 600 !important;
            letter-spacing: normal !important;
        }

        button:hover, [class*="bg-blue-"]:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1) !important;
            filter: brightness(110%);
        }

        /* ТЕНИ ДЛЯ КАРТОЧЕК (Уходим от жестких рамок) */
        .shadow, .shadow-md, .shadow-lg, .shadow-xl {
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05) !important;
            border: 1px solid rgba(226, 232, 240, 0.8) !important;
            border-radius: 16px !important;
            background: #fff !important;
        }

        /* СТАТУСЫ (Плотные, но аккуратные) */
        span[class*="rounded-full"][class*="bg-"] {
            border-radius: 8px !important;
            border: none !important;
            box-shadow: none !important;
            font-size: 11px !important;
            padding: 4px 12px !important;
            font-weight: 700 !important;
            opacity: 0.9;
        }

        /* ИНПУТЫ */
        input:not([type="file"]), select, textarea {
            border-radius: 10px !important;
            border: 1px solid var(--slate-200) !important;
            transition: border-color 0.2s, box-shadow 0.2s !important;
        }
        input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1) !important; }
    </style>
    """
    # Убираем старый жесткий патч если он был
    content = re.sub(r'.*?', '', content, flags=re.DOTALL)
    if "MODERN INDUSTRIAL PATCH" not in content:
        content = content.replace("</head>", modern_css + "\n</head>")
    
    with open(files_to_patch['base'], 'w', encoding='utf-8') as f:
        f.write(content)

# 3. ИСПРАВЛЕНИЕ ЗАГРУЗКИ ИКОНОК В APP.PY
if os.path.exists(files_to_patch['app']):
    with open(files_to_patch['app'], 'r', encoding='utf-8') as f:
        app_content = f.read()
    
    # Исправляем путь к иконкам и метод их получения
    # Мы ищем список иконок в функции маршрута категорий
    old_icon_logic = """icons = os.listdir(os.path.join('static', 'category_icons'))"""
    new_icon_logic = """
    icon_path = os.path.join(app.static_folder, 'category_icons')
    if not os.path.exists(icon_path): os.makedirs(icon_path)
    icons = [f for f in os.listdir(icon_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.svg'))]
    """
    if "os.listdir" in app_content:
        # Прямая замена логики формирования списка иконок
        app_content = re.sub(r"icons\s*=\s*os\.listdir\(.*?'category_icons'.*?\)", new_icon_logic, app_content)

    with open(files_to_patch['app'], 'w', encoding='utf-8') as f:
        f.write(app_content)

# 4. ОБНОВЛЕНИЕ ШАБЛОНА КАТЕГОРИЙ (Для отображения иконок)
if os.path.exists(files_to_patch['categories']):
    with open(files_to_patch['categories'], 'r', encoding='utf-8') as f:
        cat_html = f.read()
    
    # Убеждаемся, что цикл в модальном окне правильно строит пути
    cat_html = cat_html.replace("url_for('static', filename='category_icons/' + icon)", "url_for('static', filename='category_icons/' ~ icon)")
    
    with open(files_to_patch['categories'], 'w', encoding='utf-8') as f:
        f.write(cat_html)

print("🚀 Все исправлено! Дизайн стал мягче, а иконки должны появиться. Перезапусти сервер.")