-- Schema do banco de notas fiscais (NFS-e padrão nacional)
-- Rodar no SQL Editor do Supabase (ou qualquer Postgres)

create table if not exists tomadores (
    id serial primary key,
    cpf_cnpj text unique not null,
    razao_social text not null,
    municipio_codigo_ibge text,
    created_at timestamptz default now()
);

create table if not exists notas (
    id serial primary key,
    numero text not null,
    chave_acesso text unique not null,
    data_emissao timestamptz not null,
    competencia date not null,
    tomador_id int references tomadores(id),
    codigo_servico text,
    descricao text,
    categoria_servico text,
    valor_servico numeric(12, 2) not null,
    status text default 'ativa',
    created_at timestamptz default now()
);

-- chave_acesso é o identificador único nacional da nota, garante que
-- rodar o script de importação várias vezes nunca duplica registro.

create index if not exists idx_notas_tomador on notas (tomador_id);
create index if not exists idx_notas_competencia on notas (competencia);

-- Guarda o cursor (ultimo NSU processado) da sincronizacao via API,
-- pra cada execucao so buscar documentos novos.
create table if not exists sync_estado (
    chave text primary key,
    valor text not null,
    atualizado_em timestamptz default now()
);
