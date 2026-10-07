# 0031. Abrir o autoatendimento de conta, com as telas de senha no IdP, a API de conta para a SPA e o `sub` em UUID

## Status

Proposto — 2026-09-30

Substitui a ADR (Architecture Decision Record) 0023. Emenda quatro ADRs, que **permanecem aceitas e em vigor** fora do que se diz aqui:

- a 0003, em três pontos: a chave primária deixa de ir na claim `sub`; `email_verified` entra, porque o fluxo que a alimenta passa a existir; e a troca de e-mail, que ela deixou por decidir, fica decidida;
- a 0013, no valor do campo `sub` e no resumo do identificador, agora calculado em minúsculas;
- a 0016, na premissa de que não há rota de recuperação de senha, no alcance do limitador por caminho e no que o login bem-sucedido zera no `axes`;
- a 0029, no lugar em que o sinal `tokens_revogados` é definido e em quem o emite.

Amplia o conjunto de eventos da 0013, como a 0016 e a 0029 já fizeram. A contraparte é a ADR 0020 da aplicação de página única (SPA, de _Single-Page Application_), que substitui a 0012 dela. As duas passam a "Aceito" no mesmo ato, antes da implantação, e nesse ato a 0023 recebe o status "Substituído por ADR-0031".

## Contexto

O provedor de identidade (IdP, de _Identity Provider_) só cria, altera e remove conta pelo admin (ADR 0023, invariante N4). A pessoa não se cadastra, não troca a própria senha nem o próprio e-mail e não recupera o acesso quando esquece a senha: `/accounts/password_reset/` é 404 deliberado. A claim `email_verified` não existe, e a claim `sub` é a chave primária inteira da conta (ADR 0003), o que mostra às relying parties (RPs) a sequência interna do banco.

A 0023 deixou escritas, nesta ordem, as pré-condições de um cadastro público: validadores de senha declarados, teto de requisição no caminho de cadastro, verificação de e-mail e, só então, a claim `email_verified`. A primeira está cumprida em `config/settings.py` (`AUTH_PASSWORD_VALIDATORS`); as outras três entram nesta decisão.

O terreno, conferido no django-oauth-toolkit (DOT) 3.4.1, no Django 5.2 e no `django-axes` 8.3.1:

- **Cadastro pelo protocolo.** O toolkit implementa o OpenID Connect (OIDC) Prompt Create 1.0 em `handle_prompt_create` (`oauth2_provider/views/base.py:325`). Desligado, responde 400 a `prompt=create`. Ligado, valida o pedido de autorização, desvia ao cadastro a pessoa sem sessão, com um `next` absoluto para o mesmo `/o/authorize/` sem `create`, e a descoberta passa a anunciar `create` (`oauth2_provider/views/oidc.py:99-100`).
- **Claim `sub`.** `get_claim_dict` (`oauth2_provider/oauth2_validators.py:1337-1350`) começa por `str(r.user.pk)` e aplica `get_additional_claims()` por cima. O mapa de claims por scope já liga `nickname` e `updated_at` a `profile`, e `email_verified` a `email` (`:199`, `:208` e `:210`).
- **Recurso protegido.** `ScopedProtectedResourceView` responde 403 sem corpo a toda falha (`oauth2_provider/views/mixins.py:213-223`). A variante `ScopedProtectedResourceMetadataView` (`oauth2_provider/views/generic.py:63`) responde 401 a token ausente ou inválido e 403 a `insufficient_scope`, os dois com o desafio `WWW-Authenticate: Bearer`, que leva o parâmetro `resource_metadata` da RFC 9728 (`mixins.py:371-381`). O `dispatch` dela guarda só o usuário (`mixins.py:254-265`). O toolkit não confere `is_active` no Bearer, e toda Application pode pedir todo scope declarado.
- **CSRF.** A view de recurso é uma `View` comum, sem isenção de CSRF (_Cross-Site Request Forgery_): um `PATCH` da SPA levaria 403 do `CsrfViewMiddleware` antes de o Bearer ser lido.
- **Carimbo de senha.** No login de uma conta com hash legado, `check_password` regrava o hash por `set_password` e `save`, e zera `_password` antes do `save` (`django/contrib/auth/base_user.py:106-110`: "Password hash upgrades shouldn't be considered password changes"). O `save` só avisa os validadores de senha quando `_password` não é `None`.
- **Caixa do e-mail.** `normalize_email` só põe o domínio em minúsculas, e a unicidade do Postgres distingue caixa. O `axes` conta pelo `username` como o recebe.
- **Zeramento no login.** Com `AXES_RESET_ON_SUCCESS`, o handler de banco do `axes` apaga no login bem-sucedido as linhas de `AccessAttempt` de cada filtro de `AXES_LOCKOUT_PARAMETERS`: as da conta e as da origem. A 0016 o registra como contador da conta zerado. Com o cadastro aberto, quem ataca uma conta entra na própria, pela mesma origem, e apaga as falhas que a origem acumulou contra a vítima.
- **Teto por caminho.** `config/limites.py` busca `request.path` por igualdade: a rota de confirmação da redefinição, que leva o token no caminho, não tem entrada que a alcance.
- **Idioma.** O toolkit traz tradução para o português. Com `LANGUAGE_CODE` em `pt-br`, o `error_description` de `/o/token/` e do `WWW-Authenticate` sairia acentuado, fora do conjunto de caracteres da RFC 6749.

