import os

def fix_ai_logic():
    path = 'templates/create_proposal.html'
    if not os.path.exists(path):
        print("Файл не найден!")
        return

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Ищем, где начинается старый глючный скрипт ИИ (если он там есть)
    if "// --- AI FRONTEND LOGIC ---" in content:
        start_idx = content.find("// --- AI FRONTEND LOGIC ---")
        content = content[:start_idx] # Отрезаем старый ИИ-код
    else:
        # Если его там нет, отрезаем перед закрывающим тегом script
        start_idx = content.rfind('</script>')
        content = content[:start_idx]

    # Правильный, доработанный код
    corrected_js = """
// --- AI FRONTEND LOGIC ---
async function describeWithAI(inputId, blockId, btnElement) {
    const input = document.getElementById(inputId);
    if (!input || !input.files[0]) {
        alert('Сначала выберите или загрузите фото!');
        return;
    }
    
    const originalHtml = btnElement.innerHTML;
    btnElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Думаю...';
    btnElement.disabled = true;
    btnElement.classList.add('opacity-75', 'cursor-not-allowed');

    const formData = new FormData();
    formData.append('image', input.files[0]);

    try {
        const response = await fetch('/api/ai_describe', { method: 'POST', body: formData });
        const data = await response.json();
        
        if (data.text) {
            // Ищем редактор по data-id (так как у него нет обычного ID)
            const editor = document.querySelector(`div[data-id="${blockId}"]`);
            if (editor) {
                if(editor.innerHTML.includes('Введите текст...')) editor.innerHTML = '';
                editor.innerHTML += '<br><br><b>Описание ИИ:</b> ' + data.text.replace(/\\n/g, '<br>');
                // Обновляем скрытый инпут
                if (typeof updateRichText === 'function') updateRichText(editor);
            } else {
                alert('Редактор текста не найден!');
            }
        } else {
            alert('Ошибка ИИ: ' + (data.error || 'Неизвестная ошибка'));
        }
    } catch (e) {
        alert('Ошибка связи с сервером ИИ.');
    } finally {
        btnElement.innerHTML = originalHtml;
        btnElement.disabled = false;
        btnElement.classList.remove('opacity-75', 'cursor-not-allowed');
    }
}

document.addEventListener('change', function(e) {
    // Теперь мы ищем ЛЮБОЕ фото в текстовом блоке (in1_t_, in2_t_, in3_t_)
    if (e.target && e.target.type === 'file' && e.target.id.includes('_t_')) {
        const blockId = e.target.id.split('_')[2]; // Достаем уникальный ID блока
        const wrapper = e.target.closest('.relative');
        
        // Добавляем кнопку, если её еще нет
        if (wrapper && !wrapper.querySelector('.ai-magic-btn')) {
            const aiBtn = document.createElement('button');
            aiBtn.type = 'button';
            // Используем z-index и relative, чтобы кнопка всегда была кликабельной поверх картинок
            aiBtn.className = 'ai-magic-btn mt-2 w-full bg-blue-600 hover:bg-blue-700 text-white text-[10px] font-black uppercase tracking-widest py-2 px-3 rounded-xl transition shadow-md flex items-center justify-center gap-2 relative z-50';
            aiBtn.innerHTML = '<i class="fas fa-magic text-yellow-300"></i> Описать ИИ';
            aiBtn.onclick = function() {
                describeWithAI(e.target.id, blockId, this);
            };
            wrapper.appendChild(aiBtn);
        }
    }
});
</script>
"""
    # Склеиваем обратно
    new_content = content + corrected_js
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("✅ Логика кнопки ИИ исправлена!")

if __name__ == "__main__":
    fix_ai_logic()