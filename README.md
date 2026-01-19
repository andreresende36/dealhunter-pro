# DealHunter Pro

Sistema de scraping automatizado para coletar ofertas do Mercado Livre com histórico de preços e informações de afiliação.

## 📋 Índice

- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Setup do Banco de Dados](#-setup-do-banco-de-dados)
- [Execução](#-execução)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Troubleshooting](#-troubleshooting)
- [Migrações](#-migrações)

## 🚀 Instalação

### Pré-requisitos

- Python 3.11+
- PostgreSQL (Supabase recomendado)
- Playwright

### Passo a Passo

```bash
# 1. Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# 2. Instalar dependências
cd app
pip install -r requirements.txt

# 3. Instalar Playwright
playwright install-deps
playwright install chromium
```

## ⚙️ Configuração

### 1. Criar arquivo .env

Copie o arquivo `.env.example` para `.env`:

```bash
cp app/.env.example app/.env
```

### 2. Configurar Variáveis de Ambiente

Edite o arquivo `app/.env` com suas configurações:

#### Banco de Dados (Supabase) - OBRIGATÓRIO

**Obter String de Conexão:**

1. Acesse o [Supabase Dashboard](https://supabase.com)
2. Vá em **Settings** → **Database** → **Connect** → **Connection String**
3. Selecione **Transaction Pooler** (recomendado) ou **Session Pooler**
4. Copie a string no formato **URI**

**Converter para asyncpg:**

Adicione `+asyncpg` após `postgresql`:

```env
# Formato do Supabase: postgresql://...
# Formato necessário: postgresql+asyncpg://...

DATABASE_URL=postgresql+asyncpg://postgres.xxxxx:SUA_SENHA@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

**⚠️ Importante:**
- **Transaction Pooler**: porta `6543` (recomendado)
- **Session Pooler**: porta `5432` (alternativa)
- O parâmetro `?sslmode=require` será processado automaticamente pelo código

**Alternativa: Componentes Individuais**

Se preferir, você pode usar componentes separados:

```env
DB_HOST=db.xxxxxxxxxxxxx.supabase.co
DB_PORT=6543
DB_USER=postgres
DB_PASSWORD=sua_senha_aqui
DB_NAME=postgres
```

#### Configurações de Scraping (Opcional)

```env
# Número máximo de scrolls na página
ML_MAX_SCROLLS=4

# Número de páginas para processar
NUMBER_OF_PAGES=1

# Desconto mínimo para considerar oferta (%)
MIN_DISCOUNT_PCT=50

# Mostrar apenas ofertas com preço antigo
ONLY_WITH_OLD_PRICE=false

# Delay entre scrolls (segundos)
ML_SCROLL_DELAY_S=0.45

# Delay entre páginas (segundos)
ML_PAGE_DELAY_S=0.0

# Número máximo de itens para imprimir
MAX_ITEMS_PRINT=20
```

#### Configurações de Afiliação (Opcional)

```env
# Concorrência para enriquecer ofertas com detalhes de afiliado
AFFILIATE_CONCURRENCY=3
```

### 3. Validar Configuração

Teste se está tudo configurado corretamente:

```bash
cd app
python check_env.py
```

Ou teste a conexão com o banco:

```bash
python test_db_connection.py
```

## 🗄️ Setup do Banco de Dados

### 1. Criar Projeto no Supabase

1. Acesse [https://supabase.com](https://supabase.com)
2. Crie uma conta ou faça login
3. Crie um novo projeto
4. Anote as credenciais de conexão

### 2. Aplicar Migrações

#### Opção A: Via SQL Editor (Recomendado)

1. No Supabase Dashboard, vá em **SQL Editor**
2. Clique em **New Query**
3. Abra o arquivo `migrations/001_initial_schema.sql`
4. Cole todo o conteúdo no editor e execute
5. Repita para `migrations/002_enable_rls_policies.sql`
6. Repita para `migrations/003_update_schema_uuid_ints.sql`

#### Opção B: Via Supabase CLI

```bash
# Instalar Supabase CLI (se ainda não tiver)
npm install -g supabase

# Fazer login
supabase login

# Vincular ao projeto
supabase link --project-ref seu-project-ref

# Aplicar migração
supabase db push
```

#### Opção C: Via psql

```bash
psql -h db.xxxxxxxxxxxxx.supabase.co -U postgres -d postgres -f migrations/001_initial_schema.sql
psql -h db.xxxxxxxxxxxxx.supabase.co -U postgres -d postgres -f migrations/002_enable_rls_policies.sql
psql -h db.xxxxxxxxxxxxx.supabase.co -U postgres -d postgres -f migrations/003_update_schema_uuid_ints.sql
```

### 3. Estrutura do Banco de Dados

O banco de dados contém as seguintes tabelas:

- **offers**: Armazena as ofertas coletadas
- **scrape_runs**: Registra cada execução de scraping
- **offer_scrape_runs**: Relaciona ofertas às execuções
- **price_history**: Histórico de preços das ofertas
- **affiliate_info**: Histórico de informações de afiliação

### 4. Funcionalidades

Quando o scraper é executado:

1. Cria um registro em `scrape_runs` com status "running"
2. Para cada oferta coletada:
   - Cria ou atualiza registro em `offers`
   - Vincula a oferta à execução em `offer_scrape_runs`
   - Salva histórico de preço em `price_history`
   - Salva informações de afiliação em `affiliate_info` (se disponível)
3. Atualiza `scrape_runs` com status "completed" e contadores

### 5. Consultas Úteis

```sql
-- Ver últimas ofertas coletadas
SELECT * FROM offers ORDER BY created_at DESC LIMIT 10;

-- Ver execuções de scraping
SELECT * FROM scrape_runs ORDER BY started_at DESC LIMIT 10;

-- Ver histórico de preços de uma oferta
SELECT * FROM price_history 
WHERE offer_id = 1 
ORDER BY recorded_at DESC;

-- Ver ofertas com maior desconto
SELECT * FROM offers 
WHERE discount_pct IS NOT NULL 
ORDER BY discount_pct DESC 
LIMIT 20;
```

## ▶️ Execução

### Executar Scraping

```bash
cd app
python main.py
```

Ou usando o módulo:

```bash
cd app
python -m main
```

### Testar Conexão com Banco

```bash
cd app
# Teste completo (diagnóstico + SQL)
python test_db_connection.py

# Apenas diagnóstico básico (DNS/TCP)
python test_db_connection.py --diagnose-only

# Apenas teste SQL (pula diagnóstico)
python test_db_connection.py --skip-diagnose
```

## 📁 Estrutura do Projeto

```
dealhunter-pro/
├── app/
│   ├── config/              # Configurações do projeto
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── database/            # Camada de banco de dados
│   │   ├── __init__.py
│   │   ├── connection.py    # Conexão com banco
│   │   ├── models.py        # Modelos SQLAlchemy
│   │   └── repositories.py  # Repositórios de dados
│   ├── models/              # Modelos de domínio
│   │   ├── __init__.py
│   │   └── offer.py
│   ├── scrapers/            # Módulos de scraping
│   │   ├── __init__.py
│   │   ├── ml_scraper.py    # Scraper do Mercado Livre
│   │   ├── affiliate_enricher.py  # Enriquecimento de afiliados
│   │   ├── playwright_utils.py    # Utilitários Playwright
│   │   └── constants.py     # Constantes
│   ├── services/            # Serviços de negócio
│   │   ├── __init__.py
│   │   ├── offer_filter.py  # Filtro de ofertas
│   │   └── scrape_service.py # Serviço principal de scraping
│   ├── utils/               # Utilitários
│   │   ├── __init__.py
│   │   ├── env.py           # Leitura de variáveis de ambiente
│   │   ├── format.py        # Formatação de dados
│   │   ├── logging.py       # Sistema de logging
│   │   ├── price.py         # Utilitários de preço
│   │   └── url.py           # Manipulação de URLs
│   ├── main.py              # Ponto de entrada principal
│   ├── runner.py            # Runner de scraping
│   ├── test_db_connection.py # Teste de conexão com banco
│   ├── check_env.py         # Verificador de variáveis de ambiente
│   └── requirements.txt     # Dependências Python
├── migrations/              # Migrações SQL
│   ├── README.md
│   ├── 001_initial_schema.sql
│   ├── 002_enable_rls_policies.sql
│   └── 003_update_schema_uuid_ints.sql
└── README.md               # Este arquivo
```

## 🔧 Troubleshooting

### Erro: "DATABASE_URL não configurada"

**Causa**: A variável `DATABASE_URL` não está definida ou está vazia.

**Solução**: 
1. Verifique se o arquivo `app/.env` existe
2. Verifique se `DATABASE_URL` está definida
3. Verifique se não há espaços extras: `DATABASE_URL=...` (correto)

### Erro: "Connection refused" ou "connection refused"

**Causa**: Host, porta ou credenciais incorretas.

**Solução**:
1. Verifique a string de conexão do Supabase
2. Certifique-se de usar `postgresql+asyncpg://` (não apenas `postgresql://`)
3. Verifique se a porta está correta (6543 para Transaction Pooler, 5432 para Session Pooler)

### Erro: "password authentication failed"

**Causa**: Senha incorreta.

**Solução**:
1. Verifique a senha no Supabase Dashboard
2. Se necessário, reset a senha em Settings > Database > Database password
3. Certifique-se de que caracteres especiais estão codificados na URL

### Erro: "Connection was closed in the middle of operation"

**Causa**: Session Pooler (porta 5432) pode não funcionar bem com `asyncpg`.

**Solução**:
1. **Use Transaction Pooler (porta 6543)** - Recomendado:
   - No Supabase Dashboard: Settings → Database → Connect → Connection String
   - Selecione **Transaction Pooler** → **URI**
   - Atualize a URL no `.env` mudando a porta de `5432` para `6543`

2. Verifique se Connection Pooling está habilitado no Supabase

### Erro: "Circuit breaker open"

**Causa**: Circuit breaker do Supabase ativado após muitas falhas.

**Solução**:
1. Aguarde alguns minutos (circuit breaker se reseta automaticamente)
2. Verifique se o projeto Supabase está **ATIVO** (não pausado)
3. Verifique as credenciais no Supabase Dashboard
4. Reduza temporariamente `DB_POOL_SIZE` no `.env`

### Erro: "Connection to database not available"

**Causa**: Pooler não consegue conectar ao banco interno.

**Solução**:
1. Teste com **Transaction Pooler (porta 6543)**:
   - Altere a porta de `5432` para `6543` na `DATABASE_URL`
   
2. Verifique se Connection Pooling está habilitado:
   - Settings → Database → Connection Pooling

3. Verifique formato do usuário:
   - Deve ser `postgres.<project_ref>` (não apenas `postgres`)
   - Exemplo: `postgres.olezaxxwyfifuxdrvghg`

### Erro: "relation does not exist"

**Causa**: Tabelas não foram criadas.

**Solução**: Certifique-se de que as migrações foram aplicadas (veja [Setup do Banco de Dados](#-setup-do-banco-de-dados))

### Erro: "asyncpg not found"

**Causa**: Dependência não instalada.

**Solução**:
```bash
cd app
pip install -r requirements.txt
```

### Formato Correto da URL

**Transaction Pooler (recomendado)**:
```env
DATABASE_URL=postgresql+asyncpg://postgres.xxxxx:SENHA@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

**Session Pooler (alternativa)**:
```env
DATABASE_URL=postgresql+asyncpg://postgres.xxxxx:SENHA@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require
```

**⚠️ Pontos Importantes:**
- Usuário deve ser `postgres.<project_ref>`, não apenas `postgres`
- O parâmetro `?sslmode=require` será processado automaticamente
- SSL é configurado automaticamente via `connect_args`

## 📦 Migrações

As migrações SQL estão em `migrations/`.

### Como Aplicar

Veja [Setup do Banco de Dados - Aplicar Migrações](#2-aplicar-migrações)

### Estrutura das Migrações

- `001_initial_schema.sql`: Schema inicial com todas as tabelas, índices e triggers
- `002_enable_rls_policies.sql`: Habilita RLS e cria políticas para API
- `003_update_schema_uuid_ints.sql`: Atualiza IDs para UUID e percentuais para INT

### Ordem de Aplicação

As migrações devem ser aplicadas em ordem numérica (001, 002, etc.).

## 📚 Recursos Adicionais

- [Documentação do Supabase - Database](https://supabase.com/docs/guides/database)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [Playwright Documentation](https://playwright.dev/python/)

## 🔒 Segurança

### ⚠️ NUNCA faça commit do arquivo .env!

O arquivo `.env` contém informações sensíveis (senhas, tokens). Ele já está no `.gitignore`, mas sempre verifique:

```bash
# Verificar se .env está ignorado
git check-ignore app/.env
# Deve retornar: app/.env
```

### Melhores Práticas

1. **Nunca compartilhe** o arquivo `.env` em repositórios públicos
2. **Use variáveis de ambiente** em produção (não arquivo .env)
3. **Rotacione senhas** periodicamente
4. **Use diferentes credenciais** para desenvolvimento e produção
