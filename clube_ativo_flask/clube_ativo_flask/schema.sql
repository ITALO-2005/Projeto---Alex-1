DROP TABLE IF EXISTS user;
DROP TABLE IF EXISTS clube;
DROP TABLE IF EXISTS evento;
DROP TABLE IF EXISTS noticia;
DROP TABLE IF EXISTS forum_topico;
DROP TABLE IF EXISTS forum_post;
DROP TABLE IF EXISTS badge;
DROP TABLE IF EXISTS clube_media;
DROP TABLE IF EXISTS cardapio_ru;
DROP TABLE IF EXISTS calendario_academico;
DROP TABLE IF EXISTS inscricao_evento;
DROP TABLE IF EXISTS membros_clube;
DROP TABLE IF EXISTS user_badges;

-- Tabela para armazenar os utilizadores da aplicação
CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    image_file TEXT NOT NULL DEFAULT 'default.jpg'
);

-- Tabela para armazenar os clubes
CREATE TABLE clube (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    descricao TEXT NOT NULL,
    categoria TEXT NOT NULL,
    lider_id INTEGER,
    FOREIGN KEY (lider_id) REFERENCES user (id)
);

-- Tabela para armazenar os eventos criados pelos clubes
CREATE TABLE evento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    descricao TEXT NOT NULL,
    vagas INTEGER NOT NULL,
    data_evento TEXT NOT NULL, -- Usamos TEXT para DATETIME para simplificar com SQLite
    clube_id INTEGER NOT NULL,
    FOREIGN KEY (clube_id) REFERENCES clube (id)
);

-- Tabela para armazenar as notícias e anúncios
CREATE TABLE noticia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    data_publicacao TEXT NOT NULL,
    evento_id INTEGER,
    FOREIGN KEY (evento_id) REFERENCES evento (id)
);

-- Tabela para armazenar os tópicos do fórum de cada clube
CREATE TABLE forum_topico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    data_criacao TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    clube_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (clube_id) REFERENCES clube (id)
);

-- Tabela para armazenar as respostas (posts) nos tópicos do fórum
CREATE TABLE forum_post (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conteudo TEXT NOT NULL,
    data_criacao TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    topico_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (topico_id) REFERENCES forum_topico (id)
);

-- Tabela para armazenar os selos (badges) que podem ser conquistados
CREATE TABLE badge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    descricao TEXT NOT NULL,
    icon_class TEXT NOT NULL
);

-- Tabela para armazenar os ficheiros de mídia de cada clube
CREATE TABLE clube_media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    descricao TEXT,
    data_upload TEXT NOT NULL,
    clube_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (clube_id) REFERENCES clube (id),
    FOREIGN KEY (user_id) REFERENCES user (id)
);

-- Tabela para o cardápio do Restaurante Universitário
CREATE TABLE cardapio_ru (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT UNIQUE NOT NULL,
    prato_principal TEXT NOT NULL,
    vegetariano TEXT NOT NULL,
    acompanhamento TEXT NOT NULL,
    salada TEXT NOT NULL,
    sobremesa TEXT NOT NULL
);

-- Tabela para o calendário académico
CREATE TABLE calendario_academico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    descricao TEXT NOT NULL,
    tipo TEXT NOT NULL
);

-- Tabela que liga os utilizadores aos eventos em que estão inscritos
CREATE TABLE inscricao_evento (
    user_id INTEGER NOT NULL,
    evento_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, evento_id),
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (evento_id) REFERENCES evento (id)
);

-- Tabela que liga os utilizadores aos clubes de que são membros
CREATE TABLE membros_clube (
    user_id INTEGER NOT NULL,
    clube_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, clube_id),
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (clube_id) REFERENCES clube (id)
);

-- Tabela que liga os utilizadores aos selos que conquistaram
CREATE TABLE user_badges (
    user_id INTEGER NOT NULL,
    badge_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, badge_id),
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (badge_id) REFERENCES badge (id)
);