## Decisão

Vamos dar à pessoa o cadastro, a leitura, a edição e a exclusão da própria conta, e a recuperação da senha. Tudo o que recebe senha é página do IdP; o resto é uma API JSON sob `/api/conta/`, consumida pela SPA com o `access_token` dela. A senha continua a trafegar só dentro do IdP. O lado do IdP entra numa implantação só. Caminhos, campos, configurações e sinais novos levam nomes em português, como o código já faz.

**A conta.** `accounts.User` ganha:

- `sub`, UUID (_Universally Unique Identifier_) versão 4, único, não editável, gerado na criação. A chave primária continua sendo o `id` interno, e nenhuma chave estrangeira muda;
- `nickname`, com até 150 caracteres, como `first_name` e `last_name`;
- `email_verified`, `email_verificado_em`, `senha_alterada_em`, `updated_at`, `desativada_em`, `desativada_por` (`propria_pessoa` ou `admin`), `termos_versao` e `termos_aceitos_em`.

O e-mail é gravado em minúsculas, e todo caminho de login, inclusive o `/admin/login/`, o põe em minúsculas antes de autenticar; `manage.py changepassword` o recebe como está gravado, em minúsculas. O banco recusa duas contas que só a caixa distinga, por uma restrição única sobre `Lower(email)`. A migração das contas atuais **para** com erro, sem estado parcial, se duas colidirem. As contas atuais recebem um UUID cada, `email_verified` falso e `updated_at` igual a `date_joined`.

Três regras moram no `save()` do modelo, para valer no admin, nas páginas, na API e no shell:

- e-mail que muda zera `email_verified` e `email_verificado_em`;
- `updated_at` muda só quando muda o valor de `first_name`, `last_name`, `nickname`, `email` ou `email_verified`; login, senha, termos e desativação não o tocam;
- `senha_alterada_em` é carimbado quando `_password` não é `None`. Isso cobre admin, `changepassword`, criação, troca e redefinição, e exclui o re-hash. É dependência declarada de atributo privado do Django.

No admin, `sub`, `email_verified` e os carimbos ficam somente leitura, num grupo próprio. Desativar pelo admin carimba `desativada_em` e `desativada_por=admin`; reativar zera os dois. Trocar o e-mail pelo admin não envia e-mail nenhum.

**O contrato com as RPs.** Muda nos dois projetos:

