# Guia de teste no navegador — site de questões (Etapa 5F.11b / sessão 6)

Instruções para a IA que vai testar o site num navegador real (ex.: Claude in Chrome).

## Regras do teste

- **Não faça login** e não clique em "Entrar com Google". Tudo abaixo roda como visitante anônimo. Páginas que exigem login (`/conta`, histórico, "apagar minha conta") só devem ser checadas por **redirecionamento para `/entrar`**.
- Não dispare `alert`/`confirm` do navegador. Se aparecer um diálogo, pare e avise.
- Não altere dados. O site anônimo não grava nada.
- URL base: `http://localhost:8000` (ou a que o dono informar). Se não abrir, pare e pergunte.
- Para cada item, registre **OK / FALHA / N/A** e, em caso de falha, URL, o que viu, o que era esperado e um print. Abra o console (erros de JS) e a aba de rede (respostas 4xx/5xx inesperadas) durante todo o teste.
- Teste em **desktop (~1280 px)** e repita os itens marcados com 📱 em **mobile (~390 px de largura)**.
- Ao final, entregue o relatório no formato da última seção.

## 1. Home e navegação (`/`)

1. A home carrega sem erro no console e mostra a grade de matérias.
2. O total de questões da home aparece com ponto de milhar (ex.: `2.781`), nunca `2781`.
3. Nomes de matéria de cargo aparecem como "Conhecimentos específicos — <cargo>" (ex.: Estatístico, Médico Clínico), não como nome de cargo cru.
4. Todos os links do cabeçalho funcionam (Questões, Estatísticas, Simulado, Sobre). 📱 O botão ☰ abre e fecha o menu; ao abrir, `aria-expanded` vira `true` (cheque no inspetor).
5. O ícone da aba (favicon azul com "Q") aparece. `/favicon.svg` responde 200 e `/static/og.png` responde 200.
6. Código-fonte: `<link rel="canonical">`, `og:title`, `og:description`, `og:image`, `twitter:card`, `twitter:title` e `twitter:description` presentes.

## 2. Lista de questões (`/questoes`)

1. A lista carrega e mostra "N questões encontradas" com milhar com ponto. Cada card tem a barra cinza (posição · ID curto `Q` + 8 hex · matéria ▸ assunto).
2. **Painel no topo:** palavra-chave, dropdowns Matéria/Assunto/Subassunto/Banca/Órgão e "Mostrar filtro avançado" (Ano, Concurso, Cargo, Nível, Conhecimento + linhas "Excluir questões" e "Questões com"). A escolha simples/avançado é lembrada; com filtro avançado ativo, o avançado abre sozinho.
3. **Dropdown:** abre, a busca rápida restringe a lista, marcar mostra "N selecionado(s)" e o chip em "Filtrar por:". Esc ou clique fora fecha.
4. **Nada busca antes do Filtrar:** marcar, desmarcar, remover chip ou mudar checkbox **não** troca a lista nem a URL. Ao fechar o dropdown, só os números das outras facetas mudam (recontagem em `/questoes/facetas`).
5. **Filtrar** aplica tudo: a lista muda sem recarregar a página (HTMX), a URL leva os filtros (ex.: `orgao=PF&anuladas=excluir`) e a página volta para 1. Conferido: PF = 1.131; PF + excluir anuladas = 1.092.
6. **Palavra-chave:** sem acento acha acentuado; várias palavras valem em E. Um ID curto (ex.: `q564333ae`, minúsculas aceitas) abre a própria questão.
7. "Já resolvidas" e "Que errei" ficam desabilitados sem login (dica "Entre para usar"). Com login, filtram pelo histórico.
8. **Paginação:** páginas 2, 3 e a última; `?pagina=999` cai na última; `?pagina=0` e `?pagina=-1` não quebram. A paginação usa os filtros aplicados, não o form pendente.
9. Voltar/avançar do navegador restaura a lista, o total e os checkboxes da URL (página inteira, não só o fragmento).
10. Sem JS: os chips aparecem (via `<noscript>`) com o link que tira só aquele filtro.
11. 📱 390 px: dropdowns em coluna, painel do dropdown cabe na tela, sem rolagem horizontal; "Questões parecidas" pode quebrar em 2 linhas (aceito).
12. Compartilhamento: copie a URL filtrada, abra em nova aba e confirme o mesmo resultado.

