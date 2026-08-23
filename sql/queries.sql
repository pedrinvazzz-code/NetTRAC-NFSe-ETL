-- ============================================================
-- Queries de análise — NFS-e NetTRAC
-- Rodar no SQL Editor do Supabase (ou qualquer Postgres)
-- ============================================================


-- ============================================================
-- 1. FATURAMENTO MENSAL
--    Receita total emitida por mês, em ordem cronológica.
-- ============================================================

select
    to_char(competencia, 'YYYY-MM')   as mes,
    count(*)                           as qtd_notas,
    sum(valor_servico)                 as faturamento_total
from notas
where status = 'ativa'
group by mes
order by mes;


-- ============================================================
-- 2. FATURAMENTO ANUAL
--    Receita total emitida por ano.
-- ============================================================

select
    extract(year from competencia)::int  as ano,
    count(*)                              as qtd_notas,
    sum(valor_servico)                    as faturamento_total
from notas
where status = 'ativa'
group by ano
order by ano;


-- ============================================================
-- 3. FATURAMENTO POR CLIENTE (ranking)
--    Quais clientes geraram mais receita no total.
-- ============================================================

select
    t.razao_social                          as cliente,
    t.cpf_cnpj,
    count(n.id)                             as qtd_notas,
    sum(n.valor_servico)                    as faturamento_total,
    round(avg(n.valor_servico), 2)          as ticket_medio
from notas n
join tomadores t on t.id = n.tomador_id
where n.status = 'ativa'
group by t.id, t.razao_social, t.cpf_cnpj
order by faturamento_total desc;


-- ============================================================
-- 4. FATURAMENTO POR CLIENTE POR MÊS
--    Série histórica de receita de cada cliente.
-- ============================================================

select
    to_char(n.competencia, 'YYYY-MM')   as mes,
    t.razao_social                       as cliente,
    count(n.id)                          as qtd_notas,
    sum(n.valor_servico)                 as faturamento
from notas n
join tomadores t on t.id = n.tomador_id
where n.status = 'ativa'
group by mes, t.id, t.razao_social
order by mes, faturamento desc;


-- ============================================================
-- 5. FATURAMENTO POR CATEGORIA DE SERVIÇO
--    Quais tipos de serviço geram mais receita.
-- ============================================================

select
    coalesce(categoria_servico, 'Sem categoria')   as categoria,
    count(*)                                        as qtd_notas,
    sum(valor_servico)                              as faturamento_total,
    round(100.0 * sum(valor_servico)
          / sum(sum(valor_servico)) over (), 1)     as pct_faturamento
from notas
where status = 'ativa'
group by categoria
order by faturamento_total desc;


-- ============================================================
-- 6. ISS APURADO POR MÊS
--    Estimativa de ISS a recolher (alíquota 5% padrão).
--    Ajuste a alíquota conforme o município, se necessário.
-- ============================================================

select
    to_char(competencia, 'YYYY-MM')       as mes,
    sum(valor_servico)                     as base_calculo,
    round(sum(valor_servico) * 0.05, 2)   as iss_estimado_5pct
from notas
where status = 'ativa'
group by mes
order by mes;


-- ============================================================
-- 7. NOTAS PENDENTES DE PAGAMENTO
--    Notas emitidas que ainda não foram pagas.
-- ============================================================

select
    n.numero,
    n.data_emissao::date          as emissao,
    n.competencia,
    t.razao_social                as cliente,
    n.descricao,
    n.valor_servico,
    n.status_pagamento,
    current_date - n.competencia  as dias_em_aberto
from notas n
join tomadores t on t.id = n.tomador_id
where n.status = 'ativa'
  and n.status_pagamento = 'Pendente'
order by n.competencia;


-- ============================================================
-- 8. RESUMO GERAL
--    Painel rápido: totais consolidados de todo o histórico.
-- ============================================================

select
    count(*)                                     as total_notas,
    count(distinct tomador_id)                   as total_clientes,
    min(competencia)                             as primeira_nota,
    max(competencia)                             as ultima_nota,
    sum(valor_servico)                           as faturamento_total,
    round(avg(valor_servico), 2)                 as ticket_medio,
    sum(case when status_pagamento = 'Pendente'
             then valor_servico else 0 end)      as a_receber
from notas
where status = 'ativa';