- `sub` passa a ser o UUID em texto minúsculo com hífens, devolvido por `get_additional_claims()` em `accounts/oauth_validators.py`. Nenhum método de protocolo é sobrescrito para isso;
- `email_verified`, booleana, entra no scope `email`; `nickname`, presente mesmo vazia, e `updated_at`, em segundos desde 1970, entram no scope `profile`;
- entra o scope `conta`, que só a API de conta exige;
- `create` entra em `prompt_values_supported`;
- o CORS (_Cross-Origin Resource Sharing_) passa a valer também em `^/api/conta/`, com a mesma origem exata, e expõe `WWW-Authenticate` e `Retry-After` ao `fetch`.

`given_name` e `family_name` ficam fora.

**As páginas do IdP.** Moram em `accounts/paginas.py`, com CSRF, sessão de login do IdP, requisitos de senha montados a partir de `AUTH_PASSWORD_VALIDATORS` e volta só a destinos fixos da SPA:

- cadastro em `/accounts/registrar/`, alcançado pelo `prompt=create` do toolkit (`OIDC_RP_INITIATED_REGISTRATION_ENABLED` e `OIDC_RP_INITIATED_REGISTRATION_URL`). Cria a conta ativa, sem staff, com o aceite da versão vigente dos termos; abre a sessão por `login()` com o backend nomeado; e segue o `next` conferido como o `LoginView` confere, ou vai à raiz da SPA;
- recuperação pelas quatro views do Django, montadas uma a uma, com link de uma hora e uso único. Conta `is_staff` ou `is_superuser` não recebe link, e o link de uma conta da equipe não abre o formulário; a resposta do pedido é a mesma, e a equipe troca a senha por `manage.py changepassword`. Ao concluir, a senha muda, `email_verified` vira verdadeiro e a página final leva à SPA, sem abrir sessão;
- troca de senha, que mantém a sessão atual e derruba as outras;
- troca de e-mail, que vale na hora, mantém o `sub` e as sessões, envia a confirmação ao endereço novo e o aviso ao antigo;
- exclusão, que oferece desativar ou apagar e recusa conta `is_staff` ou `is_superuser`. Apagar é recusado a conta dona de Application, porque a remoção levaria em cascata a Application e os tokens da RP; ela só desativa. Apagar remove a conta e as linhas de `AccessAttempt`, `AccessFailureLog` e `AccessLog` do `axes` cujo `username` é o e-mail, sem distinção de caixa. Como a troca de e-mail, pela página ou pelo admin, apaga as linhas do endereço antigo, apagar não deixa endereço anterior no `axes`; a trilha fica.

Toda senha atual é conferida por `authenticate()`, com o e-mail em minúsculas no argumento `username`, para que o `axes` conte as falhas na mesma conta. A tela de login ganha formulário próprio. Ele põe o e-mail em minúsculas antes de autenticar e diz que a conta está desativada só a quem acerta a senha dela e não está bloqueado pelo `axes`. A tela ganha também "Esqueci a senha" e "Criar conta", este com o `next` preservado.

**O zeramento do `axes`.** O login bem-sucedido passa a apagar só as linhas de `AccessAttempt` da própria conta, de toda origem, por um handler próprio em `accounts/tentativas.py`, apontado em `AXES_HANDLER`. Ele herda do handler de banco da biblioteca e sobrescreve só `reset_user_attempts`. As falhas da origem contra as outras contas ficam até o prazo. A redefinição de senha apaga as mesmas linhas, pela mesma função. No resto, a 0016 continua valendo: teto, prazo, contagem por conta e por origem e contador em banco.

Troca de senha, redefinição e exclusão revogam os tokens da conta em todas as Applications. A função que revoga e o sinal `tokens_revogados` saem de `accounts/logout_rp.py` para `accounts/revogacao.py`, que passa a servir o logout pela RP e as páginas. O sinal sai uma vez por Application em que houve revogação, com o `client_id` dela, e o esquema da linha não muda.

