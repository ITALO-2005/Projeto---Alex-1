import os
import uuid
import sqlite3
import locale
from functools import wraps
from datetime import datetime, timezone, date, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, current_app
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')
    except locale.Error:
        print("Aviso: Locale 'pt_BR' não encontrado. Os nomes dos meses podem aparecer em inglês.")

load_dotenv()

# --- 1. CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)
app.config.from_mapping(
    DATABASE=os.path.join(app.instance_path, 'database.db'),
    SECRET_KEY='77cd9b0684a5113200d4810755f4a9e5455a3c860df49cf7',
    UPLOAD_FOLDER=os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/profile_pics'),
    CLUB_MEDIA_FOLDER=os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/club_media'),
    MAIL_SERVER=os.getenv('MAIL_SERVER', 'smtp.googlemail.com'),
    MAIL_PORT=int(os.getenv('MAIL_PORT', 587)),
    MAIL_USE_TLS=os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't'],
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=('Hub Comunitário', os.getenv('MAIL_USERNAME'))
)

try:
    os.makedirs(app.instance_path)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['CLUB_MEDIA_FOLDER'], exist_ok=True)
except OSError:
    pass

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_MEDIA_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mov', 'webp'}

def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set

# --- 2. GESTÃO DA BASE DE DADOS ---
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'], detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

app.teardown_appcontext(close_db)

def init_db():
    db = get_db()
    with app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

@app.cli.command('init-db')
def init_db_command():
    init_db()
    print('Base de dados inicializada.')

# --- 3. LÓGICA AUXILIAR, FILTROS E DECORATORS ---
@app.context_processor
def inject_global_vars():
    return dict(g=g, current_year=datetime.now(timezone.utc).year, timedelta=timedelta)

@app.template_filter('format_datetime')
def format_datetime_filter(s):
    if not s: return ""
    try: return datetime.fromisoformat(s).strftime('%d/%m/%Y às %H:%M')
    except: return s

@app.template_filter('format_date')
def format_date_filter(s):
    if not s: return ""
    try: return datetime.fromisoformat(s).strftime('%d/%m/%Y')
    except: return s
        
@app.template_filter('format_date_full')
def format_date_full_filter(s):
    if not s: return ""
    try: return datetime.fromisoformat(s).strftime('%d de %b de %Y')
    except: return s

