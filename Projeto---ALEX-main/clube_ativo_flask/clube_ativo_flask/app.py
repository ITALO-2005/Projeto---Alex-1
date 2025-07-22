import os
from functools import wraps
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- 1. CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'uma-chave-secreta-para-desenvolvimento')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///instance/database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- CONFIGURAÇÕES PARA ENVIO DE E-MAIL ---
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.googlemail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = ('Hub Comunitário', os.getenv('MAIL_USERNAME'))

# --- INICIALIZAÇÃO DE EXTENSÕES ---
mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- CONFIGURAÇÃO DE UPLOADS ---
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/profile_pics')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- 3. MODELOS DA BASE DE DADOS ---
# ... (Seus modelos continuam os mesmos) ...
inscricao_evento_tabela = db.Table('inscricao_evento',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('evento_id', db.Integer, db.ForeignKey('evento.id'), primary_key=True)
)
membros_clube_tabela = db.Table('membros_clube',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('clube_id', db.Integer, db.ForeignKey('clube.id'), primary_key=True)
)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(12), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    eventos_inscritos = db.relationship('Evento', secondary=inscricao_evento_tabela, back_populates='alunos_inscritos', lazy='dynamic')
    clubes_membro = db.relationship('Clube', secondary=membros_clube_tabela, back_populates='membros', lazy='dynamic')
    topicos_criados = db.relationship('ForumTopico', backref='autor', lazy='dynamic', cascade="all, delete-orphan")
    posts_criados = db.relationship('ForumPost', backref='autor', lazy='dynamic', cascade="all, delete-orphan")
    def get_reset_token(self, expires_sec=1800):
        return serializer.dumps({'user_id': self.id}, salt='password-reset-salt')
    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        try:
            data = serializer.loads(token, salt='password-reset-salt', max_age=expires_sec)
            return User.query.get(data['user_id'])
        except (SignatureExpired, Exception):
            return None