**A API de conta.** Mora em `accounts/api.py`, sobre `ScopedProtectedResourceMetadataView`, com o scope `conta`:

- `GET /api/conta/` e `PATCH /api/conta/`, este só para `first_name`, `last_name` e `nickname`, com o resto do corpo ignorado;
- `POST /api/conta/confirmacao/`, que reenvia a confirmação se a conta não está confirmada;
- `POST /api/conta/termos/`, que grava o aceite da versão vigente e recusa outra versão com `termos_desatualizados`;
- `GET /api/conta/confirmar/?t=`, sem autenticação, que confirma o e-mail e redireciona à SPA.

O `dispatch` da view de recurso é sobrescrito. Ele confere o Bearer pelo toolkit, uma vez, e então recusa com 403 e `codigo` no corpo o token de outra Application (`aplicacao_nao_autorizada`) e o de conta inativa (`conta_inativa`). Não é método de protocolo, e a N6 passa a nomeá-lo.

A API é isenta de CSRF por `csrf_exempt`, e a isenção depende de uma condição: **a API não aceita sessão**. Ela lê a conta só do token, e o cookie de sessão sozinho recebe 401. No dia em que a API aceitar sessão, a isenção vira falha.

O 400 tem sempre a forma `{"erros": {"<campo>": [{"codigo": ..., "mensagem": ...}]}}`, com `geral` para o que não é de campo. A `mensagem` sai em inglês, e a SPA exibe pelo `codigo`.

O `client_id` da SPA vem de `SPA_CLIENT_ID`, sem default, porque há uma Application por ambiente. A versão vigente dos termos é literal no código, `TERMOS_VERSAO_VIGENTE`, e começa em `1`. A falta de aceite não bloqueia nada no IdP; o bloqueio é da SPA.

**A confirmação de e-mail.** O link leva um token de `django.core.signing`, com salt próprio, prazo de sete dias, o `sub` e o resumo SHA-256 do e-mail. Ele vale enquanto o e-mail da conta for o mesmo e a conta estiver ativa. Expirado, adulterado, de e-mail trocado, de conta apagada ou de conta desativada, leva à SPA com `?email=invalido` sem mudar nada.

**Os e-mails.** São seis, em português e no fuso `America/Sao_Paulo`: boas-vindas e confirmação; aviso de troca de e-mail ao endereço antigo; redefinição de senha; senha trocada; conta desativada; conta apagada. A configuração vem das variáveis `EMAIL_*` e de `DEFAULT_FROM_EMAIL`, sem default; em desenvolvimento, o backend é o de console. Os links saem de `BASE_URL`, nunca do cabeçalho `Host`.

**O boot de produção.** Quando o host de `BASE_URL` não é local (`localhost`, `127.0.0.1`, `::1` ou um nome sob `.localhost`), o boot recusa, nomeando a variável, dois valores que estão certos em desenvolvimento e falham em silêncio em produção: `SPA_URL` em loopback, que mandaria cada pessoa à própria máquina, e um `EMAIL_BACKEND` do Django que não entrega (`console`, `dummy`, `locmem` ou `filebased`), que não enviaria nada e poria endereço e link no log ou no disco. O critério é o `BASE_URL`, e não o `DEBUG`, porque o `DEBUG` é falso em todo ambiente (ADR 0008). Com o issuer público, isso desfaz para `SPA_URL` a isenção de loopback.

O envio parte de `transaction.on_commit` e corre numa thread do processo. Assim, operação desfeita não envia, e SMTP (_Simple Mail Transfer Protocol_) lento não segura a resposta. A falha vai ao log operacional, sem o endereço. A suíte envia de forma síncrona.