@app.template_filter('format_date_short')
def format_date_short_filter(s):
    if not s: return ""
    try: return datetime.fromisoformat(s).strftime('%d/%m')
    except: return s

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = get_db().execute('SELECT * FROM user WHERE id = ?', (user_id,)).fetchone() if user_id else None
    if user_id and g.user is None: session.clear()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('Você precisa fazer login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def award_badge(user_id, badge_name, show_flash=True):
    db = get_db()
    has_badge = db.execute("SELECT 1 FROM user_badges ub JOIN badge b ON ub.badge_id = b.id WHERE ub.user_id = ? AND b.nome = ?", (user_id, badge_name)).fetchone()
    if not has_badge:
        badge = db.execute("SELECT * FROM badge WHERE nome = ?", (badge_name,)).fetchone()
        if badge:
            db.execute("INSERT INTO user_badges (user_id, badge_id) VALUES (?, ?)", (user_id, badge['id']))
            db.commit()
            if show_flash and 'request' in g:
                flash(f"Selo Desbloqueado: \"{badge['nome']}\"!", 'special')

# --- 4. ROTAS ---
@app.route('/')
def index():
    if g.user is None:
        return redirect(url_for('login'))
    return redirect(url_for('noticias'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.user: return redirect(url_for('noticias'))
    if request.method == 'POST':
        email, username, password = request.form['email'], request.form['username'], request.form['password']
        db = get_db()
        if not username or not password or not email:
            flash('Todos os campos são obrigatórios.', 'danger')
        else:
            try:
                cursor = db.execute("INSERT INTO user (username, email, password_hash) VALUES (?, ?, ?)", (username, email, generate_password_hash(password)))
                db.commit()
                new_user_id = cursor.lastrowid
                user_count = db.execute("SELECT COUNT(id) as count FROM user").fetchone()['count']
                if user_count <= 10:
                    award_badge(new_user_id, 'Membro Pioneiro')
                flash('Conta criada com sucesso! Pode fazer o login.', 'success')
                return redirect(url_for("login"))
            except db.IntegrityError:
                flash(f"Utilizador {username} ou email {email} já registado.", 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user: return redirect(url_for('noticias'))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        user = get_db().execute('SELECT * FROM user WHERE username = ?', (username,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('noticias'))
        flash('Matrícula ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if g.user: return redirect(url_for('noticias'))
    if request.method == 'POST':
        user = get_db().execute('SELECT * FROM user WHERE email = ?', (request.form['email'],)).fetchone()
        if user:
            flash('Um e-mail com instruções para redefinir sua senha foi enviado (funcionalidade em desenvolvimento).', 'info')
            return redirect(url_for('login'))
        else:
            flash('Nenhuma conta encontrada com este e-mail.', 'warning')
    return render_template('forgot_password.html')

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    db = get_db()
    if request.method == 'POST' and 'picture' in request.files:
        file = request.files['picture']
        if file.filename != '' and allowed_file(file.filename, ALLOWED_EXTENSIONS):
            ext = os.path.splitext(file.filename)[1]
            filename = secure_filename(f"{g.user['username']}{ext}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            db.execute('UPDATE user SET image_file = ? WHERE id = ?', (filename, g.user['id']))
            db.commit()
            flash('Foto de perfil atualizada com sucesso!', 'success')
            return redirect(url_for('account'))
        else:
            flash('Tipo de arquivo inválido.', 'danger')

    image_file = url_for('static', filename='profile_pics/' + g.user['image_file'])
    eventos_inscritos = db.execute("SELECT e.* FROM evento e JOIN inscricao_evento ie ON e.id = ie.evento_id WHERE ie.user_id = ? ORDER BY e.data_evento DESC", (g.user['id'],)).fetchall()
    badges = db.execute("SELECT b.* FROM badge b JOIN user_badges ub ON b.id = ub.badge_id WHERE ub.user_id = ?", (g.user['id'],)).fetchall()
    
    return render_template('account.html', image_file=image_file, eventos=eventos_inscritos, badges=badges)

@app.route('/account/change_password', methods=['POST'])
@login_required
def change_password():
    db = get_db()
    old_password, new_password, confirm_password = request.form['old_password'], request.form['new_password'], request.form['confirm_password']

    if not check_password_hash(g.user['password_hash'], old_password):
        flash('A senha antiga está incorreta.', 'danger')
    elif new_password != confirm_password:
        flash('A nova senha e a confirmação não correspondem.', 'danger')
    else:
        db.execute('UPDATE user SET password_hash = ? WHERE id = ?', (generate_password_hash(new_password), g.user['id']))
        db.commit()
        flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('account'))

@app.route('/account/delete', methods=['POST'])
@login_required
def delete_account():
    db = get_db()
    password = request.form['password']
    if not check_password_hash(g.user['password_hash'], password):
        flash('Senha incorreta. A exclusão da conta foi cancelada.', 'danger')
        return redirect(url_for('account'))

    user_id_to_delete = g.user['id']
    try:
        db.execute('DELETE FROM membros_clube WHERE user_id = ?', (user_id_to_delete,))
        db.execute('DELETE FROM inscricao_evento WHERE user_id = ?', (user_id_to_delete,))
        db.execute('DELETE FROM user_badges WHERE user_id = ?', (user_id_to_delete,))
        db.execute('DELETE FROM forum_post WHERE user_id = ?', (user_id_to_delete,))
        db.execute('DELETE FROM forum_topico WHERE user_id = ?', (user_id_to_delete,))
        db.execute('UPDATE clube SET lider_id = NULL WHERE lider_id = ?', (user_id_to_delete,))
        db.execute('DELETE FROM user WHERE id = ?', (user_id_to_delete,))
        db.commit()
    except db.Error as e:
        db.rollback()
        flash(f'Ocorreu um erro ao excluir a conta: {e}', 'danger')
        return redirect(url_for('account'))

    session.clear()
    flash('Sua conta foi excluída permanentemente.', 'info')
    return redirect(url_for('login'))

@app.route('/noticias')
@login_required
def noticias():
    query = "SELECT n.*, e.titulo as evento_titulo FROM noticia n LEFT JOIN evento e ON n.evento_id = e.id ORDER BY n.data_publicacao DESC"
    todas_noticias = get_db().execute(query).fetchall()
    return render_template('noticias.html', noticias=todas_noticias)

@app.route('/clubes')
@login_required
def clubes():
    query = "SELECT c.*, (SELECT COUNT(user_id) FROM membros_clube mc WHERE mc.clube_id = c.id) as member_count FROM clube c ORDER BY c.nome"
    todos_clubes = get_db().execute(query).fetchall()
    return render_template('clubes.html', clubes=todos_clubes)

@app.route('/clube/<int:clube_id>')
@login_required
def detalhe_clube(clube_id):
    db = get_db()
    clube_query = "SELECT c.*, u.username as lider_username, (SELECT COUNT(user_id) FROM membros_clube mc WHERE mc.clube_id = c.id) as member_count FROM clube c LEFT JOIN user u ON c.lider_id = u.id WHERE c.id = ?"
    clube = db.execute(clube_query, (clube_id,)).fetchone()
    if not clube: return "Clube não encontrado", 404

    agora = datetime.now(timezone.utc).isoformat()
    eventos_futuros = db.execute('SELECT * FROM evento WHERE clube_id = ? AND data_evento >= ? ORDER BY data_evento ASC', (clube_id, agora)).fetchall()
    eventos_passados = db.execute('SELECT * FROM evento WHERE clube_id = ? AND data_evento < ? ORDER BY data_evento DESC', (clube_id, agora)).fetchall()
    is_member = db.execute('SELECT 1 FROM membros_clube WHERE user_id = ? AND clube_id = ?', (g.user['id'], clube_id)).fetchone() is not None
    is_leader = clube['lider_id'] == g.user['id']
    
    return render_template('detalhe_clube.html', clube=clube, eventos_futuros=eventos_futuros, eventos_passados=eventos_passados, is_member=is_member, is_leader=is_leader)

@app.route('/ranking')
@login_required
def ranking():
    query = "SELECT c.*, (SELECT COUNT(user_id) FROM membros_clube mc WHERE mc.clube_id = c.id) as member_count FROM clube c ORDER BY member_count DESC, c.nome"
    clubes_rankeados = get_db().execute(query).fetchall()
    return render_template('ranking.html', clubes=clubes_rankeados)

@app.route('/eventos')
@login_required
def eventos():
    agora = datetime.now(timezone.utc).isoformat()
    todos_eventos = get_db().execute("SELECT * FROM evento WHERE data_evento >= ? ORDER BY data_evento ASC", (agora,)).fetchall()
    return render_template('eventos.html', eventos=todos_eventos)

@app.route('/evento/<int:evento_id>')
@login_required
def detalhe_evento(evento_id):
    db = get_db()
    evento = db.execute('SELECT * FROM evento WHERE id = ?', (evento_id,)).fetchone()
    if not evento: return "Evento não encontrado", 404
    
    ja_inscrito = db.execute('SELECT 1 FROM inscricao_evento WHERE user_id = ? AND evento_id = ?', (g.user['id'], evento_id)).fetchone() is not None
    inscritos_count = db.execute('SELECT COUNT(user_id) as count FROM inscricao_evento WHERE evento_id = ?', (evento_id,)).fetchone()['count']
    vagas_restantes = evento['vagas'] - inscritos_count

    return render_template('detalhe_evento.html', evento=evento, ja_inscrito=ja_inscrito, vagas_restantes=vagas_restantes)

@app.route('/evento/<int:evento_id>/inscrever', methods=['POST'])
@login_required
def inscrever_evento(evento_id):
    db = get_db()
    evento = db.execute('SELECT * FROM evento WHERE id = ?', (evento_id,)).fetchone()
    if not evento: return "Evento não encontrado", 404

    ja_inscrito = db.execute('SELECT 1 FROM inscricao_evento WHERE user_id = ? AND evento_id = ?', (g.user['id'], evento_id)).fetchone()
    if ja_inscrito:
        flash('Você já está inscrito neste evento.', 'info')
    else:
        inscritos_count = db.execute('SELECT COUNT(user_id) as count FROM inscricao_evento WHERE evento_id = ?', (evento_id,)).fetchone()['count']
        if evento['vagas'] - inscritos_count <= 0:
            flash('Vagas esgotadas para este evento!', 'danger')
        else:
            db.execute('INSERT INTO inscricao_evento (user_id, evento_id) VALUES (?, ?)', (g.user['id'], evento_id))
            db.commit()
            flash('Inscrição realizada com sucesso!', 'success')
    return redirect(url_for('detalhe_evento', evento_id=evento_id))

@app.route('/hub_servicos')
@login_required
def hub_servicos():
    agora = datetime.now(timezone.utc).isoformat()
    eventos_futuros = get_db().execute("SELECT * FROM evento WHERE data_evento >= ? ORDER BY data_evento ASC LIMIT 3", (agora,)).fetchall()
    return render_template('hub_servicos.html', eventos_futuros=eventos_futuros)

@app.route('/cardapio')
@login_required
def cardapio():
    hoje = date.today()
    start_of_week = hoje - timedelta(days=hoje.weekday())
    cardapio_semana_obj = get_db().execute("SELECT * FROM cardapio_ru WHERE data >= ? ORDER BY data ASC LIMIT 7", (start_of_week.isoformat(),)).fetchall()
    cardapio_semana = {datetime.fromisoformat(item['data']).weekday(): item for item in cardapio_semana_obj}
    return render_template('cardapio_ru.html', cardapio_semana=cardapio_semana, start_of_week=start_of_week)

@app.route('/calendario_academico')
@login_required
def calendario_academico():
    hoje = date.today().isoformat()
    eventos = get_db().execute("SELECT * FROM calendario_academico WHERE data >= ? ORDER BY data ASC", (hoje,)).fetchall()
    return render_template('calendario_academico.html', eventos=eventos)

# --- 5. COMANDO SEED-DB COMPLETO ---
@app.cli.command('seed-db')
def seed_db_command():
    init_db()
    db = get_db()
    
    badges = [('Membro Pioneiro', 'Um dos 10 primeiros.', 'fas fa-rocket'), ('Explorador de Clubes', 'Entrou no primeiro clube.', 'fas fa-compass')]
    db.executemany("INSERT INTO badge (nome, descricao, icon_class) VALUES (?, ?, ?)", badges)

    users = [
        ('lider.prog@ifpb.edu.br', '202511110001', generate_password_hash('123456')),
        ('membro.comum@ifpb.edu.br', '202511110002', generate_password_hash('123456')),
        ('lider.teatro@ifpb.edu.br', '202522220001', generate_password_hash('123456')),
    ]
    db.executemany("INSERT INTO user (email, username, password_hash) VALUES (?, ?, ?)", users)

    clubes = [
        ('Clube de Programação', 'Para entusiastas de código...', 'Tecnologia', 1),
        ('Clube de Teatro', 'Explore a arte da atuação...', 'Arte & Cultura', 3),
        ('Clube de Esportes', 'Organização de treinos...', 'Esportes', None),
        ('Clube de Robótica', 'Construção de robôs...', 'Tecnologia', None),
        ('Clube de Literatura', 'Leituras e debates...', 'Arte & Cultura', None),
    ]
    db.executemany("INSERT INTO clube (nome, descricao, categoria, lider_id) VALUES (?, ?, ?, ?)", clubes)
    
    membros = [(1, 1), (2, 1), (2, 2), (3, 2), (1, 4), (2, 5)]
    db.executemany("INSERT INTO membros_clube (user_id, clube_id) VALUES (?, ?)", membros)

    user_badges = [(1, 1), (2, 1), (2, 2), (3, 1)]
    db.executemany("INSERT INTO user_badges (user_id, badge_id) VALUES (?, ?)", user_badges)

    agora = datetime.now(timezone.utc)
    eventos = [
        ('Maratona de Programação', 'Resolva desafios...', 50, (agora + timedelta(days=30)).isoformat(), 1),
        ('Oficina de Arduino', 'Aprenda os primeiros passos...', 25, (agora + timedelta(days=45)).isoformat(), 4),
        ('Debate sobre "1984"', 'Análise da obra...', 30, (agora + timedelta(days=60)).isoformat(), 5),
        ('Apresentação Teatral', 'Performance de verão', 100, (agora - timedelta(days=30)).isoformat(), 2),
    ]
    db.executemany("INSERT INTO evento (titulo, descricao, vagas, data_evento, clube_id) VALUES (?, ?, ?, ?, ?)", eventos)

    noticias = [
        ('Inscrições Abertas para a Maratona!', 'As inscrições para a maratona de programação já começaram.', agora.isoformat(), 1),
        ('Edital de Monitoria 2025.2', 'Estão abertas as inscrições para o programa de monitoria.', (agora - timedelta(days=1)).isoformat(), None),
        ('Vem aí a Oficina de Arduino!', 'O Clube de Robótica convida a todos para uma oficina prática.', (agora - timedelta(days=2)).isoformat(), 2),
        ('Novo Horário da Biblioteca', 'Atenção, a biblioteca funcionará em horário estendido.', (agora - timedelta(days=5)).isoformat(), None),
    ]
    db.executemany("INSERT INTO noticia (titulo, conteudo, data_publicacao, evento_id) VALUES (?, ?, ?, ?)", noticias)

    hoje = date.today()
    start_of_week = hoje - timedelta(days=hoje.weekday())
    cardapio_data = []
    for i in range(5):
        menu_date = start_of_week + timedelta(days=i)
        cardapio_data.append(
            (menu_date.isoformat(), 'Frango Grelhado com Arroz e Feijão', 'Torta de Legumes', 'Batata Doce Assada', 'Mix de Folhas com Tomate', 'Fruta da Estação')
        )
    db.executemany("INSERT INTO cardapio_ru (data, prato_principal, vegetariano, acompanhamento, salada, sobremesa) VALUES (?, ?, ?, ?, ?, ?)", cardapio_data)

    calendario_data = [
        (date(2025, 8, 15).isoformat(), "Início do Semestre Letivo 2025.2", "Acadêmico"),
        (date(2025, 9, 7).isoformat(), "Feriado Nacional - Independência do Brasil", "Feriado"),
        (date(2025, 10, 12).isoformat(), "Feriado Nacional - Nossa Senhora Aparecida", "Feriado"),
        (date(2025, 10, 15).isoformat(), "Feriado - Dia do Professor", "Feriado"),
        (date(2025, 11, 2).isoformat(), "Feriado - Finados", "Feriado"),
        (date(2025, 11, 15).isoformat(), "Feriado - Proclamação da República", "Feriado"),
        (date(2025, 12, 20).isoformat(), "Fim do Semestre Letivo 2025.2", "Acadêmico")
    ]
    db.executemany("INSERT INTO calendario_academico (data, descricao, tipo) VALUES (?, ?, ?)", calendario_data)

    db.commit()
    print("Base de dados populada com sucesso!")

if __name__ == '__main__':
    app.run(debug=True)