## 3. Resolver uma questão (card e página canônica)

1. No card, abra o texto-base/figuras (`<details>`): carrega sob demanda, sem erro.
2. Marque **Certo** ou **Errado** e confirme. Deve mostrar a correção (acerto/erro e gabarito) sem recarregar a página.
3. Resolva a **mesma** questão duas vezes (marcando de novo): o contador de acertos da sessão **não** pode contar duas vezes.
4. Resolva ~5 questões variando acerto/erro e confira se o contador de acertos da sessão no cabeçalho bate com o número de acertos reais.
5. Questão **anulada** (se achar uma): não deve contar como acerto/erro.
6. Página canônica `/q/<concurso>/<caderno>/<numero>` (clique no título/ícone de link do card): carrega, tem meta description, mostra "Fonte: CEBRASPE", e o botão de resolver funciona.
7. Seção "questões parecidas" (se existir) carrega e os links funcionam.
8. Recarregue a página com `localStorage` limpo (DevTools → Application → Clear site data): nada deve quebrar.

## 4. Painel de matéria (`/materias/<id>`)

Abra pela grade da home. Teste com **LÍNGUA PORTUGUESA** e com uma matéria de cargo (ex.: Estatístico).

1. LP mostra **139** como total de questões (válidas distintas). Anote se aparecer 178 ou 2.xxx em algum lugar para LP.
2. O tooltip de "Questões da matéria" é legível e diz que anuladas não contam e que a repetida entre cadernos conta uma vez. Os 4 KPIs têm rótulos claros.
3. Ranking "O que mais cai": barras proporcionais, números com milhar com ponto, links levam à lista filtrada (`/questoes?no_id=...`) e a lista abre com o filtro aplicado.
4. A frase de reconciliação sob o ranking é coerente (soma dos subassuntos × total) e **não** diz "Anuladas ficam fora" ao lado de um "+ N anuladas".
5. Filtros de nível e cargo mudam os números; "Resolver questões desta matéria" leva à lista filtrada.
6. Matéria de cargo mostra o título "Conhecimentos específicos — <cargo>".
7. ID inexistente (`/materias/nao-existe`) → 404 com layout do site e texto **"Matéria não encontrada"**.

## 5. Estatísticas

### `/estatisticas` (o que mais cai)
1. Carrega; abas de estatística navegáveis. Filtros de nível/cargo/concurso funcionam e atualizam a tabela/ranking.
2. Percentuais com formato brasileiro (vírgula decimal) e milhares com ponto. Nada de `0.123456` cru nem `%` duplicado.
3. Links levam à lista filtrada correta.

### `/estatisticas/edital`
1. Escolha concurso e cargo; a tabela de itens de edital carrega. O select de cargo reage ao concurso escolhido.
2. Contagens com milhar com ponto; rótulos sem slug cru.

### `/estatisticas/edital-vs-prova`
1. Escolha **PF_25_ADM**, cargo 1: esperado ≈ **139 nós cobrados, 125 nunca cobrados, 0 fora do edital** (anote qualquer diferença).
2. Percentuais calculados corretamente (ex.: `acerto` em porcentagem sensata, entre 0 e 100) — a precedência do filtro já foi um bug.
3. Teste o cargo **Contador** (CARGO 3 da PF): não deve aparecer nenhum "cobrado fora do edital".
4. Cargo inexistente (`?cargo_numero=abc` ou número que não existe) → 404 com texto **"Cargo não encontrado"**, sem erro 500.

## 6. Simulado anônimo (`/simulado`)

