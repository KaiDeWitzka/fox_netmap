# fox_netmap — Manual do utilizador

Versão 1.6.1 · novembro de 2026

> Idiomas: [Deutsch](02-benutzerhandbuch.md) · [English](02-benutzerhandbuch.en.md) · [Français](02-benutzerhandbuch.fr.md) · [Español](02-benutzerhandbuch.es.md) · [Italiano](02-benutzerhandbuch.it.md) · [Português](02-benutzerhandbuch.pt.md)

O fox_netmap é um mapa de rede interativo e pesquisável para a sua rede doméstica: até ~200
dispositivos em várias sub-redes/VLANs, com topologia («ligado a»), portas abertas, histórico,
alarmes e exportaciones (JSON/CSV/impressão PDF). Os dados são persistentes em SQLite; as
pesquisas (scans) são cíclicas ou manuais.

> As imagens do mapa `docs/screenshots/01-karte.svg` e `01-karte-dunkel.png` são capturas reais da
> v1.6.1 com dados de teste. As restantes imagens (`*.svg`) são ilustrações esquemáticas da interface
> (tema escuro); a estrutura e os elementos correspondem à aplicação.

**Índice**

1. [Início rápido](#1-início-rápido)
2. [A interface](#2-a-interface)
3. [Usar o mapa](#3-usar-o-mapa)
4. [Tabela](#4-tabela)
5. [Vista de Registo](#5-vista-de-registo)
6. [Detalhes do dispositivo](#6-detalhes-do-dispositivo)
7. [Pesquisa e filtros](#7-pesquisa-e-filtros)
8. [Definições](#8-definições)
9. [Incorporação (embed, só de leitura)](#9-incorporação-embed-só-de-leitura)
10. [Exportações](#10-exportações)
11. [Scanner e modelo de dados](#11-scanner-e-modelo-de-dados)
12. [Topologia («ligado a»)](#12-topologia-ligado-a)
13. [Vários locais e IPv6](#13-vários-locais-e-ipv6)
14. [Segurança](#14-segurança)
15. [Operação e deploy](#15-operação-e-deploy)
16. [API REST (resumo)](#16-api-rest-resumo)
17. [Resolução de problemas](#17-resolução-de-problemas)
18. [Acessibilidade](#18-acessibilidade)
19. [Glossário](#19-glossário)

---

## 1. Início rápido

**Requisitos:** Docker + Docker Compose no host (o scanner precisa de `network_mode: host`
para que ARP/ping funcionem na rede real).

```bash
git clone https://github.com/KaiDeWitzka/fox_netmap.git
cd fox_netmap
# opcional: criar .env, p. ex.
#   NETZ_SUBNETS=192.0.2.0/24,198.51.100.0/24
#   NETZ_FRITZ_URL=http://192.0.2.1:49000
#   NETZ_FRITZ_USER=…   NETZ_FRITZ_PASS=…
docker compose up -d --build
```

- Interface web: **http://localhost:8399**
- No primeiro arranque com `NETZ_AUTH_PASS` vazio, é gerada uma vez uma palavra-passe aleatória e guardada em
  `./data/initial-admin-password.txt` (legível só pelo proprietário, não nos logs). Login predefinido: `admin`.
  Depois, defina `NETZ_AUTH_PASS` – o ficheiro é apagado automaticamente.
- A primeira scan corre automaticamente após `NETZ_SCAN_INTERVAL` (900 s por defeito) ou de
  imediato via **▶ Scan** no cabeçalho.
- Os dados ficam no volume `./data` (SQLite `netmap.db`, log `netmap.log`, exportações) e
  sobrevivem a `docker compose up -d --build` (recriação). **`down -v` apaga os dados!**

> Após cada atualização de código, executar sempre `docker compose up -d --build`.

---

## 2. A interface

![Mapa v1.6.1, tema claro: grupos de sub-rede Casa e Remoto, gateway com anel, legenda aberta](screenshots/01-karte.svg)

![Mapa v1.6.1, tema escuro: árvore com repetidor, switch e dispositivos finais, legenda recolhida](screenshots/01-karte.svg)

Vista esquemática com painel de detalhes: [01-karte.svg](screenshots/01-karte.svg)

O cabeçalho está **organizado em duas linhas por tema** (cada grupo com uma pequena etiqueta):
Linha 1 **Vista**: logótipo com **número de versão** (de `/api/meta`, muda a cada release), navegação
**Mapa / Tabela / Registo**, pesquisa, filtros (categoria, estado, local), **Apenas online**, estado da varredura.
Linha 2: **Mapa** (agrupar sub-redes, seletor de esquema, ↺ esquema), **Ações** (**▶ Scan**, exportações
JSON/CSV, PDF + orientação, imprimir) e **App** (tema 🌗/☀, idioma, **⚙ Definições** como botão bem visível
com ícone + rótulo, terminar sessão).

Clicar num dispositivo (ou em ⚙) abre o painel direito com os separadores **Detalhes** e
**Definições**.

---

## 3. Usar o mapa

- **Zoom/pan:** a roda faz zoom, arrastar o fundo desloca. As posições dos dispositivos são
  guardadas (arrastar um nó é persistido via API).
- **Clicar num dispositivo:** destaque (spotlight) — o dispositivo e as suas ligações diretas são
  evidenciados, o resto escurece; os detalhes abrem à direita. Novo clique no fundo limpa.
- **«Apenas online»:** esconde dispositivos offline (guardado em localStorage).
- **«Agrupar sub-redes»:** os dispositivos são agrupados por sub-rede numa moldura (etiqueta
  `sub-rede · local (nº)`). As arestas mantêm-se entre dispositivos,
  também entre sub-redes.
 As molduras começam numa grelha (posição própria por sub-rede, filhos em anel à volta do centro do grupo) — sem sobreposição no mesmo ponto.
- **«Ocultar sem IP» (ativado por defeito):** os dispositivos sem endereço IP (ex.: conhecidos só por nome via TR-064, como `PC-76-84-…`) só aparecem no mapa ao desmarcar; na tabela ficam sempre visíveis.
- **Ocultar/mostrar filhos:** no painel de detalhes de um router/switch, um botão oculta todos os
  dispositivos ligados diretamente; o nó mostra então `(+N)`.
- **Esquema:** `auto` (predefinido) organiza o mapa em árvore pela topologia: Internet em cima, abaixo o
  router, switches/repetidores e dispositivos finais. Muitos dispositivos finais de um nó ficam numa grelha
  compacta por baixo; dispositivos sem pai ficam abaixo da árvore. Se houver posições guardadas para todos os
  dispositivos (arrastar), `auto` usa-as. Outros: `tree` (sempre árvore), `force` (física), `concentric`,
  `circle`, `grid`. **Repor** limpa as posições guardadas.
- **Nós (desde a v1.6.1):** círculo neutro com símbolo de categoria (símbolos Lucide, ver `THIRD_PARTY.md`)
  em vez de cores e emoji. Router, switch, repetidor/AP, servidor/NAS e Internet têm 40 px, os dispositivos
  finais 34 px. Nos clientes o mapa distingue portátil, tablet e consola pelo nome e pelo motivo de deteção.
- **Etiqueta em duas linhas:** linha 1 o nome (abreviado com «…» a partir de 20 caracteres; o nome completo
  aparece como dica ao passar o rato), linha 2 `IP · categoria`, com `(+N)` para filhos recolhidos e
  `· offline` para dispositivos offline. O nó Internet mostra `Internet` e `WAN <IP>` («?» sem TR-064).
  As duas linhas têm a mesma cor porque a biblioteca Cytoscape não suporta uma cor por linha.
- **Gateway como raiz:** só o dispositivo com o IP do gateway (TR-064 ou encaminhamento) recebe um anel
  forte na cor de destaque com anel exterior tracejado. Repetidores/AP têm uma borda clara.
- **Offline:** corpo e símbolo esbatidos, borda tracejada; a etiqueta continua legível e indica «offline»,
  logo a informação não depende da cor.
- **Arestas:** linhas retas, LAN contínua, WLAN tracejada, PLC pontilhada. As ligações entre locais
  diferentes são mais ténues. O acesso à Internet é um pouco mais forte.
- **Legenda:** em baixo à esquerda, recolhível (estado guardado no navegador, recolhida por omissão). Mostra
  todos os símbolos com a categoria, o anel do gateway, offline e os tipos de linha.
- **Limpeza automática:** etiquetas completas a partir de zoom ≥ 0,85 (abaixo só os hubs:
  router/switch/gateway/Internet), texto muito pequeno não é desenhado; acima de 25 dispositivos os grupos
  de sub-rede ativam-se sozinhos; «Só online» está ativo por omissão.
- Nós virtuais: **Internet** (com IP WAN), **Gateway** (se o gateway não estiver na lista) e **wlan:…** para
- **Internet ↔ roteador:** se o TR-064 lê o estado WAN (p. ex. da FRITZ!Box), o mapa liga o nó Internet ao roteador — pelo IP do gateway ou pelo endpoint TR-064 (hostname/IP como "fritz.box"), mesmo que o gateway não esteja na lista (`wan_endpoint` em `/api/meta`). Estado WAN ≠ "Connected" → nó Internet offline.
  dispositivos WLAN sem nó próprio.
- **Tabela e impressão:** a célula de categoria mostra o mesmo símbolo do mapa mais o texto. Os filtros e a
  seleção de categoria são listas nativas e mostram só texto.

---

## 4. Tabela

![Tabela](screenshots/02-tabelle.svg)

- **Reordenar colunas:** arrastar uma célula de cabeçalho — a ordem é guardada (localStorage).
- **Largura das colunas:** arrastar o divisor no cabeçalho — a largura é guardada.
- **Ordenar:** clicar num cabeçalho de coluna.
- **Alterar categoria em linha:** lista pendente na coluna de categoria.
- Host/IP com portas de interface web (80/8080/443/8443) são apresentados como ligações clicáveis
  (http + https, IPv6 entre `[…]`).
- **Coluna IPv6:** endereço v6 encontrado (correspondência MAC NDP, coluna "IPv6") diretamente na tabela, "–" se desconhecido.
- Dispositivos sem MAC (p. ex. IPs avulsos da sub-rede VPN) mostram «–» como MAC.

---

## 5. Vista de Registo

![Registo](screenshots/04-log.svg)

A vista **Registo** mostraOs níveis são coloridos (INFO azul, WARN âmbar, ERROR vermelho).  o `netmap.log` (rotativo, 1 MB × 3) com atualização automática a cada
5 s, filtro por nível e transferência do ficheiro completo. O mesmo é fornecido por `/api/logs` e
`/api/logs/download`.

---

## 6. Detalhes do dispositivo

À direita, separador **Detalhes**: categoria (editável), IP/**IPv6** (v6 via correspondência MAC NDP de `ip -6 neigh`, coluna `ip6` na BD/JSON/CSV), MAC/hostname/fabricante (OUI), estado,
sub-rede, local, fonte(s) da scan (p. ex. `arp,tr064`), «ligado a» (selecionável manualmente, vazio =
automático), portas abertas com nomes de serviço, nota, histórico (online/offline/portas) e eventos.
**Guardar** persiste categoria/nota/ligação manual.

---

## 7. Pesquisa e filtros

- **Pesquisa:** procura em hostname, IP, MAC, fabricante, nota (filtro em tempo real).
- **Filtros:** categoria, estado (online/offline), local — combináveis, aplicam-se ao mapa e à tabela.
- **Apenas online:** botão rápido no cabeçalho.

---

## 8. Definições

![Definições](screenshots/03-einstellungen.svg)

O formulário está **agrupado por tema** (Geral · Varredura · TR-064 · SNMP · Alarmes · Exportações/Locais/VPN · OUI).

Tudo o que for alterado aqui tem efeito **na próxima scan sem reiniciar o contentor** (os valores
env do compose continuam a ser os predefinidos para novas instalações; vazio = predefinido env).

| Campo | Equivalente env | Significado |
|---|---|---|
| Sub-redes | `NETZ_SUBNETS` | separadas por vírgulas, CIDR IPv4 e IPv6 (p. ex. `192.0.2.0/24, 2003:db8::/64`) |
| Intervalo / timeout da scan | `NETZ_SCAN_INTERVAL` / `NETZ_SCAN_TIMEOUT` | segundos; intervalo 30–86400 |
| Âmbito de portas / portas próprias | `NETZ_PORT_TOP` / `NETZ_PORTS` | top N (0 = todas) ou lista própria `80,443,…` |
| SNMP ativo / switches / community | `NETZ_SNMP_ENABLED` / `_SWITCHES` / `_COMMUNITY` | tabela CAM + LLDP dos switches (161/udp). Community sem valor predefinido (desde v1.6.0); sem community não há SNMP |
| TR-064 dispositivo principal / outros endpoints / utilizador / palavra-passe | `NETZ_FRITZ_URL` / `_URLS` / `_USER` / `_PASS` | URL ou `host:porta`; repetidores como endpoints extra; a palavra-passe é **write-only** (o GET nunca a devolve, vazia = inalterada) |
| URL de alarme (webhook/Gotify/Ntfy) | `NETZ_NOTIFY_*` | `http(s)://…`; os tokens ficam só em env (`NETZ_NOTIFY_*_TOKEN`) |
| Whitelist | `NETZ_ALARM_WHITELIST` | MAC/IP que não disparam o alarme «novo dispositivo» |
| Locais | `NETZ_SITES` | `Nome:sub-rede; …` p. ex. `Casa:192.0.2.0/24; Remoto:198.51.100.0/24` |
| Pool de endereços VPN | `NETZ_VPN_POOL` | Padrão `off` (sem suposição). `auto` = convenção FRITZ!: último octeto ≥ 201 na /24 do gateway; também CIDR (`10.8.0.0/24`) e intervalos (`192.0.2.201-192.0.2.254`), separados por vírgula |
| Histórico / retenção | `NETZ_HISTORY_HOURS` / `NETZ_DEVICE_RETENTION_DAYS` | histórico em horas; apagar dispositivos offline após N dias (0 = nunca) |
| Retenção de eventos | `NETZ_EVENT_RETENTION_DAYS` | apagar eventos após N dias, predefinição 90 (0 = nunca) |
| Auto-exportação / intervalo / pasta | `NETZ_AUTO_EXPORT` / `_INTERVAL_HOURS` / `_DIR` | JSON+CSV automáticos; intervalo em h (0 = após cada scan) |
| mDNS | `NETZ_MDNS_ENABLED` | hostnames via mDNS PTR como recurso (+ DNS-SD, v1.6.0) |
| Fallback OUI online / máx. consultas por scan / URL da API | `NETZ_OUI_ONLINE_ENABLED` / `_MAX` / `_URL` | fabricante de MACs desconhecidos procurado online (predefinição `https://api.macvendors.com`), **desativado por predefinição** (proteção de dados: os prefixos MAC são enviados a terceiros), em cache na BD |
| Login ativo | `NETZ_AUTH_ENABLED` | login por sessão on/off (utilizador/palavra-passe ficam só em env) |
| Tema / idioma | `NETZ_THEME` / `NETZ_LANG` | dark/light; de/en/fr/es/it/pt |

**Validação:** entradas inválidas (p. ex. `nao-e-ip` como sub-rede, porta `abc`, webhook sem
`https://`) são indicadas de imediato no frontend e rejeitadas pelo backend com HTTP 422.

---

## 9. Incorporação (embed, só de leitura)

Em Definições (**Tokens de incorporación**) crie um token — opcionalmente com expiração e filtros
(sub-redes/categorias). Incorporação via:

```html
<iframe src="https://netmap.example.com/embed?token=ABC123&lang=pt" width="100%" height="600"></iframe>
```

O token só é mostrado logo após a criação; apenas um hash é guardado (desde v1.6.0). Copie-o de imediato; depois a lista mostra só os 6 primeiros caracteres.

O embed é só de leitura (sem edição, sem definições), respeita os filtros do token e pode ser
ajustado com `?theme=dark|light` e `?lang=…`.

---

## 10. Exportações

- **JSON / CSV** no cabeçalho: exportação completa de todos os dispositivos (portas, histórico,
  ligações, locais, porta no nó pai (`link_port`, ex.: `LAN:2` / `AP:5G:0` da mesh FRITZ!Box) e
  indicador VPN (`vpn`)). CSV com separador à escolha (`/api/export/csv?sep=;`).
- **Imprimir → PDF:** vista otimizada para impressão (navegador «Guardar como PDF»).
- **Auto-exportação:**
- **PDF (no servidor):** botão **PDF** no cabeçalho — captura do mapa (PNG) + tabela de dispositivos como PDF real via `POST /api/export/pdf`  (também com token, filtros via parâmetros de consulta). Orientação retrato/paisagem selecionável ao lado do botão (guardada, `orientation` no body do POST); células longas quebram em vez de se sobrepor. ativar em Definições; escreve JSON+CSV após cada intervalo na pasta de
  exportação (relativa ao volume de dados, predefinida `exports`).

---

## 11. Scanner e modelo de dados

Dois serviços compose partilham o volume `./data`:

- `netmap` — web/API (porta 8399)
- `netmap-scanner` — `command: ["scanner"]`, `network_mode: host`, caps `NET_RAW`

**Fontes por scan (prioridade de junção):** varrimento ping + ARP (`/proc/net/arp`) + sonda TCP
(80/443/22/445/8080) para hosts bloqueados em ICMP (p. ex. sub-rede VPN) → TR-064 (dispositivo
principal + `NETZ_FRITZ_URLS`, junção por IP, repetidores via `tr064_parent`) → SNMP (CAM/LLDP)
→ mDNS/DNS. Conflitos de MAC: vence a MAC ARP. Duplicados (mesmo IP) são unidos no arranque.

**Ciclo:** a cada 900 s por defeito + acionamento manual (▶ Scan). Cada scan escreve o histórico
(`device_history`), eventos (`device_events`: online/offline/portas alteradas/novo) e dispara
alarmes (webhook/Gotify/Ntfy para novo dispositivo — exceto whitelist).

**Retenção:** dispositivos offline são apagados após `NETZ_DEVICE_RETENTION_DAYS` (30 por
 defeito, 0 = nunca).

**Categorias de dispositivos (desde v1.6.0):** Router, Repetidor/AP, Switch, Servidor/NAS, Cliente, Dispositivo
móvel, Multimédia, Impressora, Casa inteligente/IoT, Desconhecido. Cada sinal soma pontos e ganha o total mais alto:
gateway (100) > papel mesh FRITZ!Box (50) > modelo mDNS, p. ex. `iPhone14,2` (8) > nome de host (6) >
serviço mDNS, p. ex. `_ipp._tcp` (4) > fabricante OUI (3) > portas abertas (1–5) > endereço Wi-Fi privado (1).
A porta 53 sozinha já não torna um dispositivo router; SMB (445) sozinho conta como cliente. São ainda verificadas
algumas portas altas inequívocas (62078 iOS, 8009 Google Cast, 1400 Sonos, 8006 Proxmox), salvo lista própria em
`NETZ_PORTS`. O painel de detalhes mostra em **Detetado por** o sinal decisivo. Uma categoria manual prevalece
sempre. A pesquisa de serviços mDNS é um único pedido local (`NETZ_MDNS_ENABLED`).

---

## 12. Topologia («ligado a»)

Prioridade: **manual** (painel de detalhes) > **SNMP** (CAM+LLDP) > **Mesh FRITZ!Box** (TR-064) > **TR-064** (repetidores) >
**WLAN** (`wlan:…` se o TR-064 marcar o host como WLAN) > **gateway**.
O tipo de ligação `lan`/`wlan`/`plc` também é guardado. As arestas vão do pai para o dispositivo
(base do esquema em árvore). Se «ligado a» for um IP ou nome de host, é associado ao dispositivo
correspondente; só se não existir é criado um nó gateway virtual.

**Atribuir vários dispositivos (desde v1.6.0):** na tabela, marque os dispositivos na primeira coluna (a caixa do cabeçalho seleciona todos), escolha o router, switch ou repetidor em **Ligado a** e prima **Definir**. **auto** remove a atribuição manual. A alteração aplica-se a todos os dispositivos marcados ou a nenhum. Atribuições que criariam um ciclo são rejeitadas. As caixas funcionam com Tab e Espaço e o resultado é anunciado aos leitores de ecrã.

**Mesh FRITZ!Box (desde v1.6.0):** através do TR-064 (`X_AVM-DE_GetMeshListPath`), o fox_netmap lê a topologia
mesh do router: que dispositivo está ligado a que repetidor ou porta LAN, por LAN ou WLAN (banda). O painel de
detalhes mostra a porta, p. ex. `WLAN · 5 GHz` ou `LAN · LAN 1`. Segundo a AVM, o utilizador TR-064 precisa do direito
«App» ou «Phone». Desativar com `NETZ_FRITZ_MESH=false`. A lista só é carregada da rede local (caminho
relativo, sem redirecionamentos, máx. 5 MB); o ID de sessão nunca é registado.

**Heurística de switch:** um switch não gerível é invisível para o router. Se numa porta LAN houver vários
dispositivos e apenas um for um switch, os restantes são-lhe atribuídos. Com dois switches na mesma porta, tudo
fica no router; use então a atribuição manual.

---

## 13. Vários locais e IPv6

Exemplo (local VPN como na sua própria rede):

```env
NETZ_SUBNETS=192.0.2.0/24,198.51.100.0/24
NETZ_SITES=Casa:192.0.2.0/24; Remoto:198.51.100.0/24
```

→ filtro de local no cabeçalho, coluna «Local» na tabela, etiqueta de local nos grupos de
sub-redes, campo `site` nas exportações. A sub-rede remota é descoberta por sonda TCP mesmo que
ICMP esteja bloqueado.

IPv6: basta adicionar um CIDR v6 às sub-redes; descoberta em redes grandes via NDP + ping ao
gateway, mais varrimento em redes pequenas; gateway-v6 para a topologia; ligações web como
`[2003:db8::10]:8080`. Em redes grandes (ex.: /64) adicionalmente: ping multicast ff02::1, candidatos SLAAC/EUI-64 por MAC conhecida (ping6) e DNS AAAA por hostname — endereços v6 globais encontrados vão para `devices.ip6` (tabela, detalhes, exportação).

**Clientes VPN (ex.: FRITZ!Box IPSec/WireGuard .201/.202):** o TR-064 reporta ligações VPN com tipo de
interface «VPN» — esses dispositivos são marcados automaticamente como VPN (selo «VPN» na tabela e
no mapa, linha «Ligação VPN» no painel de detalhes, campo `vpn` em JSON/CSV/API). Os peers WireGuard
não aparecem no TR-064; para eles existe o **pool de endereços VPN** configurável (ex.: `auto`).
Clientes VPN não disparam alarme de «novo dispositivo», porque entram e saem com o túnel.

---

## 14. Segurança

- **Desde a v1.5.0:** hash PBKDF2-SHA256 com 600 000 iterações (hashes antigos são atualizados automaticamente no próximo login); sessões expiradas são removidas; cookie de sessão `Secure` com HTTPS (`NETZ_COOKIE_SECURE=auto|true|false`); pesquisa online do fabricante desativada por predefinição.
- **Desde a v1.4.1:** todos os dados de rede e de utilizador são codificados em HTML antes de serem mostrados (proteção XSS); cabeçalhos de segurança (CSP, `X-Frame-Options`, `Referrer-Policy: no-referrer`) em todas as respostas; bloqueio do login durante 15 minutos após 5 tentativas falhadas (IP+utilizador) ou 20 (IP) (HTTP 429).
- `NETZ_EMBED_ANCESTORS` define que sites podem incorporar `/embed` num iframe (predefinição `*`; recomendado: indicar os seus próprios domínios).
- Detalhes (em alemão): [conceito de segurança](03-sicherheit.md).
- Login por sessão (PBKDF2, cookie `fox_session`), ativo por defeito; `NETZ_AUTH_ENABLED=false` desativa-o.
- `NETZ_AUTH_USER`/`NETZ_AUTH_PASS` são só env; palavra-passe vazia → palavra-passe inicial aleatória em `./data/initial-admin-password.txt` (desde a v1.5.0 já não nos logs).
- `GET /api/settings` **não devolve segredos** (coberto por teste): nem `auth_pass`, nem
  `fritz_pass`, nem `notify_*_token`. A palavra-passe TR-064 é write-only nas Definições.
- Tokens de embed: com expiração, filtáveis, só de leitura; os caminhos de API protegidos por
  token são apenas `/api/devices`, `/api/device/…`, `/api/export/…`.
- O scanner corre com caps mínimas (`NET_RAW`), só de leitura para a rede.
- **Proteção de dados:** que dados são recolhidos, guardados e enviados para fora está descrito no [aviso de privacidade](04-datenschutz.md) (em alemão). Desde a v1.5.2 é possível excluir um dispositivo no painel de detalhes em **Excluir dispositivo**, com histórico, portas e eventos (com confirmação). Se ainda estiver na rede, reaparece na próxima varredura.

---

## 15. Operação e deploy

```bash
docker compose up -d --build          # após cada atualização (recria, os dados ficam em ./data)
docker compose logs -f netmap-scanner  # logs do scanner em direto
docker compose down                    # parar (os dados ficam)
docker compose down -v                 # ATENÇÃO: apaga ./data (BD, log, exportações)!
```

- Saúde: `GET /api/health` → `{ "status": "ok", "version": "1.5.2" }`
- Desde a v1.5.0 os contentores **já não correm como root**, mas com UID/GID `10001`. A interface web não tem capabilities e tem o sistema de ficheiros raiz só de leitura; o scanner mantém apenas `NET_RAW` para ping.
- No primeiro arranque após a atualização, o contentor atribui automaticamente os ficheiros existentes em `./data` ao UID 10001. No host, use `sudo` para os ler ou adicione o seu utilizador a um grupo com GID 10001.
- Healthcheck do Docker: `docker compose ps` mostra `healthy`/`unhealthy` (web: `/api/health`, scanner: ciclo de scan ativo).
- Volumes: `./data:/data` (SQLite WAL, `netmap.log` rotativo, `exports/`)
- Portas: `NETMAP_PORT` (host) → 8399 (contentor)
- Fuso horário: `TZ=Europe/Berlin`
- Releases: as tags SemVer `vX.Y.Z` passam por `release.yml` (ruff + pytest + testes UI) e criam
  automaticamente uma release no GitHub.
- Imagem pronta (desde a v1.5.1): `docker pull ghcr.io/kaidewitzka/fox_netmap:latest` (amd64/arm64). Enquanto o repositório for privado, execute antes `docker login ghcr.io` com um token (`read:packages`). No Compose substitua `build: .` por `image: ghcr.io/kaidewitzka/fox_netmap:<versão>`. Cada imagem é verificada com o Trivy; o SBOM e o relatório são anexados à release do GitHub.

---

## 16. API REST (resumo)

| Endpoint | Objetivo |
|---|---|
| `GET /api/health` | saúde + versão (público) |
| `GET /api/devices?q=&category=&status=&subnet=&site=` | lista de dispositivos, filtrável |
| `PATCH /api/device/{mac}` | editar categoria/nota/«ligado a»/posição |
| `DELETE /api/device/{mac}` | excluir dispositivo com histórico, portas e eventos (login necessário) |
| `GET /api/device/{mac}` | detalhes (portas/histórico/eventos) |
| `POST /api/scan` · `GET /api/scan/status` | iniciar scan / estado |
| `GET /api/settings` · `PATCH /api/settings` | ler definições (sem segredos) / alterar (422 se inválido) |
| `GET/POST /api/tokens` · `DELETE /api/tokens/{id}` | gerir tokens de embed |
| `POST /api/devices/connect` | atribuição múltipla: `{"macs": [...], "connected_to": "<MAC>"}`, `""` = auto |
| `GET /api/export/json` · `GET /api/export/csv?sep=,` | exportações |
| `GET /api/logs?lines=200&level=WARNING` · `GET /api/logs/download` | registo |
| `GET /api/meta` | IP WAN, gateway, versão, sub-redes (público) |
| `GET /api/sites` · `GET /api/categories` | locais / categorias (público) |
| `POST /api/layout/reset` | limpar posições de nós guardadas |

Auth: cookie de sessão após `POST /api/login`; token de embed em vez de sessão para os caminhos com token.

---

## 17. Resolução de problemas

| Sintoma | Causa / solução |
|---|---|
| «Demasiadas tentativas falhadas» no login | Bloqueio ativo (HTTP 429). Aguardar 15 minutos ou reiniciar o contentor (`docker compose restart netmap`). |
| O embed não aparece no iframe | `NETZ_EMBED_ANCESTORS` não inclui o site que incorpora. Adicionar o domínio e executar `docker compose up -d`. |
| Dispositivo em falta na sub-rede VPN | ICMP bloqueado → a sonda TCP entra automaticamente; visível no registo (`WARN … TCP probe ok`). Adiciona a sub-rede em Definições. |
| Erros TR-064 no registo | a passagem https→http é automática; verifica URL/utilizador/palavra-passe em Definições. As falhas SOAP são registadas em texto simples. |
| Switch sem vizinhos | TL-SG108E etc. sem SNMP → apenas porta 80; define a topologia manualmente no painel de detalhes. |
| Dispositivo «duplicado» | mesmo IP com dois MAC → vence a MAC ARP, o resto é desduplicado no arranque. |
| Dispositivos antigos desaparecem | retenção ativa (30 dias offline por defeito) — coloca `0` = nunca em Definições. |
| Mapa ilegível | ativa «Agrupar sub-redes» + oculta os filhos do router/switch + experimenta os esquemas `tree`/`grid`. |
| Login esquecido | define `NETZ_AUTH_PASS` no compose/.env e `docker compose up -d --build`. |
| Recomeçar do zero | `docker compose down -v && docker compose up -d --build` — apaga a BD! Guarda as exportações antes. |

O separador **Registo** + `docker compose logs netmap-scanner` mostram cada passo da scan.

---

## 18. Acessibilidade

- Navegação por teclado: Tab pelo cabeçalho/vistas, Enter ativa; anéis de foco visíveis.
- Contrastes verificados nos temas escuro/claro; o estado também é textual («online/offline»), não só cor.
- aria-labels em botões só de ícone, região live para mensagens de estado.
- O objetivo é a conformidade total com BITV 2.1 — feedback bem-vindo (issue no repo).
- **Reduzir movimento (desde a v1.5.2):** se «reduzir movimento» estiver ativo no sistema (`prefers-reduced-motion`), o fox_netmap não mostra animações nem transições; um scan em curso aparece como um ponto fixo com texto. Caso contrário o ponto pulsa só três vezes (menos de 5 segundos) e depois fica parado (WCAG 2.2.2, 2.3.3). O mapa é sempre construído sem animação.
- **Mapa (desde a v1.6.1):** as categorias reconhecem-se por símbolo e texto, não só pela cor (WCAG 1.4.1).
  Contrastes verificados nos dois temas: etiquetas pelo menos 4,5:1 (também offline), bordas e símbolos pelo
  menos 3:1 contra o fundo (WCAG 1.4.3, 1.4.11). A legenda é um elemento nativo `<details>` utilizável por
  teclado; os seus símbolos e os da tabela são decorativos (`alt=""`) porque o texto da categoria está ao
  lado. Os nomes abreviados leem-se por inteiro na dica, na tabela e no painel de detalhes. As transições
  (150 ms) são omitidas com «reduzir movimento».
- O estado do scan só é anunciado aos leitores de ecrã quando muda de facto.

---

## 19. Glossário

- **OUI** — identificação do fabricante pelos primeiros 3 bytes do MAC (BD local `app/data/oui_seed.txt`).
- **TR-064** — interface SOAP da AVM da FRITZ!Box (lista de hosts, IP WAN, clientes WLAN).
- **Tabela CAM** — tabela MAC-porta do switch via SNMP (Q-BRIDGE/BRIDGE-MIB).
- **LLDP** — descoberta de vizinhos via SNMP (LLDP-MIB), p. ex. `lldpRemChassisId`.
- **Retenção** — eliminação automática de dispositivos há muito tempo offline.
- **Destaque (spotlight)** — realce de um dispositivo + as suas ligações diretas no mapa.
- **Local** — um nome para uma sub-rede (`NETZ_SITES`), p. ex. «Remoto» para a rede VPN.

---

*Perguntas ou bugs? Abre uma issue em `KaiDeWitzka/fox_netmap` — os requisitos estão em
`docs/01-anforderungen.md`.*
