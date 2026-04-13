from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# ==================== CONFIGURAÇÃO INICIAL ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua-chave-secreta-aqui-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== MODELOS DO BANCO DE DADOS ====================
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    unidade = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class OrdemServico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_os = db.Column(db.String(20), unique=True, nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    sistema = db.Column(db.String(50), nullable=False)
    atividade = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='À Fazer')
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    unidade = db.Column(db.String(100), nullable=False)
    criado_por = db.Column(db.String(100), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# ==================== FUNÇÃO MÁGICA DO CÓDIGO ====================
def gerar_numero_os(atividade, sistema):
    """
    Gera o código no formato: MPSDAI001, MCBMS001, ACTEL001, etc.
    """
    # Mapeia o prefixo
    prefixos = {
        'Manutenção Preventiva': 'MP',
        'Manutenção Corretiva': 'MC',
        'Acompanhamento': 'AC',
        'Outros': 'OT'
    }
    
    prefixo = prefixos.get(atividade, 'XX')
    base = f"{prefixo}{sistema}"
    
    # Busca o último número usado para esta base
    ultima_os = OrdemServico.query.filter(
        OrdemServico.numero_os.like(f"{base}%")
    ).order_by(OrdemServico.numero_os.desc()).first()
    
    if ultima_os:
        # Extrai o número (ex: MPSDAI005 -> 5)
        numero = int(ultima_os.numero_os[len(base):]) + 1
    else:
        numero = 1
    
    return f"{base}{str(numero).zfill(3)}"

# ==================== ROTAS DA APLICAÇÃO ====================
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and check_password_hash(usuario.senha_hash, senha):
            login_user(usuario)
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou senha incorretos', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Filtra por unidade (exceto admin)
    if current_user.is_admin:
        ordens = OrdemServico.query.order_by(OrdemServico.data_criacao.desc()).all()
    else:
        ordens = OrdemServico.query.filter_by(unidade=current_user.unidade)\
                                  .order_by(OrdemServico.data_criacao.desc()).all()
    
    return render_template('dashboard.html', ordens=ordens)

@app.route('/nova-os', methods=['GET', 'POST'])
@login_required
def nova_os():
    if request.method == 'POST':
        # Pega dados do formulário
        atividade = request.form.get('atividade')
        sistema = request.form.get('sistema')
        
        # Gera o número mágico
        numero_os = gerar_numero_os(atividade, sistema)
        
        # Cria a OS
        nova = OrdemServico(
            numero_os=numero_os,
            titulo=request.form.get('titulo'),
            descricao=request.form.get('descricao'),
            sistema=sistema,
            atividade=atividade,
            status=request.form.get('status'),
            data_inicio=datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d'),
            data_fim=datetime.strptime(request.form.get('data_fim'), '%Y-%m-%d'),
            unidade=current_user.unidade,
            criado_por=current_user.email
        )
        
        db.session.add(nova)
        db.session.commit()
        
        flash(f'OS {numero_os} criada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('nova_os.html')

@app.route('/editar-os/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_os(id):
    os = OrdemServico.query.get_or_404(id)
    
    # Verifica se o usuário tem permissão (mesma unidade ou admin)
    if not current_user.is_admin and os.unidade != current_user.unidade:
        flash('Você não tem permissão para editar esta OS', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        os.titulo = request.form.get('titulo')
        os.descricao = request.form.get('descricao')
        os.status = request.form.get('status')
        os.data_inicio = datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d')
        os.data_fim = datetime.strptime(request.form.get('data_fim'), '%Y-%m-%d')
        
        db.session.commit()
        flash('OS atualizada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('editar_os.html', os=os)

@app.route('/excluir-os/<int:id>')
@login_required
def excluir_os(id):
    os = OrdemServico.query.get_or_404(id)
    
    # Verifica permissão
    if not current_user.is_admin and os.unidade != current_user.unidade:
        flash('Você não tem permissão para excluir esta OS', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(os)
    db.session.commit()
    flash('OS excluída com sucesso!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/metricas')
@login_required
def metricas():
    return render_template('metricas.html')

@app.route('/api/dados-metricas')
@login_required
def api_dados_metricas():
    """Retorna JSON para os gráficos do dashboard"""
    from sqlalchemy import func, extract
    
    # Filtra por unidade
    query = OrdemServico.query
    if not current_user.is_admin:
        query = query.filter_by(unidade=current_user.unidade)
    
    # Dados para gráfico de Status
    status_counts = query.with_entities(
        OrdemServico.status, 
        func.count(OrdemServico.id)
    ).group_by(OrdemServico.status).all()
    
    # Dados por Sistema
    sistema_counts = query.with_entities(
        OrdemServico.sistema,
        func.count(OrdemServico.id)
    ).group_by(OrdemServico.sistema).all()
    
    # Dados por Mês (últimos 6 meses)
    mes_counts = query.with_entities(
        func.strftime('%Y-%m', OrdemServico.data_criacao).label('mes'),
        func.count(OrdemServico.id)
    ).group_by('mes').order_by('mes').limit(6).all()
    
    return jsonify({
        'status': dict(status_counts),
        'sistemas': dict(sistema_counts),
        'mensal': [{'mes': m[0], 'total': m[1]} for m in mes_counts]
    })

# ==================== INICIALIZAÇÃO DO BANCO ====================
def init_db():
    with app.app_context():
        db.create_all()
        
        # Cria usuário admin se não existir
        if not Usuario.query.filter_by(email='admin@exemplo.com').first():
            admin = Usuario(
                email='admin@exemplo.com',
                senha_hash=generate_password_hash('admin123'),
                nome='Administrador',
                unidade='Matriz',
                is_admin=True
            )
            db.session.add(admin)
            
            # Cria um usuário normal de teste
            user = Usuario(
                email='filial1@exemplo.com',
                senha_hash=generate_password_hash('123456'),
                nome='Usuário Filial',
                unidade='Filial SP',
                is_admin=False
            )
            db.session.add(user)
            db.session.commit()
            print("✅ Banco de dados inicializado!")
            print("👤 Admin: admin@exemplo.com / admin123")
            print("👤 Usuário: filial1@exemplo.com / 123456")

if __name__ == '__main__':
    init_db()
    # Alterar esta linha para produção:
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)