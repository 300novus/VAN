import os

print("📏 Убираем лишние боковые отступы в PDF...")

for file in ['templates/view_proposal.html', 'templates/view_proposal_2.html']:
    if not os.path.exists(file):
        continue
        
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Ищем вчерашние широкие отступы и меняем их
    # Оставляем только верх и низ (по 15мм), а бока делаем 0
    if "margin: 20mm 15mm 20mm 15mm;" in content:
        # Вариант с комментарием
        content = content.replace(
            "margin: 20mm 15mm 20mm 15mm; /* Верх, Право, Низ, Лево */", 
            "margin: 15mm 0mm 15mm 0mm; /* Верх 15мм, Бока 0мм, Низ 15мм */"
        )
        # Запасной вариант без комментария
        content = content.replace(
            "margin: 20mm 15mm 20mm 15mm;", 
            "margin: 15mm 0mm 15mm 0mm;"
        )
        
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Боковые отступы в {file} убраны!")
    else:
        print(f"⏩ В {file} старые отступы не найдены (или уже изменены).")

print("🎉 Готово! Жми F5 в браузере и проверяй.")