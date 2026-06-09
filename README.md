# Oficina Pro

Sistema local para oficina mecânica com login, cadastro de usuários, criação de orçamentos, aprovação/reprovação e controle financeiro.

Versão atual: **v1.1 - Fundação SaaS e Painel Master**.

Esta versão está em homologação local e prepara o sistema para multiempresa, autenticação com sessão, assinatura e monitoramento da plataforma.

## Como usar

1. Dê dois cliques em `iniciar_sistema.bat` ou rode `python server.py` nesta pasta.
2. Abra `http://127.0.0.1:4173/` no navegador.
3. Entre com e-mail e senha.
4. Usuários novos devem ser criados pelo MASTER na aba **Configurações**.
5. Crie orçamentos em **Atendimento > Orçamentos > Novo orçamento**.
6. Todo orçamento nasce como **pendente**.
7. Use **Aprovar** ou **Reprovar** depois do retorno do cliente.
8. Somente orçamentos aprovados aparecem em **Financeiro > Fluxo de caixa**.

## Usuário administrador

O sistema cria automaticamente um usuário administrador:

- E-mail: `master@oficina.local`
- Senha: `Master@123`

O usuário MASTER visualiza todos os orçamentos e todo o financeiro do sistema.

Usuários criados pelo MASTER em **Configurações** recebem a senha padrão informada no cadastro.

## Banco de dados

O sistema usa **SQLite local**. Os dados ficam no arquivo `oficina.db`, salvo nesta pasta do projeto.

Esse banco é compartilhado por qualquer navegador que abra `http://127.0.0.1:4173/` neste computador. Para backup, copie o arquivo `oficina.db` com o sistema fechado.

O banco já possui uma base inicial para multiempresa: a tabela `companies` e o campo `companyId` nas tabelas principais. Os dados locais atuais ficam vinculados à empresa padrão **Oficina Pro Local**.

Este banco local está sendo usado como ambiente de homologação. Ele pode receber testes de migração, autenticação, multiempresa, assinaturas e painel master antes de qualquer ambiente de produção.

Para produção comercial SaaS, a recomendação técnica é migrar para PostgreSQL gerenciado. Consulte `docs/POSTGRESQL.md`.

## Preparação para nuvem

- Configuração por ambiente via `.env`.
- Exemplo de configuração em `.env.example`.
- `Dockerfile` e `Procfile` para deploy inicial.
- Preflight técnico em `python scripts/preflight.py`.
- Validação de schema em `python scripts/validate_schema.py`.
- Backup SQLite de homologação em `python scripts/backup_sqlite.py`.
- Guia de deploy em `docs/DEPLOY.md`.
- Hash de senha novo com PBKDF2 e migração automática de hashes antigos no login.
- Headers básicos de segurança HTTP.
- Smoke tests de API em `python scripts/smoke_api.py`.
- Registro de baseline de schema em `schema_migrations`.
- Snapshot auditável do schema em `migrations/20260609_web_saas_baseline.sqlite.sql`.
- Baseline PostgreSQL em `migrations/20260609_web_saas_baseline.postgres.sql`.
- Exportação SQLite JSONL para migração em `python scripts/export_sqlite_jsonl.py`.
- CI no GitHub Actions para validar sintaxe, schema, preflight e smoke API.

## Recursos incluidos

- Tela de login e cadastro de usuários.
- Login validado no servidor local.
- Sessão com token temporário após o login.
- Rotas da API protegidas por token, exceto saúde do sistema e login.
- Senhas armazenadas com hash SHA-256.
- A opção de lembrar acesso salva apenas o usuário/e-mail, não a senha.
- Cadastro de cliente, e-mail, telefone, endereço, veículo, placa, peças, mão de obra e observações.
- Cadastro central de clientes e veículos para histórico operacional.
- Orçamento pode reutilizar cliente e veículo já cadastrados.
- Seleção de veículo no orçamento também preenche automaticamente o proprietário.
- Busca automática por e-mail, telefone ou placa para evitar redigitação.
- Lançamento separado de peças com quantidade, descrição e valor unitário.
- Lançamento separado de mão de obra com descrição e valor.
- Resumo automático de total em peças, total em mão de obra e total do orçamento.
- Menu Atendimento com Orçamentos, Novo orçamento, Aprovados, Reprovados e Pendentes.
- Menu Atendimento com Clientes e veículos.
- Menu Atendimento com Ordens de serviço.
- Geração de ordem de serviço a partir de orçamento aprovado.
- Acompanhamento de OS por status: aberta, em andamento, aguardando peça, concluída e entregue.
- Menu Financeiro com Contas à pagar, Tabela de custos e Fluxo de caixa.
- Visualização de orçamentos aprovados diretamente no fluxo de caixa.
- Edição de orçamento aprovado com retorno automático para pendente e nova aprovação.
- Tela de configurações exclusiva do MASTER para criação de usuários com nome completo, nome de usuário, email, telefone, senha e nível de acesso.
- Menu lateral de Configurações com subopções para Usuários e Níveis de acesso.
- Busca e gerenciamento de usuários com bloqueio de acesso, alteração de senha e exclusão.
- Níveis de acesso: Administrador, Financeiro e Analista.
- Criação de níveis de acesso personalizados pelo MASTER.
- Permissões por nível para definir visualização, criação, aprovação e edição por área do sistema.
- Exemplo: criar um nível que visualiza financeiro, mas não edita orçamentos pelo financeiro.
- Status de orçamento: pendente, aprovado e reprovado.
- Envio por e-mail via aplicativo de e-mail padrão do computador.
- Impressão do orçamento.
- Fluxo de caixa contabilizando apenas orçamentos aprovados.
- Base inicial multiempresa com empresa padrão, vínculo de usuários e filtro por `companyId` nas rotas da API.
- Base inicial de assinatura com tabelas `subscriptions` e `payments`.
- Base inicial de Painel Master via API para monitorar empresas, planos, status de assinatura e pagamentos.
- Tela inicial de Painel Master, visível apenas para usuário plataforma, com resumo de oficinas, assinaturas e pagamentos.
- Cadastro de nova oficina pelo Painel Master com usuário dono e assinatura inicial.
- Ações administrativas no Painel Master para atualizar assinatura e registrar pagamento manual.
- Filtros no Painel Master por status, plano e busca por oficina.
- Auditoria master para registrar criação de oficina, alteração de assinatura e lançamento de pagamento.
- Catálogo comercial de planos: Essencial, Profissional e Premium.
- Ciclos de cobrança: mensal, trimestral e anual.
- Regras de acesso por plano aplicadas no frontend e backend.
- Resumo "Minha assinatura" no painel do cliente.
- Painel Master não exibe faturamento operacional das oficinas por padrão; acesso a valores da oficina fica reservado para suporte autorizado e auditável.

## Planos em homologação

| Plano | Indicação | Recursos principais | Usuários | Mensal | Trimestral | Anual |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Essencial | Oficina pequena começando a organizar atendimento | Painel e orçamentos | 1 | R$ 59,00 | R$ 159,00 | R$ 549,00 |
| Profissional | Plano principal para operação completa | Orçamentos, financeiro, estoque e usuários | 5 | R$ 99,00 | R$ 267,00 | R$ 949,00 |
| Premium | Operação maior ou gestão avançada | Recursos do Profissional, mais usuários, relatórios avançados e suporte prioritário | 15 | R$ 149,00 | R$ 402,00 | R$ 1.399,00 |
