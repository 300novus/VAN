import os
import re
import shutil

print("Запуск обновления модуля 'Текст / Стиль'...")

# Файлы для обновления
files_to_patch = {
    'app': 'app.py',
    'create': 'templates/create_proposal.html',
    'edit': 'templates/edit_proposal.html',
    'view': 'templates/view_proposal.html'
}

# 1. Функция создания бэкапа
def backup(filepath):
    if os.path.exists(filepath):
        shutil.copy2(filepath, filepath + '.bak')
        print(f"📦 Создан бэкап: {filepath}.bak")

for f in files_to_patch.values():
    backup(f)

# 2. Обновление app.py (Бэкенд)
if os.path.exists(files_to_patch['app']):
    with open(files_to_patch['app'], 'r', encoding='utf-8') as f:
        app_code = f.read()
    
    app_code = app_code.replace(
        "'bc': request.form.get(f'txt_bc_{bid}'), 'bw': request.form.get(f'txt_bw_{bid}')}",
        "'bc': request.form.get(f'txt_bc_{bid}'), 'bw': request.form.get(f'txt_bw_{bid}'), 'b_style': request.form.get(f'txt_bstyle_{bid}', 'left'), 'b_rad': request.form.get(f'txt_brad_{bid}', 0)}"
    )
    app_code = app_code.replace(
        "'bc': request.form.get(f'txt_bc_{bid}', '#2563eb'), 'bw': request.form.get(f'txt_bw_{bid}', 4)}",
        "'bc': request.form.get(f'txt_bc_{bid}', '#2563eb'), 'bw': request.form.get(f'txt_bw_{bid}', 4), 'b_style': request.form.get(f'txt_bstyle_{bid}', 'left'), 'b_rad': request.form.get(f'txt_brad_{bid}', 0)}"
    )
    with open(files_to_patch['app'], 'w', encoding='utf-8') as f:
        f.write(app_code)
    print("✅ app.py обновлен.")

# 3. Обновление JS Live-Превью (Для Create и Edit)
new_js_logic = """const bStyle = row.querySelector(`[name="txt_bstyle_${id}"]`) ? row.querySelector(`[name="txt_bstyle_${id}"]`).value : 'left';
        const bRad = row.querySelector(`[name="txt_brad_${id}"]`) ? row.querySelector(`[name="txt_brad_${id}"]`).value : 0;
        previewDiv.style.backgroundColor = bg;
        previewDiv.style.color = col;
        previewDiv.style.border = 'none';
        previewDiv.style.borderRadius = `${bRad}px`;
        if (bStyle === 'all') previewDiv.style.border = `${bw}px solid ${bc}`;
        else if (bStyle === 'double') previewDiv.style.border = `${bw}px double ${bc}`;
        else if (bStyle === 'left') previewDiv.style.borderLeft = `${bw}px solid ${bc}`;
        else if (bStyle === 'right') previewDiv.style.borderRight = `${bw}px solid ${bc}`;
        else if (bStyle === 'top') previewDiv.style.borderTop = `${bw}px solid ${bc}`;
        else if (bStyle === 'bottom') previewDiv.style.borderBottom = `${bw}px solid ${bc}`;"""