Todo envio passa por um teto por destinatário por hora, contado no Redis com o resumo do endereço na chave. Acima dele o envio não sai, e a resposta não muda. São dois tetos, com contadores separados. Cadastro, "reenviar", "esqueci a senha" e a confirmação ao endereço novo, que qualquer um dispara contra um endereço alheio, têm o de cinco. Os avisos de senha trocada, de senha redefinida, de troca de e-mail, de desativação e de exclusão têm o de vinte. Sem teto, quem tem a sessão e a senha de alguém lotaria a caixa dela de avisos. Com o teto alto, suprimir um aviso exige vinte trocas na mesma hora, e cada uma delas já chega à caixa da dona.

**O idioma.** As páginas de conta, a tela de login e os e-mails saem em português por `translation.override("pt-br")`, com a resposta renderizada dentro do bloco. `LANGUAGE_CODE` continua `en-us`, e nem o protocolo nem a API mudam de idioma.

**Os tetos.** O limitador da ADR 0016 passa a cobrir, por origem e por minuto, `/accounts/registrar/`, `/accounts/password_reset/`, `/accounts/password_change/`, `/accounts/email/` e `/accounts/excluir/` a 60, como o login, e cada um dos quatro caminhos fixos da API a 120, como `/o/`. A confirmação da redefinição, `/accounts/reset/<uidb64>/<token>/`, **fica sem teto**, porque o caminho dela muda a cada link e o limitador compara por igualdade. O que a protege é o token de uso único e de uma hora. Os números são literais em `config/settings.py`.

**A trilha.** Amplia a 0013 com os sinais `conta_criada`, `email_confirmado`, `conta_editada`, `email_trocado`, `senha_trocada`, `recuperacao_pedida`, `senha_redefinida`, `termos_aceitos`, `conta_desativada` e `conta_apagada`, definidos em `accounts/sinais.py`, cada um com `event` igual ao próprio nome. Dois campos entram no esquema, cada um num evento só: `campos`, a lista dos nomes alterados em `conta_editada`, sem os valores; e `termos_versao`, em `termos_aceitos`. Nenhum endereço de e-mail entra.

O `sub` de toda linha passa a ser o UUID, igual à claim. As linhas antigas ficam como estão, com o `id` interno, que continua na conta para a correlação. O resumo do identificador passa a ser calculado em minúsculas: com o e-mail em minúsculas e a restrição sobre `Lower(email)`, já não há duas contas que só a caixa distinga, e duas caixas do mesmo endereço passam a dar o mesmo resumo.

**A ordem de implantação.** O IdP implanta primeiro, e a SPA depois. Implantada antes, a SPA pediria o scope `conta` e receberia `invalid_scope`, e "Criar conta" receberia 400.

**N4 e N6.** A N4 passa a dizer que as contas nascem no admin ou pelo cadastro e que a pessoa edita a própria conta pelas páginas do IdP e pela API de conta. A N6 passa a dizer que o `dispatch` da view de recurso da API é sobrescrito sem ser método de protocolo.

## Consequências

Positivas:

- A pessoa cria, lê, edita e exclui a própria conta e recupera a senha sem quem opera, e a senha continua só em telas do IdP.
- As RPs passam a receber um `sub` que não revela a sequência interna e não muda com o e-mail, e um `email_verified` que o IdP sustenta.
- As quatro pré-condições da 0023 entram juntas, e a claim vem por último: nasce falsa para toda conta.
- O cadastro entra pelo protocolo do toolkit, e as views de senha são as do Django. O código próprio fica na troca de e-mail, na exclusão e na API.
- Uma regra só, no `save()`, rege `updated_at`, a verificação do e-mail e o carimbo de senha em todos os caminhos de escrita.
- Quem esqueceu a senha, fora da equipe, deixa de depender de quem opera, e o bloqueio de quinze minutos do `axes` passa a ter saída pela própria pessoa.

Negativas:

