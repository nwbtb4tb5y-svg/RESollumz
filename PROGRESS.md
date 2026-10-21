# RESollumz — andamento

## Status geral

**Fases 0–4 concluídas. Fase 5 — validação e empacotamento local — concluída; publicação no GitHub ainda não realizada.**

## Fase 0 — análise do projeto

**Status:** análise e decisões concluídas.

### Estado do workspace

- A raiz é uma fork do add-on Sollumz, atualmente na branch `main`, commit-base `e124bdd`.
- A identidade ainda é majoritariamente Sollumz (`bl_info`, nome e IDs do manifesto).
- `RECodeWalker/` é um submódulo fixado no commit `485d56bec00262ed7fa472261cce7bbc6202b96e`, usado como fonte de `CodeWalker.Core` pelo CWBridge.

### Sollumz: arquitetura observada

- O entry point `__init__.py` executa `register()`/`unregister()`. `auto_load.py` importa os submódulos e registra/desregistra classes e hooks dos módulos.
- O add-on é hoje uma extensão com `blender_manifest.toml` (`id = "sollumz_dev"`, mínimo Blender 4.2), mas também mantém `bl_info` para instalação legada. Preferências usam `__package__`; o namespace não deve ser presumido como um nome simples.
- Dependências: `szio` é obrigatória e marcada segura para reload; `pymateria` é opcional e não é segura para reload. Os pacotes são montados em `sys.path` em diretório compartilhado do add-on; a instalação já evita remover diretamente wheels nativas possivelmente carregadas.
- O guard `check_single_sollumz_instance()` bloqueia outra instância quando `bpy.types.Object.sollum_type` já existe. A troca de versão em processo não pode ser tratada como simples remoção de `sys.modules`: classes e propriedades do Blender, handlers, timers, keymaps e bibliotecas nativas também precisam ser considerados.

### Sollumz: releases oficiais e compatibilidade

Foram enumeradas e inspecionadas as 21 tags de release oficiais disponíveis, incluindo seus arquivos-fonte gerados pelo GitHub. Os marcos estruturais observados:

| Releases | Estrutura/formato | Blender e observações |
|---|---|---|
| `legacy`, `v2.0.0`–`v2.4.2` | Add-on legado, `cwxml` local (14–15 arquivos); sem `blender_manifest.toml`. | `bl_info` normalmente indica Blender 4.0, com exceções `v2.0.0`, `v2.1.0`, `v2.2.0` e `v2.3.1-maintenance-3.6`, que indicam 3.5.1. |
| `v2.5.0`–`v2.7.2` | Manifesto de extensão presente; `cwxml` continua local (15–17 arquivos). | Manifesto exige Blender 4.2; `bl_info` ainda diz 4.0. |
| `v2.8.0`–`v2.9.0` | Migração estrutural: `cwxml` deixa de estar no add-on e o fluxo passa a usar `szio`; a compatibilidade XML depende também dessa dependência. | Manifesto exige Blender 4.2. |

Tags examinadas: `legacy`, `v2.0.0`, `v2.1.0`, `v2.2.0`, `v2.3.0`, `v2.3.1`, `v2.3.1-maintenance-3.6`, `v2.4.0`, `v2.4.1`, `v2.4.2`, `v2.5.0`, `v2.6.0`, `v2.6.1`, `v2.7.0`, `v2.7.1`, `v2.7.2`, `v2.8.0`, `v2.8.1`, `v2.8.2`, `v2.8.3` e `v2.9.0`.

Os IDs de operador também evoluíram: quatro IDs usados na versão mais recente estão todos presentes em `v2.9.0`, dois em `v2.5.0`–`v2.8.3` e nenhum nas versões anteriores. Portanto, um adaptador não deve depender apenas de nomes de operadores nem do número da versão: precisa detectar capacidades e validar os formatos efetivamente disponíveis.

O metadado `bl_info["version"]` também não é fonte confiável em todos os tags (por exemplo, `legacy` e `v2.0.0` ainda reportam `0.4.0`); a tag do release deve ser a identidade canônica do pacote instalado.

Todos os releases enumerados têm um asset ZIP instalável (`Sollumz.zip`, salvo o asset `Sollumz-legacy.zip`); a API do GitHub fornece digest SHA-256 para os releases mais recentes, mas não para todos os antigos. Os arquivos-fonte podem ser usados como fallback, mas não foi necessário para os releases consultados.

### CodeWalker: APIs confirmadas

