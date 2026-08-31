# Passo 09 — Telas e estáticos

## Objetivo

Entregar as telas server-side onde a senha é digitada — login, home e consentimento — com
CSS servido de verdade.

## Depende de

- Passo 06, porque login exige um usuário existente no banco.
- Passo 07, porque o override de `oauth2_provider/authorize.html` só faz sentido com o DOT
  instalado, e a tela de consentimento é a que fecha o fluxo.

## Arquivos criados

- `templates/base.html` — layout mínimo compartilhado.
- `templates/registration/login.html` — **obrigatória**: a `LoginView` não traz template
  próprio.
- `templates/home.html` — quem está logado, e o formulário POST de logout.
- `templates/oauth2_provider/authorize.html` — override da tela de consentimento sobre
  `base.html`.
- `static/css/idp.css` — estilo mínimo de login, home e consentimento.
- `config/views.py` — **criado aqui**, com a view `home`. É o mesmo arquivo que recebe a
  view `health` no passo 10; nasce neste passo porque a `home` é a primeira view de borda
  do projeto.

## Arquivos modificados

- `config/urls.py` — rotas de login, logout e home.
- `config/settings.py` — `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`,
  `STATIC_ROOT`, `STORAGES` e a lista final de `MIDDLEWARE`.

## O que fazer

### Rotas de autenticação, uma a uma

Registrar `LoginView` em `/accounts/login/` e `LogoutView` em `/accounts/logout/`,
nomeadas.

**Não incluir `django.contrib.auth.urls` inteiro.** Ele publica quatro rotas de reset de
senha sem template, cada uma um 500 esperando um clique.

### `LOGIN_URL` por `reverse`

`LOGIN_URL` é resolvida por `reverse` do nome da rota de login, não escrita como string
literal. Era um contrato implícito entre settings e urls; agora é explícito.

Se ficar sem configuração, o Django usa `/accounts/login/` como default — e o sinal disso
aparece longe: `/o/authorize/` redireciona para uma URL que dá 404 e o fluxo morre no
primeiro salto, sem causa óbvia.

### Home como destino dos redirects

`LOGIN_REDIRECT_URL` e `LOGOUT_REDIRECT_URL` apontam para a view `home`.

Os defaults do Django apontam para `/accounts/profile/`, que **não existe neste projeto** e
seria mais um 404 — logo depois de um login bem-sucedido, que é o pior momento para um.

A view `home` mostra quem está logado: é como a sessão SSO fica visível sem precisar de
uma RP.

### Logout por POST

`LogoutView` só aceita POST desde o Django 5.0. O logout em `base.html` e `home.html` é
`<form method="post">` com `{% csrf_token %}`, **nunca** `<a href>`.

### Estáticos

Três coisas nas settings, mais o CSS referenciado por `base.html`. Uma tela de credencial
sem CSS é uma tela que ninguém confia.

**`STATIC_ROOT`** — o diretório para onde `collectstatic` copia, e de onde o WhiteNoise
serve. É o `staticfiles/` que o `.gitignore` do passo 01 já barra.

**`STORAGES`** — o dicionário que substituiu `STATICFILES_STORAGE`, **removido no Django
5.1**; configurar pela chave antiga não produz erro, só é ignorado silenciosamente:

```
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

A chave `default` precisa constar junto: declarar `STORAGES` substitui o dicionário
inteiro, e omitir `default` deixa o projeto sem backend de arquivos.

O backend com manifesto serve os estáticos com nome versionado e cabeçalho de cache longo.
A contrapartida vale para a **jornada de construção**: com `DEBUG=False`, o `runserver` não
serve estático por conta própria — quem serve é o WhiteNoise, a partir do `STATIC_ROOT`.
**Rodar `python manage.py collectstatic` antes de subir o `runserver`**, e de novo a cada
alteração no CSS. Na jornada de clonar-e-rodar, o entrypoint do passo 11 já faz isso.

### Lista final de `MIDDLEWARE`

O passo 04 estabeleceu a regra do CORS; aqui a lista fica completa, e é esta:

```
corsheaders.middleware.CorsMiddleware
django.middleware.security.SecurityMiddleware
whitenoise.middleware.WhiteNoiseMiddleware
django.contrib.sessions.middleware.SessionMiddleware
django.middleware.common.CommonMiddleware
django.middleware.csrf.CsrfViewMiddleware
django.contrib.auth.middleware.AuthenticationMiddleware
django.contrib.messages.middleware.MessageMiddleware
django.middleware.clickjacking.XFrameOptionsMiddleware
```

Duas posições não são arbitrárias:

- **`CorsMiddleware` em primeiro**, acima de `CommonMiddleware` e de qualquer outro capaz
  de gerar resposta — resposta emitida antes dele sai sem os cabeçalhos de CORS. Sem
  consumidor nesta fase, uma posição errada é **indetectável agora** e reaparece na fase do
  SPA como erro de CORS que ninguém associa a esta linha. Comentário no código, e registro
  no README (passo 12).
- **`WhiteNoiseMiddleware` logo depois do `SecurityMiddleware`**, para que o estático seja
  servido sem atravessar sessão, CSRF e autenticação.

## Proibições que incidem aqui

- **Não incluir `django.contrib.auth.urls` inteiro** — quatro rotas de reset sem template,
  cada uma um 500 esperando um clique.
- **Não fazer logout por link.** `LogoutView` só aceita POST desde o Django 5.0.
- **Não fazer override de view do DOT.** Override de **template** do DOT — a tela de
  consentimento — é permitido e esperado; override de view, não. Não é a mesma coisa e não
  tem o mesmo risco.
- **Não coletar senha em nenhum lugar que não seja a máquina de autenticação do Django** —
  a nossa `/accounts/login/` e o `/admin/login/`. Nenhuma RP, nenhum endpoint custom,
  nenhum formulário próprio recebe credencial.
- **Não criar `accounts/views.py`.** Login e logout são views prontas do
  `django.contrib.auth`; a `home` mora em `config/views.py`, junto com o roteamento de
  borda.

## Riscos e sinais

- **`LOGIN_URL` não configurada** — sinal: `/o/authorize/` redireciona para
  `/accounts/login/` (default do Django) e dá 404; o fluxo morre no primeiro salto, sem
  causa óbvia.
- **`LOGIN_REDIRECT_URL` no default** — sinal: 404 em `/accounts/profile/` logo após um
  login que funcionou.
- **Logout escrito como link** — sinal: 405 Method Not Allowed, ou uma página de logout que
  não desloga, conforme a versão.
- **`registration/login.html` ausente** — sinal: `TemplateDoesNotExist` na primeira visita
  a `/accounts/login/`. Falha ruidosa.
- **`CorsMiddleware` mal posicionado** — sinal: **nenhum nesta fase**.
- **`STATICFILES_STORAGE` no lugar de `STORAGES`** — sinal: nenhum erro; a configuração é
  ignorada e o WhiteNoise serve com o backend padrão. Removida no Django 5.1.
- **`collectstatic` não executado antes do `runserver`** — sinal: com o backend de
  manifesto, a página falha ao resolver o CSS, ou ele simplesmente não chega. Parece
  problema de template e é o manifesto ausente.

## Passo concluído quando

Depois de `python manage.py collectstatic`: `/accounts/login/` renderiza com CSS aplicado;
autenticar leva à `home`, que mostra o usuário logado; o botão de logout (POST) desloga e
volta à `home`; `/o/authorize/` com o client do passo 07 exibe a tela de consentimento com
o layout do projeto.
