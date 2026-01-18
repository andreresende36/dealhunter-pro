# Migrations

Este diretório contém as migrações SQL do banco de dados.

## Como aplicar as migrações no Supabase

### Opção 1: Via SQL Editor no Supabase Dashboard
1. Acesse o Supabase Dashboard
2. Vá em "SQL Editor"
3. Cole o conteúdo do arquivo `001_initial_schema.sql`
4. Execute o script

### Opção 2: Via Supabase CLI
```bash
supabase db push
```

### Opção 3: Via psql
```bash
psql -h <seu-host> -U <seu-usuario> -d <seu-database> -f migrations/001_initial_schema.sql
```

## Estrutura das Migrações

- `001_initial_schema.sql`: Schema inicial com todas as tabelas, índices e triggers
- `002_enable_rls_policies.sql`: Habilita RLS e cria políticas para permitir acesso via API REST do Supabase

## Ordem de Aplicação

As migrações devem ser aplicadas em ordem numérica (001, 002, etc.).
