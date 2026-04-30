from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import time
import os
import shutil
import json
from datetime import datetime

import google.generativeai as genai
import PIL.Image
import io

# Читаем ключ из спрятанного файла
try:
    with open('api_key.txt', 'r', encoding='utf-8') as f:
        API_KEY = f.read().strip()
    genai.configure(api_key=API_KEY)
except FileNotFoundError:
    print("ВНИМАНИЕ: Файл api_key.txt не найден! ИИ работать не будет.")


app = Flask(__name__)
DB_NAME = 'chingiskhan_v5.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('templates', exist_ok=True)

def get_categories():
    with sqlite3.connect(DB_NAME) as conn:
        cats_db = conn.cursor().execute("SELECT * FROM categories ORDER BY name").fetchall()
        return [{'id': str(r[0]), 'name': str(r[1]), 'icon': str(r[2])} for r in cats_db]

def num2words_ru(n):
    units = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
    teens = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать', 'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать']
    tens = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
    hundreds = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 'шестьсот', 'семьсот', 'восемьсот', 'девятьсот']
    def convert_block(num, is_thousands=False):
        res = []
        h, t, u = num // 100, (num % 100) // 10, num % 10
        if h > 0: res.append(hundreds[h])
        if t == 1: res.append(teens[u])
        else:
            if t > 1: res.append(tens[t])
            if u > 0:
                if is_thousands and u == 1: res.append('одна')
                elif is_thousands and u == 2: res.append('две')
                else: res.append(units[u])
        return ' '.join(res)
    if n == 0: return 'ноль тенге 00 тиын'
    integer_part = int(n)
    fractional_part = int(round((n - integer_part) * 100))
    parts = []
    mil, tho, rem = integer_part // 1000000, (integer_part % 1000000) // 1000, integer_part % 1000
    if mil > 0:
        parts.append(convert_block(mil))
        parts.append('миллионов' if 5 <= mil % 20 <= 19 or mil % 10 in [0,5,6,7,8,9] else 'миллион' if mil % 10 == 1 else 'миллиона')
    if tho > 0:
        parts.append(convert_block(tho, True))
        parts.append('тысяч' if 5 <= tho % 20 <= 19 or tho % 10 in [0,5,6,7,8,9] else 'тысяча' if tho % 10 == 1 else 'тысячи')
    if rem > 0 or integer_part == 0: parts.append(convert_block(rem))
    res_str = ' '.join(parts).strip().capitalize() + f' тенге {fractional_part:02d} тиын'
    return res_str

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS clients (id TEXT PRIMARY KEY, name TEXT, bin TEXT, contact TEXT, address TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS invoices (id TEXT PRIMARY KEY, client_id TEXT, date TEXT, subtotal REAL, vat_rate REAL, vat_amount REAL, total REAL, status INTEGER DEFAULT 0, knp TEXT DEFAULT "859", markup REAL DEFAULT 0)')
        c.execute('CREATE TABLE IF NOT EXISTS invoice_items (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id TEXT, item TEXT, unit TEXT, qty REAL, price REAL, total REAL)')
        c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS knp_directory (code TEXT PRIMARY KEY, name TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS internal_costs (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id TEXT, label TEXT, value REAL)')
        c.execute('CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, client_id TEXT, date TEXT, project_name TEXT, total REAL, status INTEGER DEFAULT 0)')
        c.execute('CREATE TABLE IF NOT EXISTS proposal_blocks (id INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT, block_type TEXT, sort_order INTEGER, title TEXT, text_content TEXT, qty REAL, price REAL, unit TEXT, img1 TEXT, img2 TEXT, img3 TEXT, items_json TEXT, cost REAL DEFAULT 0)')
        c.execute('CREATE TABLE IF NOT EXISTS catalog (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, unit TEXT, cost REAL, retail_price REAL, img1 TEXT, img2 TEXT, img3 TEXT, category_id INTEGER DEFAULT 0, bom_json TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, icon TEXT)')
        try: c.execute("ALTER TABLE proposal_blocks ADD COLUMN items_json TEXT")
        except: pass
        try: c.execute("ALTER TABLE proposal_blocks ADD COLUMN cost REAL DEFAULT 0")
        except: pass
        try: c.execute("ALTER TABLE catalog ADD COLUMN category_id INTEGER DEFAULT 0")
        except: pass
        try: c.execute("ALTER TABLE catalog ADD COLUMN bom_json TEXT")
        except: pass
        c.execute("SELECT COUNT(*) FROM categories")
        if c.fetchone()[0] == 0:
            defaults = [('Скамейки', 'fa-chair'), ('Урны', 'fa-trash-alt'), ('Освещение', 'fa-lightbulb'), ('Прочее', 'fa-cube')]
            for n, i in defaults: c.execute("INSERT INTO categories (name, icon) VALUES (?, ?)", (n, i))
        defaults_sets = [('company_name', 'ИП "ЧИНГИЗХАН"'), ('company_bin', '881221301113'), ('company_bank', 'АО "ForteBank"'), ('company_iban', 'KZ1796502F0021560313KZT'), ('company_address', 'г. Алматы'), ('company_bik', 'IRTYKZKA'), ('company_kbe', '19')]
        for key, val in defaults_sets: c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        conn.commit()

init_db()

def s_float(v):
    try: return float(str(v).replace(' ', '').replace(',', '.'))
    except: return 0.0

def save_file(file_obj, prefix):
    if file_obj and file_obj.filename:
        ext = file_obj.filename.split('.')[-1]
        filename = f"{prefix}_{int(time.time()*1000)}.{ext}"
        file_obj.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return ""

def copy_file(filename, new_prefix):
    if filename and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        ext = filename.split('.')[-1]
        new_name = f"{new_prefix}_{int(time.time()*1000)}.{ext}"
        shutil.copy(os.path.join(app.config['UPLOAD_FOLDER'], filename), os.path.join(app.config['UPLOAD_FOLDER'], new_name))
        return new_name
    return ""

@app.route('/')
def dashboard():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        stats = {'clients': c.execute("SELECT COUNT(*) FROM clients").fetchone()[0], 'invoices': c.execute("SELECT COUNT(*) FROM invoices").fetchone()[0], 'drafts': c.execute("SELECT COUNT(*) FROM invoices WHERE status = 0").fetchone()[0], 'pending': c.execute("SELECT COUNT(*) FROM invoices WHERE status = 1").fetchone()[0], 'paid': c.execute("SELECT COUNT(*) FROM invoices WHERE status = 2").fetchone()[0]}
        paid_invoices = c.execute("SELECT id, total FROM invoices WHERE status = 2").fetchall()
        total_revenue = sum(inv[1] for inv in paid_invoices)
        total_costs = 0
        for inv in paid_invoices:
            costs = c.execute("SELECT SUM(value) FROM internal_costs WHERE invoice_id = ?", (inv[0],)).fetchone()[0]
            if costs: total_costs += costs
        fin_stats = {'revenue': total_revenue, 'costs': total_costs, 'profit': total_revenue - total_costs, 'margin': ((total_revenue - total_costs) / total_revenue * 100) if total_revenue > 0 else 0}
        recent = c.execute("SELECT i.id, c.name, i.date, i.total, i.status FROM invoices i LEFT JOIN clients c ON i.client_id = c.id ORDER BY i.date DESC LIMIT 5").fetchall()
    return render_template('dashboard.html', **stats, fin_stats=fin_stats, recent=recent)

@app.route('/categories')
def categories_list():
    return render_template('categories.html', categories=get_categories())

@app.route('/api/add_category', methods=['POST'])
def add_category():
    d = request.json
    with sqlite3.connect(DB_NAME) as conn:
        conn.cursor().execute("INSERT INTO categories (name, icon) VALUES (?, ?)", (d['name'], d['icon']))
        conn.commit()
    return jsonify(success=True)

@app.route('/api/edit_category', methods=['POST'])
def edit_category():
    d = request.json
    with sqlite3.connect(DB_NAME) as conn:
        conn.cursor().execute("UPDATE categories SET name=?, icon=? WHERE id=?", (d['name'], d['icon'], d['id']))
        conn.commit()
    return jsonify(success=True)

@app.route('/api/delete_category/<id>', methods=['POST'])
def delete_category(id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.cursor().execute("DELETE FROM categories WHERE id=?", (id,))
        conn.cursor().execute("UPDATE catalog SET category_id=0 WHERE category_id=?", (id,))
        conn.commit()
    return jsonify(success=True)

@app.route('/catalog')
def catalog_list():
    with sqlite3.connect(DB_NAME) as conn:
        raw_items = conn.cursor().execute("SELECT id, name, description, unit, cost, retail_price, img1, img2, img3, category_id, bom_json FROM catalog ORDER BY id DESC").fetchall()
        items = [{'id': str(i[0]), 'name': str(i[1]), 'desc': str(i[2]), 'unit': str(i[3]), 'cost': float(i[4] or 0), 'retail_price': float(i[5] or 0), 'img1': str(i[6]), 'img2': str(i[7]), 'img3': str(i[8]), 'cat_id': str(i[9]), 'bom': str(i[10])} for i in raw_items]
    return render_template('catalog.html', items=items, categories=get_categories())

@app.route('/api/add_catalog', methods=['POST'])
def add_catalog():
    name, desc, unit, cat_id = request.form.get('name'), request.form.get('description'), request.form.get('unit', 'шт.'), request.form.get('category_id', 0)
    cost, retail = s_float(request.form.get('cost')), s_float(request.form.get('retail_price'))
    bom_names, bom_prices = request.form.getlist('bom_name[]'), request.form.getlist('bom_price[]')
    bom = [{'name': bom_names[i], 'price': s_float(bom_prices[i])} for i in range(len(bom_names))]
    bom_json = json.dumps(bom, ensure_ascii=False)
    t = int(time.time()*1000)
    i1, i2, i3 = save_file(request.files.get('img1'), f"cat_{t}_1"), save_file(request.files.get('img2'), f"cat_{t}_2"), save_file(request.files.get('img3'), f"cat_{t}_3")
    with sqlite3.connect(DB_NAME) as conn:
        conn.cursor().execute("INSERT INTO catalog (name, description, unit, cost, retail_price, img1, img2, img3, category_id, bom_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (name, desc, unit, cost, retail, i1, i2, i3, cat_id, bom_json))
        conn.commit()
    return redirect(url_for('catalog_list'))

@app.route('/api/edit_catalog', methods=['POST'])
def edit_catalog():
    item_id, name, desc, unit, cat_id = request.form.get('item_id'), request.form.get('name'), request.form.get('description'), request.form.get('unit'), request.form.get('category_id', 0)
    cost, retail = s_float(request.form.get('cost')), s_float(request.form.get('retail_price'))
    bom_names, bom_prices = request.form.getlist('bom_name[]'), request.form.getlist('bom_price[]')
    bom = [{'name': bom_names[i], 'price': s_float(bom_prices[i])} for i in range(len(bom_names))]
    bom_json = json.dumps(bom, ensure_ascii=False)
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        item = c.execute("SELECT img1, img2, img3 FROM catalog WHERE id=?", (item_id,)).fetchone()
        i1, i2, i3 = item[0], item[1], item[2]
        t = int(time.time()*1000)
        n1, n2, n3 = request.files.get('img1'), request.files.get('img2'), request.files.get('img3')
        if n1 and n1.filename: i1 = save_file(n1, f"cat_{t}_1")
        if n2 and n2.filename: i2 = save_file(n2, f"cat_{t}_2")
        if n3 and n3.filename: i3 = save_file(n3, f"cat_{t}_3")
        c.execute("UPDATE catalog SET name=?, description=?, unit=?, cost=?, retail_price=?, img1=?, img2=?, img3=?, category_id=?, bom_json=? WHERE id=?", (name, desc, unit, cost, retail, i1, i2, i3, cat_id, bom_json, item_id))
        conn.commit()
    return redirect(url_for('catalog_list'))

@app.route('/api/delete_catalog/<item_id>', methods=['POST'])
def delete_catalog(item_id):
    with sqlite3.connect(DB_NAME) as conn: conn.cursor().execute("DELETE FROM catalog WHERE id=?", (item_id,)); conn.commit()
    return jsonify(success=True)

@app.route('/api/get_catalog')
def get_catalog_api():
    with sqlite3.connect(DB_NAME) as conn:
        items = conn.cursor().execute("SELECT id, name, description, unit, cost, retail_price, img1, img2, img3, category_id, bom_json FROM catalog ORDER BY name").fetchall()
        result = [{'id': str(i[0]), 'name': str(i[1]), 'desc': str(i[2]), 'unit': str(i[3]), 'cost': float(i[4] or 0), 'retail_price': float(i[5] or 0), 'img1': str(i[6]), 'img2': str(i[7]), 'img3': str(i[8]), 'cat_id': str(i[9])} for i in items]
    return jsonify(result)

@app.route('/api/get_categories_json')
def get_categories_api():
    return jsonify(get_categories())

@app.route('/proposals')
def proposals_list():
    with sqlite3.connect(DB_NAME) as conn: props = conn.cursor().execute("SELECT p.id, c.name, p.project_name, p.date, p.total, p.status FROM proposals p LEFT JOIN clients c ON p.client_id = c.id ORDER BY p.date DESC").fetchall()
    return render_template('proposals.html', proposals=props)

@app.route('/create_proposal', methods=['GET', 'POST'])
def create_proposal():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if request.method == 'POST':
            cid, p_name = request.form.get('client_id'), request.form.get('project_name')
            prop_id = f"KP-{int(time.time())}"
            total = 0
            c.execute("INSERT INTO proposals (id, client_id, date, project_name, total, status) VALUES (?, ?, ?, ?, 0, 0)", (prop_id, cid, datetime.now().strftime("%d.%m.%Y"), p_name))
            block_ids = request.form.getlist('block_ids[]')
            for order, bid in enumerate(block_ids):
                b_type = request.form.get(f'b_type_{bid}')
                if b_type == 'cover':
                    title, subtitle = request.form.get(f'title_{bid}'), request.form.get(f'subtitle_{bid}')
                    i1, i2, i3 = save_file(request.files.get(f'img1_{bid}'), f"{prop_id}_c1_{bid}"), save_file(request.files.get(f'img2_{bid}'), f"{prop_id}_c2_{bid}"), save_file(request.files.get(f'img3_{bid}'), f"{prop_id}_c3_{bid}")
                    s_json = json.dumps({'angle': request.form.get(f'cov_angle_{bid}'), 'gap': request.form.get(f'cov_gap_{bid}'), 'grad': request.form.get(f'cov_grad_{bid}'), 'color': request.form.get(f'cov_color_{bid}'), 'shadow': request.form.get(f'cov_shadow_{bid}'), 'top_text': request.form.get(f'cov_top_{bid}')}, ensure_ascii=False)
                    c.execute("INSERT INTO proposal_blocks (proposal_id, block_type, sort_order, title, text_content, img1, img2, img3, items_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (prop_id, b_type, order, title, subtitle, i1, i2, i3, s_json))
                elif b_type == 'text':
                    text = request.form.get(f'text_{bid}')
                    i1, i2, i3 = save_file(request.files.get(f'img1_{bid}'), f"{prop_id}_t1_{bid}"), save_file(request.files.get(f'img2_{bid}'), f"{prop_id}_t2_{bid}"), save_file(request.files.get(f'img3_{bid}'), f"{prop_id}_t3_{bid}")
                    s_json = json.dumps({'bg': request.form.get(f'txt_bg_{bid}'), 'color': request.form.get(f'txt_color_{bid}'), 'bc': request.form.get(f'txt_bc_{bid}'), 'bw': request.form.get(f'txt_bw_{bid}'), 'b_style': request.form.get(f'txt_bstyle_{bid}', 'left'), 'b_rad': request.form.get(f'txt_brad_{bid}', 0)}, ensure_ascii=False)
                    c.execute("INSERT INTO proposal_blocks (proposal_id, block_type, sort_order, text_content, img1, img2, img3, items_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (prop_id, b_type, order, text, i1, i2, i3, s_json))
                elif b_type == 'product':
                    title, unit = request.form.get(f'title_{bid}'), request.form.get(f'unit_{bid}')
                    qty, price, cost = s_float(request.form.get(f'qty_{bid}')), s_float(request.form.get(f'price_{bid}')), s_float(request.form.get(f'cost_{bid}'))
                    total += qty * price
                    cat1, cat2, cat3 = request.form.get(f'cat_img1_{bid}'), request.form.get(f'cat_img2_{bid}'), request.form.get(f'cat_img3_{bid}')
                    i1 = copy_file(cat1, f"{prop_id}_p1_{bid}") if cat1 else save_file(request.files.get(f'img1_{bid}'), f"{prop_id}_p1_{bid}")
                    i2 = copy_file(cat2, f"{prop_id}_p2_{bid}") if cat2 else save_file(request.files.get(f'img2_{bid}'), f"{prop_id}_p2_{bid}")
                    i3 = copy_file(cat3, f"{prop_id}_p3_{bid}") if cat3 else save_file(request.files.get(f'img3_{bid}'), f"{prop_id}_p3_{bid}")
                    c.execute("INSERT INTO proposal_blocks (proposal_id, block_type, sort_order, title, unit, qty, price, cost, img1, img2, img3) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (prop_id, b_type, order, title, unit, qty, price, cost, i1, i2, i3))
                elif b_type == 'manual_product':
                    i1, i2, i3 = save_file(request.files.get(f'img1_{bid}'), f"{prop_id}_mp1_{bid}"), save_file(request.files.get(f'img2_{bid}'), f"{prop_id}_mp2_{bid}"), save_file(request.files.get(f'img3_{bid}'), f"{prop_id}_mp3_{bid}")
                    man_titles, man_units, man_qtys, man_prices = request.form.getlist(f'man_title_{bid}[]'), request.form.getlist(f'man_unit_{bid}[]'), request.form.getlist(f'man_qty_{bid}[]'), request.form.getlist(f'man_price_{bid}[]')
                    rows = []
                    for i in range(len(man_titles)):
                        q, p = s_float(man_qtys[i]), s_float(man_prices[i])
                        total += q * p
                        rows.append({'title': man_titles[i], 'unit': man_units[i], 'qty': q, 'price': p})
                    items_json = json.dumps(rows, ensure_ascii=False)
                    c.execute("INSERT INTO proposal_blocks (proposal_id, block_type, sort_order, img1, img2, img3, items_json) VALUES (?, ?, ?, ?, ?, ?, ?)", (prop_id, b_type, order, i1, i2, i3, items_json))
            c.execute("UPDATE proposals SET total=? WHERE id=?", (total, prop_id))
            conn.commit()
            return redirect(url_for('proposals_list'))
        clients = c.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
    return render_template('create_proposal.html', clients=clients, json=json)
@app.route('/edit_proposal/<prop_id>', methods=['GET', 'POST'])
def edit_proposal(prop_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if request.method == 'POST':
            p_name = request.form.get('project_name')
            cid = request.form.get('client_id')
            c.execute("UPDATE proposals SET project_name=?, client_id=? WHERE id=?", (p_name, cid, prop_id))
            c.execute("DELETE FROM proposal_blocks WHERE proposal_id=?", (prop_id,))
            
            block_ids = request.form.getlist('block_ids[]')
            
            # ДОБАВЛЕНО: Создаем счетчик новой суммы
            total = 0 
            
            for order, bid in enumerate(block_ids):
                b_type = request.form.get(f'b_type_{bid}')
                title = request.form.get(f'title_{bid}', '')
                text_content = request.form.get(f'text_{bid}', '')
                qty = request.form.get(f'qty_{bid}', 1)
                price = request.form.get(f'price_{bid}', 0)
                unit = request.form.get(f'unit_{bid}', 'шт.')
                cost = request.form.get(f'cost_{bid}', 0)
                
                # ДОБАВЛЕНО: Если это товар, плюсуем к итоговой сумме
                if b_type == 'product':
                    total += float(qty) * float(price)
                
# Сохраняем картинки (ИСПРАВЛЕНО ДЛЯ КАТАЛОГА)
                def save_img(idx):
                    # 1. Если загружен новый файл руками
                    f = request.files.get(f'img{idx}_{bid}')
                    if f and f.filename:
                        fn = f"pr_{prop_id}_{bid}_{idx}_{int(time.time()*1000)}.png"
                        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                        return fn
                    
                    # 2. Если блок добавлен из каталога (копируем фото каталога)
                    cat_img = request.form.get(f'cat_img{idx}_{bid}')
                    if cat_img:
                        return copy_file(cat_img, f"pr_{prop_id}_{bid}_cat{idx}")
                        
                    # 3. Если ничего не меняли, сохраняем старое фото
                    return request.form.get(f'old_img{idx}_{bid}', '')
                
                i1, i2, i3 = save_img(1), save_img(2), save_img(3)
                
                # Собираем JSON
                items_json = "{}"
                if b_type == 'cover':
                    items_json = json.dumps({'angle': request.form.get(f'cov_angle_{bid}', 10), 'gap': request.form.get(f'cov_gap_{bid}', 5), 'grad': request.form.get(f'cov_grad_{bid}', 70), 'color': request.form.get(f'cov_color_{bid}', '#ffffff'), 'shadow': request.form.get(f'cov_shadow_{bid}', 'on'), 'top_text': request.form.get(f'cov_top_{bid}', '')})
                elif b_type == 'text':
                    items_json = json.dumps({'bg': request.form.get(f'txt_bg_{bid}', '#f9fafb'), 'color': request.form.get(f'txt_color_{bid}', '#333333'), 'bc': request.form.get(f'txt_bc_{bid}', '#2563eb'), 'bw': request.form.get(f'txt_bw_{bid}', 4), 'b_style': request.form.get(f'txt_bstyle_{bid}', 'left'), 'b_rad': request.form.get(f'txt_brad_{bid}', 0)})
                elif b_type == 'manual_product':
                    man_titles = request.form.getlist(f'man_title_{bid}[]')
                    man_units = request.form.getlist(f'man_unit_{bid}[]')
                    man_qtys = request.form.getlist(f'man_qty_{bid}[]')
                    man_prices = request.form.getlist(f'man_price_{bid}[]')
                    rows = [{'title': man_titles[i], 'unit': man_units[i], 'qty': man_qtys[i], 'price': man_prices[i]} for i in range(len(man_titles))]
                    
                    # ДОБАВЛЕНО: Считаем сумму для таблицы-спецификации
                    for i in range(len(man_titles)):
                        total += float(man_qtys[i]) * float(man_prices[i])
                        
                    items_json = json.dumps(rows, ensure_ascii=False)
                
                c.execute("""INSERT INTO proposal_blocks 
                    (proposal_id, block_type, sort_order, title, text_content, qty, price, unit, img1, img2, img3, items_json, cost) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                    (prop_id, b_type, order, title, text_content, qty, price, unit, i1, i2, i3, items_json, cost))
            
            # ДОБАВЛЕНО: Сохраняем новую посчитанную сумму в базу
            c.execute("UPDATE proposals SET total=? WHERE id=?", (total, prop_id))
            
            conn.commit()
            return redirect(url_for('proposals_list'))

        prop = c.execute("SELECT id, client_id, date, project_name, total FROM proposals WHERE id=?", (prop_id,)).fetchone()
        blocks = c.execute("SELECT id, block_type, title, text_content, qty, price, unit, img1, img2, img3, items_json, cost FROM proposal_blocks WHERE proposal_id=? ORDER BY sort_order", (prop_id,)).fetchall()
        clients = c.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
    return render_template('edit_proposal.html', prop=prop, blocks=blocks, clients=clients, json=json)

@app.route('/proposal_to_invoice/<prop_id>')
def proposal_to_invoice(prop_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        prop = c.execute("SELECT client_id, total FROM proposals WHERE id=?", (prop_id,)).fetchone()
        products = c.execute("SELECT title, unit, qty, price, block_type, items_json, cost FROM proposal_blocks WHERE proposal_id=? AND block_type IN ('product', 'manual_product') ORDER BY sort_order", (prop_id,)).fetchall()
        year = datetime.now().strftime("%y")
        cid = prop[0] if prop[0] else "000"
        c.execute("SELECT id FROM invoices WHERE id LIKE ? ORDER BY id DESC", (f"{cid}{year}%",))
        last_inv = c.fetchone()
        num = int(last_inv[0][-4:]) + 1 if last_inv else 1
        inv_id = f"{cid}{year}{str(num).zfill(4)}"
        c.execute("INSERT INTO invoices (id, client_id, date, subtotal, vat_rate, vat_amount, total, status, knp, markup) VALUES (?, ?, ?, ?, ?, ?, ?, 0, '859', 0)", (inv_id, cid, datetime.now().strftime("%d.%m.%Y"), prop[1], 0, 0, prop[1]))
        for p in products:
            if p[4] == 'product':
                c.execute("INSERT INTO invoice_items (invoice_id, item, unit, qty, price, total) VALUES (?, ?, ?, ?, ?, ?)", (inv_id, p[0], p[1], p[2], p[3], p[2]*p[3]))
                if p[6] and float(p[6]) > 0:
                    c.execute("INSERT INTO internal_costs (invoice_id, label, value) VALUES (?, ?, ?)", (inv_id, f"{p[0]} (Себест.)", float(p[6])*float(p[2])))
            elif p[4] == 'manual_product':
                if p[5]:
                    rows = json.loads(p[5])
                    for r in rows:
                        c.execute("INSERT INTO invoice_items (invoice_id, item, unit, qty, price, total) VALUES (?, ?, ?, ?, ?, ?)", (inv_id, r['title'], r['unit'], r['qty'], r['price'], float(r['qty'])*float(r['price'])))
        c.execute("UPDATE proposals SET status = 1 WHERE id = ?", (prop_id,))
        conn.commit()
    return redirect(url_for('edit_invoice', invoice_id=inv_id))

@app.route('/api/delete_proposal/<prop_id>', methods=['POST'])
def delete_proposal(prop_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.cursor().execute("DELETE FROM proposals WHERE id=?", (prop_id,))
        conn.cursor().execute("DELETE FROM proposal_blocks WHERE proposal_id=?", (prop_id,))
        conn.commit()
    return jsonify(success=True)

@app.route('/duplicate_proposal/<prop_id>')
def duplicate_proposal(prop_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        prop = c.execute("SELECT client_id, project_name, total FROM proposals WHERE id=?", (prop_id,)).fetchone()
        if not prop: return redirect(url_for('proposals_list'))
        new_id = f"KP-{int(time.time())}"
        c.execute("INSERT INTO proposals (id, client_id, date, project_name, total, status) VALUES (?, '', ?, ?, ?, 0)", (new_id, datetime.now().strftime("%d.%m.%Y"), f"{prop[1]} (Копия)", prop[2]))
        blocks = c.execute("SELECT block_type, sort_order, title, text_content, qty, price, unit, img1, img2, img3, items_json, cost FROM proposal_blocks WHERE proposal_id=?", (prop_id,)).fetchall()
        for b in blocks:
            i1, i2, i3 = copy_file(b[7], f"{new_id}_1"), copy_file(b[8], f"{new_id}_2"), copy_file(b[9], f"{new_id}_3")
            c.execute("INSERT INTO proposal_blocks (proposal_id, block_type, sort_order, title, text_content, qty, price, unit, img1, img2, img3, items_json, cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (new_id, b[0], b[1], b[2], b[3], b[4], b[5], b[6], i1, i2, i3, b[10], b[11]))
        conn.commit()
    return redirect(url_for('edit_proposal', prop_id=new_id))


@app.route('/view_proposal/<prop_id>')
def view_proposal(prop_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        prop = c.execute("SELECT p.id, p.date, p.project_name, p.total, c.name, p.status FROM proposals p LEFT JOIN clients c ON p.client_id = c.id WHERE p.id=?", (prop_id,)).fetchone()
        blocks = c.execute("SELECT block_type, title, text_content, qty, price, unit, img1, img2, img3, items_json, cost FROM proposal_blocks WHERE proposal_id=? ORDER BY sort_order", (prop_id,)).fetchall()
        s = {r[0]: r[1] for r in c.execute("SELECT * FROM settings").fetchall()}
    return render_template('view_proposal.html', prop=prop, blocks=blocks, s=s, json=json)


@app.route('/invoices')
def invoices_list():
    with sqlite3.connect(DB_NAME) as conn: invoices = conn.cursor().execute("SELECT i.id, c.name, i.date, i.total, i.status FROM invoices i LEFT JOIN clients c ON i.client_id = c.id ORDER BY i.date DESC").fetchall()
    return render_template('invoices.html', invoices=invoices, title="Все счета")

@app.route('/create_invoice', methods=['GET', 'POST'])
def create_invoice():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if request.method == 'POST':
            cid, year, num, knp = request.form.get('client_id'), request.form.get('year'), request.form.get('doc_num'), request.form.get('knp')
            inv_id = f"{cid}{year}{str(num).zfill(4)}"
            items, units, qtys, prices = request.form.getlist('item[]'), request.form.getlist('unit[]'), request.form.getlist('qty[]'), request.form.getlist('price[]')
            cost_labels, cost_values = request.form.getlist('cost_label[]'), request.form.getlist('cost_value[]')
            if c.execute("SELECT id FROM invoices WHERE id=?", (inv_id,)).fetchone():
                clients = c.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
                knp_list = c.execute("SELECT * FROM knp_directory ORDER BY code").fetchall()
                form_items = [{'item': items[i], 'unit': units[i], 'qty': qtys[i], 'price': prices[i]} for i in range(len(items))]
                form_costs = [{'label': cost_labels[i], 'value': cost_values[i]} for i in range(len(cost_labels)) if cost_labels[i]]
                return render_template('invoice_form.html', clients=clients, knp_list=knp_list, error="Счет с таким номером уже существует!", current_client=cid, current_knp=knp, form_items=form_items, form_costs=form_costs, year=year, doc_num=num)
            subtotal = sum(s_float(qtys[i]) * s_float(prices[i]) for i in range(len(items)))
            vat_rate = s_float(request.form.get('vat', 0))
            total = subtotal * (1 + vat_rate/100)
            c.execute("INSERT INTO invoices (id, client_id, date, subtotal, vat_rate, vat_amount, total, status, knp, markup) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, 0)", (inv_id, cid, datetime.now().strftime("%d.%m.%Y"), subtotal, vat_rate, subtotal*(vat_rate/100), total, knp))
            for i in range(len(items)): c.execute("INSERT INTO invoice_items (invoice_id, item, unit, qty, price, total) VALUES (?, ?, ?, ?, ?, ?)", (inv_id, items[i], units[i], s_float(qtys[i]), s_float(prices[i]), s_float(qtys[i])*s_float(prices[i])))
            for i in range(len(cost_labels)):
                if cost_labels[i] and cost_values[i]: c.execute("INSERT INTO internal_costs (invoice_id, label, value) VALUES (?, ?, ?)", (inv_id, cost_labels[i], s_float(cost_values[i])))
            conn.commit()
            return redirect(url_for('invoices_list'))
        clients = c.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
        knp_list = c.execute("SELECT * FROM knp_directory ORDER BY code").fetchall()
    return render_template('invoice_form.html', clients=clients, knp_list=knp_list, current_client=request.args.get('client', ''))

@app.route('/edit_invoice/<invoice_id>', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        inv = c.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv or inv[7] != 0: return redirect(url_for('invoices_list'))
        if request.method == 'POST':
            items, units, qtys, prices = request.form.getlist('item[]'), request.form.getlist('unit[]'), request.form.getlist('qty[]'), request.form.getlist('price[]')
            subtotal = sum(s_float(qtys[i]) * s_float(prices[i]) for i in range(len(items)))
            vat_rate, knp = s_float(request.form.get('vat', 0)), request.form.get('knp', '859')
            total = subtotal * (1 + vat_rate/100)
            c.execute("UPDATE invoices SET subtotal=?, vat_rate=?, vat_amount=?, total=?, knp=?, markup=0 WHERE id=?", (subtotal, vat_rate, subtotal*(vat_rate/100), total, knp, invoice_id))
            c.execute("DELETE FROM invoice_items WHERE invoice_id=?", (invoice_id,))
            for i in range(len(items)): c.execute("INSERT INTO invoice_items (invoice_id, item, unit, qty, price, total) VALUES (?, ?, ?, ?, ?, ?)", (invoice_id, items[i], units[i], s_float(qtys[i]), s_float(prices[i]), s_float(qtys[i])*s_float(prices[i])))
            c.execute("DELETE FROM internal_costs WHERE invoice_id=?", (invoice_id,))
            cost_labels, cost_values = request.form.getlist('cost_label[]'), request.form.getlist('cost_value[]')
            for i in range(len(cost_labels)):
                if cost_labels[i] and cost_values[i]: c.execute("INSERT INTO internal_costs (invoice_id, label, value) VALUES (?, ?, ?)", (invoice_id, cost_labels[i], s_float(cost_values[i])))
            conn.commit()
            return redirect(url_for('invoices_list'))
        clients = c.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
        knp_list = c.execute("SELECT * FROM knp_directory ORDER BY code").fetchall()
        inv_items = c.execute("SELECT * FROM invoice_items WHERE invoice_id=?", (invoice_id,)).fetchall()
        costs = c.execute("SELECT label, value FROM internal_costs WHERE invoice_id=?", (invoice_id,)).fetchall()
    return render_template('edit_invoice.html', inv=inv, items=inv_items, costs=costs, clients=clients, knp_list=knp_list, current_knp=inv[8])

@app.route('/invoice_stats/<invoice_id>')
def invoice_stats(invoice_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        inv = c.execute("SELECT total, markup FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        costs = c.execute("SELECT label, value FROM internal_costs WHERE invoice_id=?", (invoice_id,)).fetchall()
    if not inv: return "Счет не найден", 404
    total_cost = sum(v for l, v in costs)
    profit = inv[0] - total_cost
    margin = (profit / inv[0] * 100) if inv[0] > 0 else 0
    return render_template('stats.html', inv_id=invoice_id, total=inv[0], costs=costs, total_cost=total_cost, profit=profit, margin=margin)

@app.route('/api/update_status/<id>/<int:s>', methods=['POST'])
def update_status(id, s):
    with sqlite3.connect(DB_NAME) as conn: conn.cursor().execute("UPDATE invoices SET status = ? WHERE id = ?", (s, id)); conn.commit()
    return jsonify(success=True)

@app.route('/api/delete_invoice/<id>', methods=['POST'])
def delete_invoice(id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM invoices WHERE id=?", (id,)); c.execute("DELETE FROM invoice_items WHERE invoice_id=?", (id,)); c.execute("DELETE FROM internal_costs WHERE invoice_id=?", (id,))
        conn.commit()
    return jsonify(success=True)

@app.route('/clients')
def clients():
    with sqlite3.connect(DB_NAME) as conn: clients = conn.cursor().execute("SELECT * FROM clients ORDER BY id").fetchall()
    return render_template('clients.html', clients=clients, json=json)

@app.route('/api/add_client', methods=['POST'])
def add_client():
    d = request.json
    with sqlite3.connect(DB_NAME) as conn: conn.cursor().execute("INSERT OR REPLACE INTO clients VALUES (?, ?, ?, ?, ?)", (d['client_id'].zfill(3), d['name'], d['bin'], d['contact'], d['address'])); conn.commit()
    return jsonify(success=True)

@app.route('/api/edit_client', methods=['POST'])
def edit_client():
    d = request.json
    with sqlite3.connect(DB_NAME) as conn: conn.cursor().execute("UPDATE clients SET name=?, bin=?, contact=?, address=? WHERE id=?", (d['name'], d['bin'], d['contact'], d['address'], d['client_id'])); conn.commit()
    return jsonify(success=True)

@app.route('/api/delete_client/<client_id>', methods=['POST'])
def delete_client(client_id):
    with sqlite3.connect(DB_NAME) as conn: conn.cursor().execute("DELETE FROM clients WHERE id = ?", (client_id,)); conn.commit()
    return jsonify(success=True)

@app.route('/knp')
def knp_list():
    with sqlite3.connect(DB_NAME) as conn: knps = conn.cursor().execute("SELECT * FROM knp_directory ORDER BY code").fetchall()
    return render_template('knp.html', knp_list=knps)

@app.route('/api/add_knp', methods=['POST'])
def add_knp():
    d = request.json
    with sqlite3.connect(DB_NAME) as conn: conn.cursor().execute("INSERT OR REPLACE INTO knp_directory VALUES (?, ?)", (d['code'], d['name'])); conn.commit()
    return jsonify(success=True)

@app.route('/api/edit_knp', methods=['POST'])
def edit_knp():
    d = request.json
    with sqlite3.connect(DB_NAME) as conn:
        conn.cursor().execute("UPDATE knp_directory SET code=?, name=? WHERE code=?", (d['new_code'], d['name'], d['old_code']))
        conn.cursor().execute("UPDATE invoices SET knp=? WHERE knp=?", (d['new_code'], d['old_code'])); conn.commit()
    return jsonify(success=True)

@app.route('/api/delete_knp/<code>', methods=['POST'])
def delete_knp(code):
    with sqlite3.connect(DB_NAME) as conn: conn.cursor().execute("DELETE FROM knp_directory WHERE code = ?", (code,)); conn.commit()
    return jsonify(success=True)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if request.method == 'POST':
            for k in ['company_name', 'company_bin', 'company_bank', 'company_iban', 'company_address', 'company_bik', 'company_kbe']: c.execute("UPDATE settings SET value=? WHERE key=?", (request.form.get(k), k))
            conn.commit()
            return redirect(url_for('settings'))
        sets = {r[0]: r[1] for r in c.execute("SELECT * FROM settings").fetchall()}
    return render_template('settings.html', s=sets)

@app.route('/print/<id>')
def print_invoice(id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        inv = c.execute("SELECT id, client_id, date, subtotal, vat_rate, vat_amount, total, status, knp FROM invoices WHERE id=?", (id,)).fetchone()
        items = c.execute("SELECT * FROM invoice_items WHERE invoice_id=?", (id,)).fetchall()
        client = c.execute("SELECT * FROM clients WHERE id=?", (inv[1],)).fetchone()
        s = {r[0]: r[1] for r in c.execute("SELECT * FROM settings").fetchall()}
    return render_template('print_invoice.html', inv=inv, items=items, client=client, s=s, sum_words=num2words_ru(inv[6]))

@app.route('/issued_invoices')
def issued_invoices():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        clients = c.execute("SELECT id, name FROM clients ORDER BY name").fetchall()
        clients_data = []
        for client in clients:
            cid = client[0]
            inv_count = c.execute("SELECT COUNT(*) FROM invoices WHERE client_id = ?", (cid,)).fetchone()[0]
            total_revenue = c.execute("SELECT SUM(total) FROM invoices WHERE client_id = ?", (cid,)).fetchone()[0] or 0
            invoices = c.execute("SELECT id FROM invoices WHERE client_id = ?", (cid,)).fetchall()
            total_costs = 0
            for inv in invoices:
                costs = c.execute("SELECT SUM(value) FROM internal_costs WHERE invoice_id = ?", (inv[0],)).fetchone()[0]
                if costs: total_costs += costs
            total_profit = total_revenue - total_costs
            clients_data.append({'id': cid, 'name': client[1], 'count': inv_count, 'revenue': total_revenue, 'profit': total_profit})
    return render_template('issued_clients.html', clients=clients_data)

@app.route('/client_invoices/<client_id>')
def client_invoices(client_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        name = c.execute("SELECT name FROM clients WHERE id=?", (client_id,)).fetchone()[0]
        invs = c.execute("SELECT i.id, c.name, i.date, i.total, i.status FROM invoices i LEFT JOIN clients c ON i.client_id = c.id WHERE i.client_id = ? ORDER BY i.date DESC", (client_id,)).fetchall()
    return render_template('invoices.html', invoices=invs, title=f"Счета: {name}", current_client=client_id)


@app.route('/api/get_local_icons')
def get_local_icons():
    # Используем абсолютный путь для надежности
    folder = os.path.join(app.static_folder, 'category_icons')
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # Получаем список файлов и фильтруем только картинки
    icons = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.svg', '.jpg', '.webp'))]
    return jsonify(icons)



# --- AI ROUTE ---
@app.route('/api/ai_describe', methods=['POST'])
def ai_describe():
    if 'image' not in request.files:
        return jsonify({'error': 'Фото не найдено'}), 400
        
    try:
        file = request.files['image']
        img = PIL.Image.open(io.BytesIO(file.read()))
        
# АРХИТЕКТУРНЫЙ И КОНЦЕПТУАЛЬНЫЙ ПРОМПТ
        prompt = (
            "Ты — концептуальный промышленный дизайнер и архитектурный критик. "
            "Твоя задача — описать это изделие (МАФ) глубоко, метафорично и со вкусом, "
            "раскрывая философию его дизайна.\n"
            "Посмотри на фото и выполни следующее:\n"
            "1. Назови объект (пергола, урна, скамейка, качели и т.д.), но подай это как арт-объект.\n"
            "2. Найди интересную ассоциацию для его формы. С чем это перекликается? "
            "(Например: отсылка к природной бионике, динамика мегаполиса, строгая геометрия оригами, "
            "парящий силуэт, переосмысление традиционных форм).\n"
            "3. Опиши гармонию материалов: как тяжесть и брутальность металла контрастируют с теплой, "
            "живой фактурой дерева.\n"
            "4. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать рекламные штампы ('премиальный статус', 'идеальный выбор', "
            "'покупайте', 'выгодное решение'). Текст должен звучать благородно и дорого, как аннотация "
            "к экспонату на выставке современного дизайна.\n"
            "Напиши 3-4 предложения. Выведи ТОЛЬКО текст."
        )
        
        # Получаем СПИСОК ВСЕХ МОДЕЛЕЙ, которые РЕАЛЬНО доступны твоему ключу прямо сейчас
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        print(f"\n[АВТОДИАГНОСТИКА] Доступные модели от Google: {available_models}\n")
        
        # Ищем самую подходящую
        model_name = None
        for m in available_models:
            if '1.5-flash' in m:
                model_name = m
                break
        
        if not model_name:
            for m in available_models:
                if 'vision' in m or '1.5' in m:
                    model_name = m
                    break
                    
        if not model_name and available_models:
            model_name = available_models[0] # Если ничего не подошло, берем первую разрешенную
            
        if not model_name:
            return jsonify({'error': 'Ключ не имеет доступа к моделям генерации'}), 500
            
        # Очищаем префикс 'models/', так как GenerativeModel принимает имя без него
        clean_model_name = model_name.replace('models/', '')
        print(f"[АВТОДИАГНОСТИКА] Выбрана рабочая модель: {clean_model_name}")
        
        model = genai.GenerativeModel(clean_model_name)
        response = model.generate_content([img, prompt])
        
        if not response.text:
            return jsonify({'text': 'ИИ не смог распознать объект на фото.'})
            
        return jsonify({'text': response.text})
        
    except Exception as e:
        print(f"Критическая ошибка ИИ: {e}")
        return jsonify({'error': str(e)}), 500
# ----------------

if __name__ == '__main__': 
    app.run(debug=True)