- `YdrFile`, `YftFile`, `YddFile` e `YtdFile` aceitam bytes com `Load(byte[])` para recursos soltos; a conversão binária é feita com `Save()`.
- A geração de XML está nas classes `YdrXml.GetXml`, `YftXml.GetXml`, `YddXml.GetXml` e `YtdXml.GetXml`. O caminho inverso está em `XmlYdr.GetYdr`, `XmlYft.GetYft`, `XmlYdd.GetYdd` e `XmlYtd.GetYtd`.
- Esses carregadores de bytes chamam `RpfFile.LoadResourceFile`; não exigem abrir a interface ou montar RPFs para arquivos de recurso soltos. `RpfManager.IsGen9` é estado estático usado para escolher a geração/formato e precisa ser configurado pelo bridge.
- O XML de YTD escreve recursos DDS por `TextureDictionary.WriteXmlNode`; o código de textura usa `DDSIO.GetDDSFile` e grava os bytes. A conversão posterior para PNG não foi localizada como parte desse fluxo.
- `CodeWalker.Core` mira `netstandard2.0` e depende de SharpDX; os apps WinForms/WPF miram `net48`. O ambiente atual tem runtimes .NET 8/9, mas não tem SDK .NET instalado, então ainda não é possível validar um bridge compilando-o aqui.

### Funcionalidades já existentes relacionadas a C/D

- O importador YTD atual entende `.ytd` e `.ytd.xml`, acompanha o par base/`+hi`, carrega texturas embutidas e pode empacotá-las no `.blend`.
- `lookup_texture_file()` procura DDS ao lado do asset e, quando habilitado, nos diretórios compartilhados configurados pelo usuário.
- O operador `sollumz.txd_find_missing` remapeia imagens quebradas usando texturas de YTDs já importados na cena.
- Isso não equivale ao recurso pedido: não localiza/extrai automaticamente um YTD para um modelo selecionado, não associa diretamente suas texturas aos samplers do material do modelo e não indexa YTDs em pastas. A extensão deve reutilizar o fluxo existente em vez de duplicá-lo.

### Riscos e direção técnica preliminar

1. **Identidade/escopo:** foi decidido criar um loader RESollumz independente e manter o código Sollumz atual como base/compatibilidade, sem convertê-lo no loader.
2. **Troca de versão:** o hot-swap não é confiável como mecanismo genérico, devido a registros do Blender, estado de arquivos `.blend` e dependências nativas. Será tentado somente para combinações verificadas; qualquer dependência nativa já carregada ou limpeza incompleta deve gravar a seleção e exigir reinício. Nunca tentar descarregar DLL/PYD em uso.
3. **Isolamento de dependências:** cada versão precisa de caminho de dependências próprio, evitando o `site-packages` compartilhado que a instalação atual utiliza. Downloads devem ser consentidos, validados (hash quando publicado e caminhos ZIP seguros) e só registrados como ativos após extração íntegra.
4. **CWBridge:** a solução é console C# sobre `CodeWalker.Core`, mantendo stdout JSON e mensagens de erro/códigos de saída previsíveis. O build do bridge e a conversão de recursos soltos foram validados na Fase 2; round-trip de arquivos representativos e compatibilidade do XML por release ainda precisam de testes. Chamadas longas devem ficar fora da thread principal do Blender; acesso a `bpy` permanece na thread principal.
5. **Compatibilidade:** a API do Sollumz mudou de XML local para `szio`, assim como os operadores. XML pode ser o contrato entre o bridge e o add-on, mas precisa de testes de round-trip por tipo e por versão; não é garantia por si só de compatibilidade do XML entre todos os releases.

### Decisões registradas e validações para as próximas fases

- **Arquitetura escolhida:** loader RESollumz independente; o código Sollumz atual permanece como base/compatibilidade.
- **Blender alvo:** 4.2 LTS ou mais recente.
- **Troca de versão:** tentar hot-swap quando possível e pedir reinício como fallback. O hot-swap será limitado a combinações verificadas; dependências nativas já carregadas, estado de registro incerto ou versões não testadas devem gravar a seleção e exigir reinício.
- A compatibilidade do XML por release do Sollumz continua precisando de testes específicos para cada release.

## Fase 1 — loader de releases oficiais

**Status:** implementada; testes unitários e smoke tests reais de registro passaram.

O add-on independente `resollumz_loader/` lista releases oficiais do Sollumz, baixa e instala uma versão escolhida sob demanda, valida o SHA-256 quando publicado e extrai o ZIP com proteção contra caminhos inseguros. As versões ficam lado a lado, em namespaces Python privados e com diretórios de dependências separados. O catálogo é armazenado localmente para consulta offline; rede e token opcional do GitHub são tratados sem gravar credenciais nas preferências.

O loader registra suas próprias preferências e cria uma entrada de preferências para cada namespace gerenciado antes de registrar o Sollumz. Isso é necessário para releases que consultam `AddonPreferences` durante `register()`. Os hooks de `known_paths` e `dependencies` são reaplicados após a atualização de módulos feita pelo Blender, garantindo que o `site-packages` e o `requirements.txt` de cada versão apontem para o diretório isolado correto. Releases antigos que não têm `dependencies.py` continuam suportados.

