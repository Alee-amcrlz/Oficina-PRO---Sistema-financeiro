# Oficina Pro

Sistema local para oficina mecânica com login, cadastro de usuários, criação de orçamentos, aprovação/reprovação e controle financeiro.

## Como usar

1. Abra o arquivo `index.html` no navegador.
2. Entre com e-mail e senha.
3. Usuários novos devem ser criados pelo MASTER na aba **Configurações**.
4. Crie orçamentos em **Atendimento > Orçamentos > Novo orçamento**.
5. Todo orçamento nasce como **pendente**.
6. Use **Aprovar** ou **Reprovar** depois do retorno do cliente.
7. Somente orçamentos aprovados aparecem em **Financeiro > Fluxo de caixa**.

## Usuário administrador

O sistema cria automaticamente um usuário administrador:

- E-mail: `master@oficina.local`
- Senha: `Master@123`

O usuário MASTER visualiza todos os orçamentos e todo o financeiro do sistema.

Usuários criados pelo MASTER em **Configurações** recebem a senha padrão informada no cadastro.

## Banco de dados

Esta primeira versão usa **IndexedDB**, o banco de dados local do navegador, para registrar usuários e orçamentos. Os dados ficam salvos no navegador usado no computador.

## Recursos incluidos

- Tela de login e cadastro de usuários.
- Senhas armazenadas com hash SHA-256.
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
