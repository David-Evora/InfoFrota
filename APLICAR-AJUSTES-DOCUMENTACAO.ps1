$ErrorActionPreference = 'Stop'

function Replace-TextOnce {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Old,
        [Parameter(Mandatory=$true)][string]$New
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Warning "Arquivo não encontrado, ignorando: $Path"
        return
    }

    $fullPath = (Resolve-Path -LiteralPath $Path).Path
    $content = [System.IO.File]::ReadAllText($fullPath)
    if (-not $content.Contains($Old)) {
        Write-Host "Trecho já atualizado ou não encontrado: $Path" -ForegroundColor Yellow
        return
    }

    $content = $content.Replace($Old, $New)
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($fullPath, $content, $utf8)
    Write-Host "Atualizado: $Path" -ForegroundColor Green
}

# README principal: remove a descrição da interface antiga e consolida o único site.
Replace-TextOnce -Path 'README.md' -Old '| Dashboard | MVP frontend em HTML, CSS e JavaScript; interface web servida pela API em `/`: ao vivo (resumo, alertas e assistente) com a API ativa, demonstração estática com dados ilustrativos sem ela |' -New '| Site de apresentação | Único frontend do projeto, em `docs/site/`, com catálogo de funcionalidades, demonstrações, gráficos sintéticos e arquitetura interativa; servido pela API em `/` e publicado pelo GitHub Pages |'
Replace-TextOnce -Path 'README.md' -Old '| Site de apresentação | `docs/site/`: página estática em HTML, CSS e JavaScript, em modo claro e escuro, com explorador de funcionalidades, demonstração simulada do assistente, gráficos sobre dados sintéticos e diagrama de arquitetura; servida em `/site/` (veja `docs/site/README.md`) |' -New '| Publicação do site | O workflow do GitHub Pages publica `docs/site/` na raiz do endereço do repositório. |'

# Documentação do InfoFrota AI: atualiza a localização do frontend e seu comportamento.
Replace-TextOnce -Path 'docs/INFOFROTA_AI.md' -Old 'A interface (`docs/index.html`) é servida pela API em `/`: com a API ativa, os indicadores, a tabela de linhas, os alertas e o assistente usam dados reais do banco sintético; sem ela (GitHub Pages, arquivo aberto direto), continua uma demonstração estática com dados fictícios.' -New 'O único site do projeto fica em `docs/site/` e é servido pela API em `/`. Com a API ativa, a demonstração de IA pode consultar os endpoints na mesma origem; no GitHub Pages ou sem backend, o site permanece em modo demonstrativo com dados sintéticos.'

# A documentação de arquitetura não deve tratar o frontend antigo como parte do projeto.
Replace-TextOnce -Path 'docs/architecture-infofrota-ai.md' -Old '- Integração do dashboard estático à API.' -New '- Implantação do backend em ambiente público; o GitHub Pages hospeda somente o site estático.'

# Em hospedagem de projeto no GitHub Pages, mantém as chamadas relativas dentro de /InfoFrota/.
Replace-TextOnce -Path 'docs/site/index.html' -Old '<meta name="infofrota-api" content="../">' -New '<meta name="infofrota-api" content="./">'

Write-Host ''
Write-Host 'Ajustes textuais concluídos. Revise git diff antes de commitar.' -ForegroundColor Cyan