def patch_js(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    # Заменяем старую логику применения стилей
    code = re.sub(
        r'previewDiv\.style\.backgroundColor\s*=\s*bg;\s*previewDiv\.style\.color\s*=\s*col;\s*previewDiv\.style\.borderLeft\s*=\s*`\$\{bw\}px solid \$\{bc\}`;',
        new_js_logic,
        code
    )
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(code)

patch_js(files_to_patch['create'])
patch_js(files_to_patch['edit'])

# 4. Обновление HTML-интерфейса блоков (Create)
if os.path.exists(files_to_patch['create']):
    with open(files_to_patch['create'], 'r', encoding='utf-8') as f:
        html = f.read()
    
    old_ui = '<div class="flex flex-col"><span class="text-[9px] font-bold text-gray-500">Толщина (px)</span><input type="number" name="txt_bw_${id}" value="4" min="0" max="20" class="w-12 h-6 text-xs text-center border rounded outline-none"></div>'
    new_ui = '<div class="flex flex-col"><span class="text-[9px] font-bold text-gray-500">Толщина</span><input type="number" name="txt_bw_${id}" value="4" min="0" max="20" class="w-12 h-6 text-xs text-center border rounded outline-none"></div>' + \
             '<div class="flex flex-col"><span class="text-[9px] font-bold text-gray-500">Рамка</span><select name="txt_bstyle_${id}" onchange="updateLiveText(this.closest(\'.block-row\'))" class="h-6 text-xs border rounded outline-none bg-white"><option value="left">Слева</option><option value="all">Полная</option><option value="double">Двойная</option><option value="right">Справа</option><option value="top">Сверху</option><option value="bottom">Снизу</option></select></div>' + \
             '<div class="flex flex-col"><span class="text-[9px] font-bold text-gray-500">Скругление</span><input type="range" name="txt_brad_${id}" value="0" min="0" max="50" oninput="updateLiveText(this.closest(\'.block-row\'))" class="w-16"></div>'
    
    html = html.replace(old_ui, new_ui)
    
    # Меняем инициализирующий стиль при добавлении блока
    html = html.replace('border-left:4px solid #2563eb;"', 'border-left:4px solid #2563eb; border-radius:0px;"')
    
    with open(files_to_patch['create'], 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ create_proposal.html обновлен.")

# 5. Обновление HTML-интерфейса блоков (Edit)
if os.path.exists(files_to_patch['edit']):
    with open(files_to_patch['edit'], 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Обновляем дефолтные значения json.loads
    html = html.replace("{'bg': '#f9fafb', 'color': '#333333', 'bc': '#2563eb', 'bw': '4'}", "{'bg': '#f9fafb', 'color': '#333333', 'bc': '#2563eb', 'bw': '4', 'b_style': 'left', 'b_rad': '0'}")
    
    # Обновляем UI панели инструментов (JinJa)
    old_edit_ui = '<div class="flex flex-col"><span class="text-[9px] font-bold text-gray-500">Толщина (px)</span><input type="number" name="txt_bw_{{ id }}" value="{{ s_txt.bw }}" min="0" max="20" class="w-12 h-6 text-xs text-center border rounded outline-none"></div>'
    new_edit_ui = '<div class="flex flex-col"><span class="text-[9px] font-bold text-gray-500">Толщина</span><input type="number" name="txt_bw_{{ id }}" value="{{ s_txt.bw }}" min="0" max="20" class="w-12 h-6 text-xs text-center border rounded outline-none"></div>' + \
                  '<div class="flex flex-col"><span class="text-[9px] font-bold text-gray-500">Рамка</span><select name="txt_bstyle_{{ id }}" onchange="updateLiveText(this.closest(\'.block-row\'))" class="h-6 text-xs border rounded outline-none bg-white"><option value="left" {% if s_txt.b_style == "left" %}selected{% endif %}>Слева</option><option value="all" {% if s_txt.b_style == "all" %}selected{% endif %}>Полная</option><option value="double" {% if s_txt.b_style == "double" %}selected{% endif %}>Двойная</option><option value="right" {% if s_txt.b_style == "right" %}selected{% endif %}>Справа</option><option value="top" {% if s_txt.b_style == "top" %}selected{% endif %}>Сверху</option><option value="bottom" {% if s_txt.b_style == "bottom" %}selected{% endif %}>Снизу</option></select></div>' + \
                  '<div class="flex flex-col"><span class="text-[9px] font-bold text-gray-500">Скругление</span><input type="range" name="txt_brad_{{ id }}" value="{{ s_txt.b_rad|default(0) }}" min="0" max="50" oninput="updateLiveText(this.closest(\'.block-row\'))" class="w-16"></div>'
    html = html.replace(old_edit_ui, new_edit_ui)
    
    # Меняем рендер стиля (JinJa)
    old_style = 'style="background-color:{{ s_txt.bg }}; color:{{ s_txt.color }}; border-left:{{ s_txt.bw }}px solid {{ s_txt.bc }};"'
    new_style = "{% set border_css = 'border: ' ~ s_txt.bw ~ 'px solid ' ~ s_txt.bc if s_txt.b_style == 'all' else 'border: ' ~ s_txt.bw ~ 'px double ' ~ s_txt.bc if s_txt.b_style == 'double' else 'border-right: ' ~ s_txt.bw ~ 'px solid ' ~ s_txt.bc if s_txt.b_style == 'right' else 'border-top: ' ~ s_txt.bw ~ 'px solid ' ~ s_txt.bc if s_txt.b_style == 'top' else 'border-bottom: ' ~ s_txt.bw ~ 'px solid ' ~ s_txt.bc if s_txt.b_style == 'bottom' else 'border-left: ' ~ s_txt.bw ~ 'px solid ' ~ s_txt.bc %}\n                            style=\"background-color:{{ s_txt.bg }}; color:{{ s_txt.color }}; {{ border_css }}; border-radius:{{ s_txt.b_rad|default(0) }}px;\""
    html = html.replace(old_style, new_style)
    
    with open(files_to_patch['edit'], 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ edit_proposal.html обновлен.")

# 6. Обновление view_proposal.html (Рендер для клиента / PDF)
if os.path.exists(files_to_patch['view']):
    with open(files_to_patch['view'], 'r', encoding='utf-8') as f:
        html = f.read()
    
    html = html.replace("{'bg': '#f9fafb', 'color': '#333333', 'bc': '#2563eb', 'bw': '4'}", "{'bg': '#f9fafb', 'color': '#333333', 'bc': '#2563eb', 'bw': '4', 'b_style': 'left', 'b_rad': '0'}")
    
    old_view_div = '<div class="block-text" style="background-color: {{ s_txt.bg }}; color: {{ s_txt.color }}; border-left: {{ s_txt.bw }}px solid {{ s_txt.bc }};">'
    new_view_div = "{% set border_css = 'border: ' ~ s_txt.bw ~ 'px solid ' ~ s_txt.bc if s_txt.b_style == 'all' else 'border: ' ~ s_txt.bw ~ 'px double ' ~ s_txt.bc if s_txt.b_style == 'double' else 'border-right: ' ~ s_txt.bw ~ 'px solid ' ~ s_txt.bc if s_txt.b_style == 'right' else 'border-top: ' ~ s_txt.bw ~ 'px solid ' ~ s_txt.bc if s_txt.b_style == 'top' else 'border-bottom: ' ~ s_txt.bw ~ 'px solid ' ~ s_txt.bc if s_txt.b_style == 'bottom' else 'border-left: ' ~ s_txt.bw ~ 'px solid ' ~ s_txt.bc %}\n                <div class=\"block-text\" style=\"background-color: {{ s_txt.bg }}; color: {{ s_txt.color }}; {{ border_css }}; border-radius: {{ s_txt.b_rad|default(0) }}px;\">"
    
    html = html.replace(old_view_div, new_view_div)
    
    with open(files_to_patch['view'], 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ view_proposal.html обновлен.")

print("🚀 Патч успешно применен! Теперь перезапусти сервер Flask.")