- **O contrato público muda, e voltar atrás é quebra nos dois projetos.** As sessões abertas na implantação mostram erro na SPA até o reload, porque o `id_token` delas traz o `sub` antigo e o `userinfo` já traz o UUID. Quem correlacionou contas pelo `sub` antigo perde a correlação.
- **A única volta atrás permitida é para a frente, com imagem nova.** A migração que sorteia o UUID de cada conta é irreversível. Voltar a imagem antiga sobre o esquema novo, ou restaurar um dump anterior à implantação, cria uma terceira identidade por conta.
- **A trilha passa a ter duas populações de `sub`:** antes desta decisão, o `id` interno; depois, o UUID. A correlação entre elas passa pelo admin.
- **O carimbo de senha depende de `_password`, atributo privado do Django.** Um upgrade que o renomeie faz o carimbo parar, ou passar a marcar o re-hash, sem erro. A subida do Django relê esse ponto.
- **As regras do `save()` não alcançam `QuerySet.update()`.** Escrita em massa nesses campos fica fora delas, em silêncio.
- **O e-mail em thread se perde se o worker morrer durante o envio.** A pessoa tem "reenviar" e "pedir outro link"; não há fila durável.
- **Uma falha de SMTP só aparece no log operacional.** A pessoa vê a resposta de sucesso e não recebe nada.
- **A isenção de CSRF da API vale só enquanto ela não aceitar sessão.**
- **A confirmação da redefinição fica sem teto de requisição.**
- **O desafio leva `resource_metadata`** apontando para `/o/.well-known/oauth-protected-resource` no host do pedido, cujo `resource` é `/o` nesse mesmo host, e não a API. A SPA o ignora; um cliente estrito da RFC 9728 o recusaria.
- **A página de cadastro revela quem tem conta,** pelo erro de e-mail em uso. Fica aceito para a audiência pequena; a recuperação não revela nada.
- **A troca de e-mail vale na hora.** Um erro de digitação muda o login para um endereço que a pessoa não controla. O aviso ao endereço antigo sinaliza a troca, mas não a desfaz, e a saída é o admin.
- **A troca de e-mail apaga as linhas do `axes` do endereço antigo,** e o histórico de login daquele endereço se perde.
- **A mensagem de conta desativada confirma a desativação a quem acerta a senha.** Quem só sabe o e-mail vê o erro genérico.
- **Contas nunca confirmadas acumulam,** e quem cadastra o e-mail de outra pessoa ocupa o endereço até a dona usar "esqueci a senha".
- **Um antivírus que abra o link confirma a conta** sem clique humano.
- **Quem lê a caixa de entrada troca a senha** de conta fora da equipe e zera o bloqueio do `axes` da conta. O prazo de uma hora e o uso único reduzem a janela, e o aviso de senha trocada chega à mesma caixa.
- **O SMTP é de conta pessoal,** com limite diário de envio, e os tetos por destinatário não o protegem. O cadastro com endereços distintos dispara um e-mail por conta, e a 60 requisições por minuto uma origem só cria cerca de trinta contas por minuto. Isso esgota uma cota de algumas centenas por dia em menos de uma hora, e até o fim do dia nenhum link nem aviso sai. A saída é a fila ou o serviço transacional descartados nesta fase, ou um desafio no cadastro.
- **O cadastro é público na prática:** nada impede abrir a página direto. As defesas são o teto por origem, o teto por destinatário e o pedido de autorização válido que o `prompt=create` exige.
- **As variáveis novas sem default,** `EMAIL_*`, `DEFAULT_FROM_EMAIL` e `SPA_CLIENT_ID`, derrubam o boot e a suíte de todo clone cujo `.env` não as tenha. O `.env` de cada ambiente as recebe antes do merge.
- **`SPA_CLIENT_ID` errado não derruba nada:** a API recusa toda chamada com `aplicacao_nao_autorizada`.
- **O handler próprio do `axes` sobrescreve um método da biblioteca.** Uma subida que renomeie `reset_user_attempts`, ou passe a zerar por outro caminho, volta a apagar as falhas da origem no login, sem erro. A subida do `axes` relê esse ponto.
- **O login de uma conta tira da contagem de cada origem as falhas contra ela,** porque a linha de `AccessAttempt` guarda a conta e a origem juntas. Quem ataca só perde, assim, as falhas contra quem entrou.
- **O ensaio de produção sob nome público exige os valores de produção:** `SPA_URL` fora de loopback e um backend que entregue. O mesmo vale para todo clone cujo `PUBLIC_HOST` não esteja sob `.localhost`.
- **Trocar a versão dos termos não cabe numa implantação de cada lado.** Com o IdP antes, a SPA antiga envia a versão anterior e recebe `termos_desatualizados`; com a SPA antes, ela envia a nova a um IdP que ainda não a conhece. A primeira troca exige decisão nos dois projetos e uma janela em que o IdP aceite as duas versões.
- **Um pedido de recuperação contra conta da equipe não deixa linha na trilha;** só a linha de acesso do POST.
- **A decisão emenda quatro ADRs aceitas,** e quem lê a 0003, a 0013, a 0016 ou a 0029 precisa do índice para chegar aqui.

