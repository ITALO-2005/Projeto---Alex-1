import os
import shutil
from app import app, db
from app import User, Clube, Evento, Noticia, ForumTopico, ForumPost
from datetime import datetime, timezone

# --- CAMINHO CORRETO DO BANCO DE DADOS (DENTRO DA PASTA 'instance') ---
DB_PATH = os.path.join(app.instance_path, 'database.db')
MIGRATIONS_FOLDER = 'migrations'

print("--- INICIANDO RESET TOTAL DO BANCO DE DADOS (VERSÃO CORRETA) ---")

# 1. Apagar o arquivo do banco de dados na pasta 'instance', se existir
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print(f"✅ Banco de dados verdadeiro em '{DB_PATH}' foi apagado.")
else:
    print(f"ℹ️ Banco de dados verdadeiro em '{DB_PATH}' não encontrado.")

# 2. Apagar a pasta de migrações, se ela existir
if os.path.exists(MIGRATIONS_FOLDER):
    shutil.rmtree(MIGRATIONS_FOLDER)
    print(f"✅ Pasta '{MIGRATIONS_FOLDER}' foi apagada.")
else:
    print(f"ℹ️ Pasta '{MIGRATIONS_FOLDER}' não encontrada.")

# 3. Usar o contexto da aplicação para recriar tudo do zero
with app.app_context():
    print("⏳ Criando todas as tabelas a partir do app.py...")
    db.create_all()
    print("✅ Tabelas criadas com sucesso.")

    print("⏳ Adicionando dados de exemplo (seeding)...")
    try:
        # Lógica de seeding para evitar o erro de UNIQUE constraint
        if Clube.query.count() == 0:
            clube1 = Clube(nome='Clube de Programação', descricao='Para entusiastas de código e desenvolvimento.', categoria='Tecnologia')
            clube2 = Clube(nome='Clube de Leitura', descricao='Discussões sobre obras literárias.', categoria='Cultura')
            clube3 = Clube(nome='Clube de Esportes', descricao='Organização de treinos e campeonatos.', categoria='Esportes')
            db.session.add_all([clube1, clube2, clube3])
            db.session.commit()

            e1 = Evento(titulo='Maratona de Programação', descricao='Resolva desafios de programação em equipe.', vagas=50, clube_id=clube1.id, data_evento=datetime(2025, 8, 10, 9, 0, 0, tzinfo=timezone.utc))
            e2 = Evento(titulo='Debate sobre Ficção Científica', descricao='Análise do livro "Duna".', vagas=30, clube_id=clube2.id, data_evento=datetime(2025, 8, 15, 18, 30, 0, tzinfo=timezone.utc))
            e3 = Evento(titulo='Torneio de Vôlei', descricao='Monte sua equipe e participe!', vagas=40, clube_id=clube3.id, data_evento=datetime(2025, 8, 20, 14, 0, 0, tzinfo=timezone.utc))
            db.session.add_all([e1, e2, e3])
            db.session.commit()

            n1 = Noticia(titulo='Inscrições Abertas para a Maratona!', conteudo='Não perca!', evento_id=e1.id)
            db.session.add(n1)
            db.session.commit()
            print("✅ Dados de exemplo inseridos com sucesso.")
        else:
             print("ℹ️ Dados de exemplo já existem no banco.")

    except Exception as e:
        print(f"❌ Erro ao inserir dados de exemplo: {e}")
        db.session.rollback()

print("\n--- RESET CONCLUÍDO! ---")
print("Agora sim! Rode 'flask run' para iniciar a aplicação.")