Para evitar uma desativação incompleta de classes, propriedades e bibliotecas nativas, a versão selecionada é ativada imediatamente apenas quando não há outra versão gerenciada ativa. Para trocar uma versão já carregada, a seleção é salva para o próximo início do Blender; conflitos com uma instalação Sollumz comum são reportados, não desativados à força.

### Validação da Fase 1

- 6 testes unitários passaram: catálogo, URLs oficiais, ordenação semântica, layouts de ZIP, isolamento de dependências, validação de hash, rejeição de path traversal e remoção de instalação gerenciada.
- `compileall` e `git diff --check` passaram.
- No Blender 5.2.2, os releases oficiais `v2.7.2`, `v2.8.0` e `v2.9.0` foram instalados para o smoke test e cada um registrou e desregistrou com sucesso em processo próprio.
- Os caminhos de dados/dependências isolados foram verificados nos releases `v2.8.0` e `v2.9.0`; o release `v2.7.2`, sem gerenciador de dependências, também registrou e desregistrou.
- O registro das preferências do próprio loader foi testado no Blender 5.2.2.

### Limites conhecidos

- O smoke test real foi feito no Blender 5.2.2; Blender 4.2+ é o alvo declarado, mas a versão mínima ainda precisa de validação manual.
- A instalação pelo fluxo visual do Blender, as permissões de rede e a atualização do catálogo devem ser verificadas manualmente em uma instalação limpa.
- O hot-swap entre versões não é tentado: o loader exige reinício para trocar uma versão que já está ativa.
- A integração com CodeWalker/CWBridge e as funcionalidades específicas da fork RESollumz permanecem fora do escopo desta fase.

## Fase 2 — CWBridge

**Status:** implementada; build e smoke test de round-trip passaram.

Criado `cwbridge/`, um console .NET 8 que referencia apenas o projeto `CodeWalker.Core` do clone `RECodeWalker/`. O protocolo recebe um objeto JSON por stdin e retorna uma única resposta JSON por stdout; diagnóstico de exceções segue para stderr. Suporta conversão nos dois sentidos de recursos soltos `.ydr`, `.yft`, `.ydd` e `.ytd`, com seleção explícita da geração Gen9. No export XML, texturas DDS podem ser gravadas ao lado do XML; no import, os DDS referenciados são resolvidos a partir da pasta do XML. O bridge não monta RPFs nem depende de caminhos instalados do jogo.

Arquivos e instruções:

- Projeto e protocolo: [cwbridge/README.md](./cwbridge/README.md)
- Implementação: `cwbridge/Program.cs`

### Validação da Fase 2

- `dotnet build cwbridge\CWBridge.csproj --configuration Release`: passou, sem warnings ou erros, incluindo o build de `CodeWalker.Core`.
- Round-trip no protocolo real: XML mínimo YTD → `.ytd` → XML → `.ytd`, todos os subprocessos retornaram sucesso JSON.
- Conversões YTD nos modos Gen8 e Gen9 passaram; entradas JSON inválidas e formatos não suportados retornaram erro JSON estruturado e código de saída `1`.
- O SDK .NET 8 usado na validação foi instalado apenas em pasta temporária local, não como dependência global.

### Limites conhecidos

- O teste funcional foi um YTD mínimo; conversões com modelos reais, texturas DDS, YFT/YDD e Gen9 de outros tipos ainda precisam de fixtures/testes de integração.
- O bridge é framework-dependent e requer o runtime .NET 8 na máquina que o executar. A publicação/binário que será distribuído com o add-on deve ser definida na fase de integração Python.
- Conversões com arquivos reais e compatibilidade do XML com cada release Sollumz ainda precisam de fixtures/testes de integração.

## Fase 3 — integração do CWBridge e localização de texturas YTD

**Status:** integração e interface implementadas; operador e indexação de YTDs reais validados no Blender 5.2.2 (Fase 4).

Foi adicionado um cliente Python para executar o bridge configurado pelo usuário, validar respostas JSON, propagar erros estruturados e aplicar timeout. Em Sollumz Preferences > Import/Export, o campo **CWBridge Executable** aceita o executável publicado ou o `CWBridge.dll`.

O painel de Texture Dictionaries agora oferece **Find Textures in YTD Folder**. Com um modelo selecionado, a operação indexa recursivamente `.ytd` usando o CWBridge, exporta os DDS para um cache persistente por arquivo de origem e relaciona texturas com nomes iguais aos samplers Sollumz em falta. Prefere dicionários com o nome do modelo e variantes `+hi`; nomes ambíguos são ignorados, imagens existentes/empacotadas são preservadas, e a seleção Gen8/Gen9 é explícita. O processo de leitura e conversão acontece em uma thread de fundo; as imagens Blender só são carregadas na thread principal.

