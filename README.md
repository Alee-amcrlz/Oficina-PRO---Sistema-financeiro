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

## Recursos incluidos

- Tela de login e cadastro de usuários.
- Login validado no servidor local.
- Sessão com token temporário após o login.
- Rotas da API protegidas por token, exceto saúde do sistema e login.
- Senhas armazenadas com hash SHA-256.
- A opção de lembrar acesso salva apenas o usuário/e-mail, não a senha.
- Cadastro de cliente, e-mail, telefone, endereço, veículo, placa, peças, mão de obra e observações.
- Lançamento separado de peças com quantidade, descrição e valor unitário.
- Lançamento separado de mão de obra com descrição e valor.
- Resumo automático de total em peças, total em mão de obra e total do orçamento.
- Menu Atendimento com Orçamentos, Novo orçamento, Aprovados, Reprovados e Pendentes.
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
- Painel Master não exibe faturamento operacional das oficinas por padrão; acesso a valores da oficina fica reservado para suporte autorizado e auditável.