class Clube(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    membros = db.relationship('User', secondary=membros_clube_tabela, back_populates='clubes_membro', lazy='dynamic')
    eventos = db.relationship('Evento', backref='clube_organizador', lazy='dynamic')
class Evento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    vagas = db.Column(db.Integer, nullable=False)
    data_evento = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    clube_id = db.Column(db.Integer, db.ForeignKey('clube.id'), nullable=False)
    alunos_inscritos = db.relationship('User', secondary=inscricao_evento_tabela, back_populates='eventos_inscritos', lazy='dynamic')
    noticias = db.relationship('Noticia', backref='evento', lazy='dynamic', cascade="all, delete-orphan")
    @property
    def vagas_restantes(self):
        return self.vagas - self.alunos_inscritos.count()
class Noticia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    data_publicacao = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    evento_id = db.Column(db.Integer, db.ForeignKey('evento.id'), nullable=True)
class ForumTopico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    posts = db.relationship('ForumPost', backref='topico', lazy='dynamic', cascade="all, delete-orphan")
class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conteudo = db.Column(db.Text, nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topico_id = db.Column(db.Integer, db.ForeignKey('forum_topico.id'), nullable=False)

# --- 4. LÓGICA AUXILIAR ---
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = User.query.get(user_id) if user_id else None
    if user_id and g.user is None:
        session.clear()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('Você precisa fazer login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user_and_year():
    return dict(current_user_data=g.user, current_year=datetime.now(timezone.utc).year)

# --- 5. ROTAS ---
# ... (Suas rotas de index, gerenciamento de conta e autenticação continuam as mesmas) ...
@app.route('/')
def index():
    return redirect(url_for('login')) if g.user is None else redirect(url_for('noticias'))
def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Redefinição de Senha - Hub Comunitário', recipients=[user.email])
    msg.html = render_template('email/reset_password.html', user=user, token=token)
    mail.send(msg)
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if g.user: return redirect(url_for('noticias'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user:
            send_reset_email(user)
            flash('Um e-mail com instruções para redefinir sua senha foi enviado.', 'info')
            return redirect(url_for('login'))
        else:
            flash('Nenhuma conta encontrada com este e-mail.', 'warning')
    return render_template('forgot_password.html')
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if g.user: return redirect(url_for('noticias'))
    user = User.verify_reset_token(token)
    if not user:
        flash('O token é inválido ou expirou.', 'warning')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        user.password_hash = generate_password_hash(request.form.get('password'))
        db.session.commit()
        flash('Sua senha foi atualizada! Você já pode fazer login.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)
@app.route('/account/change_password', methods=['POST'])
@login_required
def change_password():
    if not check_password_hash(g.user.password_hash, request.form.get('old_password')):
        flash('A senha antiga está incorreta.', 'danger')
    elif request.form.get('new_password') != request.form.get('confirm_password'):
        flash('A nova senha e a confirmação não correspondem.', 'danger')
    else:
        g.user.password_hash = generate_password_hash(request.form.get('new_password'))
        db.session.commit()
        flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('account'))
@app.route('/account/delete', methods=['POST'])
@login_required
def delete_account():
    if not check_password_hash(g.user.password_hash, request.form.get('password')):
        flash('Senha incorreta. A exclusão da conta foi cancelada.', 'danger')
        return redirect(url_for('account'))
    user_to_delete = g.user
    session.clear()
    db.session.delete(user_to_delete)
    db.session.commit()
    flash('Sua conta foi excluída permanentemente.', 'info')
    return redirect(url_for('login'))
@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.user: return redirect(url_for('noticias'))
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(email=email).first():
            flash('Este e-mail já está em uso.', 'warning')
        elif User.query.filter_by(username=username).first():
            flash('Esta matrícula já está registrada.', 'warning')
        else:
            novo_user = User(email=email, username=username, password_hash=generate_password_hash(password))
            db.session.add(novo_user)
            db.session.commit()
            flash('Conta criada com sucesso! Pode fazer o login.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user: return redirect(url_for('noticias'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('noticias'))
        else:
            flash('Matrícula ou senha inválidos.', 'danger')
    return render_template('login.html')
@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('login'))

# ROTA DA CONTA ATUALIZADA
@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    # Esta parte lida com o upload do arquivo de imagem
    if request.method == 'POST':
        # Verifica se a requisição POST tem a parte do arquivo
        if 'picture' not in request.files:
            flash('Nenhuma parte do arquivo encontrada no formulário.', 'danger')
            return redirect(request.url)
        file = request.files['picture']
        # Se o usuário não selecionar um arquivo, o navegador
        # envia um arquivo vazio sem nome de arquivo.
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'warning')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            # Gera um nome de arquivo seguro
            ext = os.path.splitext(file.filename)[1]
            filename = secure_filename(f"{g.user.username}{ext}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            # Atualiza o nome do arquivo no banco de dados
            g.user.image_file = filename
            db.session.commit()
            flash('Foto de perfil atualizada com sucesso!', 'success')
            return redirect(url_for('account'))
        else:
            flash('Tipo de arquivo inválido. Use png, jpg, jpeg ou gif.', 'danger')
            return redirect(url_for('account'))

    # Esta parte lida com a requisição GET (carregamento normal da página)
    image_file = url_for('static', filename='profile_pics/' + g.user.image_file)
    return render_template('account.html', image_file=image_file, eventos=g.user.eventos_inscritos)

# ROTAS PRINCIPAIS DA APLICAÇÃO
@app.route('/noticias')
@login_required
def noticias():
    todas_noticias = Noticia.query.order_by(Noticia.data_publicacao.desc()).all()
    return render_template('noticias.html', noticias=todas_noticias)
@app.route('/clubes')
@login_required
def clubes():
    todos_clubes = Clube.query.order_by(Clube.nome).all()
    return render_template('clubes.html', clubes=todos_clubes)
@app.route('/clube/<int:clube_id>')
@login_required
def detalhe_clube(clube_id):
    clube = Clube.query.get_or_404(clube_id)
    agora = datetime.now(timezone.utc)
    eventos_futuros = clube.eventos.filter(Evento.data_evento >= agora).order_by(Evento.data_evento.asc()).all()
    eventos_passados = clube.eventos.filter(Evento.data_evento < agora).order_by(Evento.data_evento.desc()).all()
    return render_template('detalhe_clube.html', clube=clube, eventos_futuros=eventos_futuros, eventos_passados=eventos_passados)
@app.route('/ranking')
@login_required
def ranking():
    clubes_rankeados = sorted(Clube.query.all(), key=lambda c: c.membros.count(), reverse=True)
    return render_template('ranking.html', clubes=clubes_rankeados)
@app.route('/forum')
@login_required
def forum():
    topicos = ForumTopico.query.order_by(ForumTopico.data_criacao.desc()).all()
    return render_template('forum.html', topicos=topicos)
@app.route('/forum/topico/<int:topico_id>', methods=['GET', 'POST'])
@login_required
def detalhe_topico(topico_id):
    topico = ForumTopico.query.get_or_404(topico_id)
    if request.method == 'POST':
        conteudo_post = request.form.get('conteudo')
        if conteudo_post:
            novo_post = ForumPost(conteudo=conteudo_post, user_id=g.user.id, topico_id=topico.id)
            db.session.add(novo_post)
            db.session.commit()
            flash('Resposta adicionada com sucesso!', 'success')
            return redirect(url_for('detalhe_topico', topico_id=topico.id))
    posts = topico.posts.order_by(ForumPost.data_criacao.asc()).all()
    return render_template('detalhe_topico.html', topico=topico, posts=posts)
@app.route('/forum/novo_topico', methods=['GET', 'POST'])
@login_required
def criar_topico():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        conteudo = request.form.get('conteudo')
        if titulo and conteudo:
            novo_topico = ForumTopico(titulo=titulo, conteudo=conteudo, user_id=g.user.id)
            db.session.add(novo_topico)
            db.session.commit()
            flash('Tópico criado com sucesso!', 'success')
            return redirect(url_for('detalhe_topico', topico_id=novo_topico.id))
    return render_template('criar_topico.html')
@app.route('/hub_servicos')
@login_required
def hub_servicos():
    eventos_futuros = Evento.query.filter(Evento.vagas > 0).order_by(Evento.data_evento.asc()).limit(3).all()
    return render_template('hub_servicos.html', eventos_futuros=eventos_futuros)
@app.route('/eventos')
@login_required
def eventos():
    todos_eventos = Evento.query.order_by(Evento.data_evento.asc()).all()
    return render_template('eventos.html', eventos=todos_eventos)
@app.route('/evento/<int:evento_id>')
@login_required
def detalhe_evento(evento_id):
    evento = Evento.query.get_or_404(evento_id)
    ja_inscrito = evento in g.user.eventos_inscritos.all()
    return render_template('detalhe_evento.html', evento=evento, ja_inscrito=ja_inscrito)
@app.route('/evento/<int:evento_id>/inscrever', methods=['POST'])
@login_required
def inscrever_evento(evento_id):
    evento = Evento.query.get_or_404(evento_id)
    if evento in g.user.eventos_inscritos.all():
        flash('Você já está inscrito neste evento.', 'info')
    elif evento.vagas_restantes <= 0:
        flash('Vagas esgotadas para este evento!', 'danger')
    else:
        g.user.eventos_inscritos.append(evento)
        db.session.commit()
        flash('Inscrição realizada com sucesso!', 'success')
    return redirect(url_for('detalhe_evento', evento_id=evento.id))

# ... (Seu comando seed-db continua o mesmo) ...
@app.cli.command('seed-db')
def seed_db_command():
    if Clube.query.count() > 0:
        print("O banco de dados já contém dados. Abortando o seeding.")
        return
    print("Criando clubes de exemplo...")
    clube_prog = Clube(nome='Clube de Programação', descricao='Para entusiastas de código, desenvolvimento de software e competições.', categoria='Tecnologia')
    clube_robotica = Clube(nome='Clube de Robótica', descricao='Construção e programação de robôs para desafios e aprendizado.', categoria='Tecnologia')
    clube_teatro = Clube(nome='Clube de Teatro', descricao='Explore a arte da atuação, expressão corporal e montagem de peças.', categoria='Arte & Cultura')
    clube_literatura = Clube(nome='Clube de Literatura', descricao='Leituras, debates e análises de obras clássicas e contemporâneas.', categoria='Arte & Cultura')
    clube_esportes = Clube(nome='Clube de Esportes', descricao='Organização de treinos e campeonatos de diversas modalidades.', categoria='Esportes')
    db.session.add_all([clube_prog, clube_robotica, clube_teatro, clube_literatura, clube_esportes])
    db.session.commit()
    print("Clubes criados.")
    print("Criando eventos de exemplo...")
    e1 = Evento(titulo='Maratona de Programação', descricao='Resolva desafios de programação em equipe.', vagas=50, clube_id=clube_prog.id, data_evento=datetime(2025, 8, 10, 9, 0, 0, tzinfo=timezone.utc))
    e2 = Evento(titulo='Oficina de Arduino', descricao='Aprenda os primeiros passos com a plataforma Arduino.', vagas=25, clube_id=clube_robotica.id, data_evento=datetime(2025, 8, 22, 14, 0, 0, tzinfo=timezone.utc))
    e3 = Evento(titulo='Debate sobre "1984"', descricao='Análise da obra de George Orwell e suas implicações atuais.', vagas=30, clube_id=clube_literatura.id, data_evento=datetime(2025, 8, 15, 18, 30, 0, tzinfo=timezone.utc))
    db.session.add_all([e1, e2, e3])
    db.session.commit()
    print("Eventos criados.")
    print("Criando notícias de exemplo...")
    n1 = Noticia(titulo='Inscrições Abertas para a Maratona de Programação!', conteudo='As inscrições para a maratona de programação já começaram. Monte sua equipe e participe!', evento_id=e1.id)
    n2 = Noticia(titulo='Edital de Monitoria 2025.2', conteudo='Estão abertas as inscrições para o programa de monitoria. Os interessados devem procurar a coordenação do seu curso para mais informações sobre vagas e disciplinas disponíveis.')
    db.session.add_all([n1, n2])
    db.session.commit()
    print("Notícias criadas.")
    print("Banco de dados populado com sucesso!")

if __name__ == '__main__':
    app.run(debug=True)
