import os
import re
import shutil

print("Запуск обновления UI загрузки фотографий...")

files_to_patch = {
    'create': 'templates/create_proposal.html',
    'edit': 'templates/edit_proposal.html'
}

# 1. Бэкап
def backup(filepath):
    if os.path.exists(filepath):
        shutil.copy2(filepath, filepath + '.bak_ui')
        print(f"📦 Создан бэкап: {filepath}.bak_ui")

for f in files_to_patch.values():
    backup(f)

# 2. Новые функции JavaScript
new_preview = """function previewImageRow(input) { 
    const p = input.nextElementSibling; 
    if(input.files && input.files[0]) { 
        const r = new FileReader(); 
        r.onload = function(e){ 
            p.src=e.target.result; 
            p.classList.remove('hidden'); 
            const btn = p.parentElement.querySelector('button');
            if(btn) { btn.classList.remove('hidden'); btn.style.display = 'flex'; }
        }; 
        r.readAsDataURL(input.files[0]); 
    } 
}"""

new_clear = """function clearImage(inputId, previewId, hiddenId) { 
    if(document.getElementById(inputId)) document.getElementById(inputId).value=''; 
    const p=document.getElementById(previewId); 
    if(p) {
        p.src='#'; 
        p.classList.add('hidden'); 
        const btn = p.parentElement.querySelector('button');
        if(btn) { btn.classList.add('hidden'); btn.style.display = 'none'; }
    }
    if(hiddenId && document.getElementById(hiddenId)) document.getElementById(hiddenId).value=''; 
    if(document.getElementById(inputId)) {
        const row = document.getElementById(inputId).closest('.block-row');
        if(row && typeof updateLiveCover === 'function') updateLiveCover(row);
    }
}"""

js_injection = """
// --- INJECTED UI UPGRADE FOR FILE INPUTS ---
function upgradeFileInputs() {
    document.querySelectorAll('input[type="file"]').forEach(inp => {
        if(inp.dataset.upgraded) return;
        inp.dataset.upgraded = 'true';
        
        const wrapper = inp.closest('.relative');
        if(!wrapper || wrapper.classList.contains('no-upgrade')) return;
        
        // Стилизуем обертку (делаем красивую рамку)
        wrapper.classList.add('h-24', 'border-2', 'border-dashed', 'border-gray-300', 'rounded-2xl', 'flex', 'items-center', 'justify-center', 'bg-gray-50', 'hover:bg-gray-100', 'transition', 'overflow-hidden', 'group', 'w-full');
        
        // Прячем стандартный инпут, но оставляем его кликабельным поверх всего
        inp.className = 'absolute inset-0 opacity-0 cursor-pointer z-10 w-full h-full';
        
        // Добавляем красивую иконку облака и текст "Загрузить"
        const uiBg = document.createElement('div');
        uiBg.className = 'absolute inset-0 flex flex-col items-center justify-center text-gray-400 group-hover:text-blue-500 pointer-events-none transition z-0';
        uiBg.innerHTML = '<i class="fas fa-cloud-upload-alt text-2xl mb-1"></i><span class="text-[9px] font-black uppercase tracking-widest">Загрузить</span>';
        wrapper.appendChild(uiBg);
        
        // Стилизуем саму картинку, когда она загрузится
        const img = inp.nextElementSibling;
        if(img && img.tagName === 'IMG') {
            img.classList.remove('h-20', 'aspect-square', 'border', 'border-gray-200', 'rounded-lg', 'rounded-xl');
            img.classList.add('absolute', 'inset-0', 'w-full', 'h-full', 'object-cover', 'z-20', 'pointer-events-none', 'bg-white');
        }
        
        // Стилизуем кнопку удаления (делаем ее современной)
        const btn = wrapper.querySelector('button');
        if(btn) {
            btn.classList.remove('top-8', 'w-6', 'h-6', 'rounded-full', 'text-xs');
            btn.classList.add('top-2', 'right-2', 'w-8', 'h-8', 'rounded-xl', 'shadow-lg', 'flex', 'items-center', 'justify-center', 'z-30', 'hover:scale-110', 'bg-red-500', 'hover:bg-red-600', 'text-white', 'transition');
            
            // Синхронизируем видимость кнопки с картинкой
            if(img && img.classList.contains('hidden')) {
                btn.classList.add('hidden');
                btn.style.display = 'none';
            } else {
                btn.classList.remove('hidden');
                btn.style.display = 'flex';
            }
        }
    });
}

// Автоматически применяем стили ко всем новым блокам, которые ты добавляешь
const observer = new MutationObserver(mutations => {
    mutations.forEach(mutation => {
        if(mutation.addedNodes.length) upgradeFileInputs();
    });
});
const blocksList = document.getElementById('blocksList');
if(blocksList) observer.observe(blocksList, { childList: true, subtree: true });

// Запускаем при загрузке страницы
document.addEventListener('DOMContentLoaded', upgradeFileInputs);
// ------------------------------------------
"""

def apply_patch(filepath):
    if not os.path.exists(filepath):
        print(f"⚠️ Файл не найден: {filepath}")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Заменяем логику превью
    content = re.sub(
        r'function previewImageRow\(input\)\s*\{.*?\.readAsDataURL\(input\.files\[0\]\);\s*\}\s*\}',
        new_preview,
        content,
        flags=re.DOTALL
    )
    
    # 2. Заменяем логику очистки
    content = re.sub(
        r'function clearImage\(inputId,\s*previewId,\s*hiddenId\)\s*\{.*?\.closest\(\'\.block-row\'\)\);\s*\}',
        new_clear,
        content,
        flags=re.DOTALL
    )
    
    # 3. Внедряем наш супер-скрипт обновления дизайна перед концом </script>
    if "upgradeFileInputs()" not in content:
        last_script_idx = content.rfind('</script>')
        if last_script_idx != -1:
            content = content[:last_script_idx] + js_injection + "\n" + content[last_script_idx:]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Успешно обновлен: {filepath}")

for path in files_to_patch.values():
    apply_patch(path)

print("🚀 Патч UI применен! Зайди в создание КП и оцени новые кнопки.")