## Alternativas consideradas

- **Manter a 0023** — nenhuma superfície nova. Descartada: a pessoa continuaria sem recuperar a senha, e toda conta continuaria a ser trabalho de quem opera.
- **Telas de senha na SPA, sobre a API** — uma interface só. Descartada: a senha passaria a trafegar fora do IdP.
- **Trocar a chave primária por UUID** — o `sub` sairia direto da chave. Descartada: refaria as chaves estrangeiras do toolkit, do admin e do `axes`.
- **`ScopedProtectedResourceView` como vem** — sem `dispatch` próprio. Descartada: responde 403 sem desafio a toda falha, e uma RP não reconheceria o token vencido, que pede novo login. O desafio com `insufficient_scope` segue a RFC 6750 e serve a qualquer RP; a SPA não o trata à parte (ADR 0020 dela).
- **Django REST Framework** — serialização e erros prontos. Descartada: dependência nova para quatro endpoints.
- **`LANGUAGE_CODE` em `pt-br`** — tradução global. Descartada: o `error_description` do protocolo sairia acentuado.
- **Carimbo de senha em `set_password`** — sem atributo privado. Descartada: o re-hash do login marcaria troca de senha.
- **Comparar o e-mail sem caixa no backend de autenticação** — sem migração. Descartada: o `axes` contaria cada caixa à parte, e variar a caixa multiplicaria as tentativas contra uma conta.
- **Enviar dentro da requisição** — sem thread. Descartada: prenderia um dos três workers pelo tempo do SMTP.
- **Fila durável ou serviço de e-mail transacional** — sem perda de envio. Descartada nesta fase: um serviço a mais para operar.
- **Teto na confirmação da redefinição por expressão regular no limitador** — fecharia a lacuna. Descartada: o limitador compara por igualdade, e o token de uso único de uma hora já limita o que se ganha ali.
- **Token de confirmação em tabela** — revogável a qualquer momento. Descartada: o token assinado com o resumo do e-mail se invalida sozinho quando o e-mail muda.
- **Token de confirmação com o e-mail em claro** — conferência direta. Descartada: o endereço iria na URL, legível em todo log de borda.
- **Manter o zeramento do `axes` como vem** — nenhum código próprio. Descartada: com o cadastro aberto, entrar na própria conta apagaria as falhas da origem contra a vítima.
- **Avisos de segurança sem teto** — nenhum aviso suprimido. Descartada: o volume para uma caixa ficaria sem limite.
- **Teto global de envios por dia** — preservaria a cota do SMTP. Descartada nesta fase: troca a cota esgotada por um teto esgotado, com o mesmo efeito para quem espera um link.
- **`DEBUG` como sinal de produção** — a variável já existe. Descartada: o `DEBUG` é falso em todo ambiente (ADR 0008), e a guarda derrubaria o desenvolvimento e a suíte.