1. A página lista concursos (rótulo "PF 2025") e, ao escolher, o select de cargo é preenchido. O `value` enviado é o **slug**; o botão "Iniciar" abre a prova do concurso/cargo certo (não 404).
2. A prova abre na ordem original (básico, depois específico), com cronômetro correndo.
3. Marque algumas respostas, recarregue a página: o **rascunho** deve ser restaurado (localStorage).
4. Envie a prova (marque tudo "Certo" no PF_25_ADM cargo 1): esperado **58 − 60 = −2 de 118** (anuladas fora da nota e do máximo). Anote o resultado exato.
5. A página de resultado mostra placar por matéria, as discursivas (tema/quesitos, padrão de resposta só aqui) e um aviso de itens ilegíveis quando aplicável (PF cargo 5).
6. Após o resultado, o rascunho foi apagado; voltar à prova não reaparece com marcações antigas.
7. Se o envio falhar (simule offline no DevTools antes de enviar): as marcações **não podem sumir**.
8. Abra `/simulado/999999999` → 404 com texto **"Simulado não encontrado"**. Abra `/simulado/prova?concurso=XXX&cargo_numero=1` → "Prova não encontrada".
9. Anônimo em `/simulado/<id>/revisar` ou `/conta` → redireciona para `/entrar` (não teste o login em si).
10. 📱 A prova e o cronômetro são utilizáveis no celular.

## 7. Busca

1. Busque um termo comum (ex.: "crase"): resultados aparecem, com contagem em milhar com ponto.
2. Busque algo sem resultado (ex.: `zzzzqqq`): deve mostrar **estado vazio** amigável, não página em branco.
3. Termo com acento e em caixa diferente retorna o mesmo.

## 8. Erros (404/405) e API

1. `/nao-existe` (aceitando HTML) → página 404 com layout do site, botões "Voltar" e "Sobre", texto "Erro 404".
2. `/api/v1/nao-existe` → **JSON** (`{"detail": ...}`), não HTML.
3. `/api/v1/questoes?pagina=999` e `/api/v1/materias` respondem JSON válido; `/api/v1/materias` mostra LP com `total_questoes` = 139.
4. `/docs` (Swagger) abre e lista as tags documentadas; `/api/v1/saude` responde 200.
5. Um `POST` em uma página só-GET (ex.: via console `fetch('/sobre',{method:'POST'})`) → 405 com "Erro 405" e cabeçalho `Allow`.

## 9. Sobre (`/sobre`)

1. Carrega com crédito "Fonte: CEBRASPE" e o canal de remoção com o e-mail **athosroque@hotmail.com**.
2. O link de e-mail (`mailto:`) está correto.

## 10. Acessibilidade e robustez

1. Navegação só por teclado: Tab percorre filtros, botões e menu; foco visível; Enter/Espaço aciona o botão ☰ e o Certo/Errado.
2. Imagens têm `alt` (figuras das questões incluídas); contraste legível.
3. Zoom de 200%: layout continua utilizável.
4. Bloqueie `localStorage` (janela anônima com cookies/dados de sites bloqueados) e navegue pela home, lista e resolução de uma questão: nada pode quebrar com erro no console.
5. Console: **zero** erros de JS em todas as páginas acima. Lista de requisições com 4xx/5xx inesperadas (além dos 404 propositais).

## 11. Itens abertos que a IA deve só observar (não bloqueiam)

- Números ao lado dos nós da árvore de filtros × contador "N questões encontradas" (anote divergências).
- Matérias cujos nomes aparecem em minúscula ou com grafia estranha (ex.: "NOÇOES"); liste os exemplos encontrados.
- Qualquer lugar com 178 questões para LP, ou `|title` com siglas quebradas (SOAP, JSON, REST).

## Formato do relatório final

Tabela com colunas: **Seção/item · Resultado (OK/FALHA/N/A) · URL · Observação**.
Depois, uma lista **"Falhas"** ordenada por gravidade (bloqueia deploy / incômodo / cosmético), cada uma com passos para reproduzir e print, e uma lista **"Observações"** (seção 11). Não corrija nada; só reporte.