Erros de conversão individuais são reportados e não impedem indexar outros YTDs. O cache é invalidado quando muda o tamanho ou o horário de modificação do YTD. O CodeWalker também valida os nomes das texturas antes de criar arquivos DDS.

### Validação da Fase 3

- `py -3.15 -m unittest discover -s cwbridge\tests -v`: 7 testes passaram, cobrindo respostas e erros do bridge, cache, seleção por nome e tratamento de ambiguidades.
- `py -3.15 -m compileall -q cwbridge ytd\operators\txd.py ytd\ui.py sollumz_preferences.py` e `git diff --check`: passaram.
- O build Release do CWBridge e `dotnet format --verify-no-changes` passaram.
- O fluxo real de indexação extraiu `test_image.dds` dos fixtures YTD Gen8 e Gen9, sem erros; o Blender 5.2.2 carregou ambos os DDS com dimensões 64 × 64.
- O smoke test completo do operador e a correção de registro estão documentados na Fase 4.

### Limites conhecidos

- O índice lê os YTDs em uma pasta escolhida a cada operação; o cache otimiza a extração, mas não mantém um catálogo de diretórios configurados para atualização automática.
- A validação interativa da interface e testes em versões Blender 4.2+ ainda faltam.
- O executável não é incluído no repositório. `cwbridge\publish.ps1` o publica localmente e copia os avisos de terceiros para o pacote.

## Fase 4 — validação end-to-end da integração YTD

**Status:** concluída no Blender 5.2.2.

O smoke test com `szio` revelou que `auto_load.py` também descobria o pacote independente `resollumz_loader/` e tentava registrar suas classes duas vezes durante o registro do add-on. A descoberta automática agora ignora esse pacote separado.

### Validação da Fase 4

- `szio==1.4.0.dev2` foi instalado com hash verificado numa pasta temporária isolada, sem alterar dependências persistentes do Blender.
- O add-on registrou com as dependências obrigatórias disponíveis; as propriedades de sampler e o operador **Find Textures in YTD Folder** ficaram registrados.
- O operador foi executado até o fim, incluindo thread de indexação, tratamento do evento de conclusão, carregamento do DDS e vínculo ao sampler ausente, usando os YTDs reais Gen8 e Gen9 de `tests/assets`.
- Nos dois modos, foi vinculado `test_image.dds` com dimensões 64 × 64 e o sampler deixou de ser identificado como ausente.
- A validação da interface visual em sessão interativa e o teste na versão mínima Blender 4.2 permanecem pendentes.

## Fase 5 — validação, polimento, empacotamento e release

**Status:** concluída para validação e empacotamento local; nenhum push nem release público foi feito.

Escopo e ordem definidos pelo usuário:

### Resultado final

- Os round-trips reais Gen8/Gen9 passaram para os 16 casos disponíveis de YDR, YFT cloth e YTD. As diferenças de normalização de shader e nomes/hash estão descritas acima; os arquivos não são byte-idênticos.
- Não há fixtures YDD nem YFT de veículo, portanto esses formatos não foram certificados por round-trip real. PyMateria ausente também impede confirmar a importação final do binário na cena neste ambiente.
- No Blender 5.2.2, o registro do add-on, exportação CWXML, busca de YTD, cache/reindexação e associação de DDS a sampler foram exercitados. O add-on habilitado e desabilitado foi testado; a troca de versão do loader exige reinício.
- Testes: 14 testes CWBridge e 7 testes do loader passaram. Build Release e publish self-contained win-x64 do bridge passaram.
- Os ZIPs de RESollumz e RESollumz Loader passaram por `blender --command extension validate` e foram habilitados em extrações temporárias limpas no Blender 5.2.2.
- `RECodeWalker/` foi fixado como submódulo. `cwbridge\publish.ps1` recria o executável e inclui `CodeWalker.Notice.txt` e `SharpDX.LICENSE.txt` no pacote instalável.
- Pacote principal `dist/resollumz-0.1.0.zip`: 35.974.145 bytes; SHA-256 `80E7FDE6D6E1A2AB323A965E1C4CE1AA1CB69EDA1D238C5357A8D1788A2839C6`.
- Pacote Loader `dist/resollumz_loader-0.1.0.zip`: 13.188 bytes; SHA-256 `946F598B6D51B8509EA72838CCC0E885A94377B09536C2A305AF340AFE74CF06`.
- Os pacotes ficam em `dist/`, ignorado pelo Git. Remover os ZIPs existentes antes de reconstruí-los: o comando do Blender pode acrescentar o novo conteúdo ao arquivo anterior.
- Documentação, empacotamento, 41 commits locais por arquivo (com `.gitmodules` e gitlink juntos) e a tag anotada local `v0.1.0` (“RESollumz Prototype”) estão preparados. Nenhum push ou release público foi feito; a publicação aguarda confirmação explícita.
