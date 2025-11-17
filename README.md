# Borrador de PDF com Desfoque

Aplicativo desktop simples em Python/Tkinter para abrir um PDF, selecionar qualquer retângulo da página, borrá-lo e salvar o resultado em outro arquivo.

## Recursos principais

- Visualização da página atual do PDF com ajuste automático ao tamanho da janela.
- Seleção de retângulos com o mouse (clique, arraste e solte).
- Controle do raio de desfoque (2 a 40 px) para personalizar a intensidade.
- Navegação entre páginas e salvamento em um novo PDF.

> **Observação:** páginas editadas são rasterizadas ao salvar para garantir que o desfoque faça parte do documento final.

## Pré-requisitos

- Python 3.10 ou superior.
- Dependências listadas em `requirements.txt` (PyMuPDF, Pillow e pytest para os testes opcionais).

Instale tudo com:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Como executar (interface desktop)

```bash
source .venv/bin/activate  # se ainda não estiver ativa
python app.py
```

1. Clique em **"Abrir PDF"** e escolha o arquivo desejado.
2. Arraste o mouse sobre a área que quer borrar.
3. Ajuste o raio de desfoque, se necessário, e pressione **"Aplicar desfoque"**.
4. Repita em outras páginas usando os botões de navegação.
5. Clique em **"Salvar PDF"** quando terminar.

## Interface web com Streamlit

Também é possível rodar a aplicação no navegador, com upload de PDF e seleção de áreas diretamente na tela:

```bash
source .venv/bin/activate
python -m streamlit run streamlit_app.py
```

> Dica: se `which streamlit` apontar para fora da pasta `.venv`, prefira sempre `python -m streamlit ...` para garantir que o interpretador correto (com PyMuPDF) seja usado. Caso tenha instalado um pacote "fitz" globalmente, remova-o com `pip uninstall fitz` para evitar conflitos.

Fluxo sugerido:

1. Faça upload do PDF na barra lateral do Streamlit.
2. Use o slider para escolher a página e o controle de desfoque para definir a intensidade.
3. Desenhe um retângulo sobre a página usando o canvas interativo; clique em **"Aplicar desfoque"** para salvar a alteração.
4. Repita o processo em quantas páginas quiser.
5. Baixe o PDF resultante pelo botão **"Baixar PDF borrado"**.

## Implantação no Heroku

Pré-requisitos:

- Conta no [Heroku](https://dashboard.heroku.com/) com o Heroku CLI instalado.
- Plano que permita apps com buildpacks Python padrão.

Arquivos adicionados:

- `runtime.txt`: fixa a versão do Python usada no dyno (`python-3.11.9`).
- `Procfile`: inicia o Streamlit com `streamlit run streamlit_app.py --server.port=$PORT ...`.
- `setup.sh`: cria `~/.streamlit/config.toml` com as flags necessárias (headless, CORS off, porta dinâmica).

Passo a passo recomendado:

```bash
# 1. Login (caso ainda não tenha feito)
heroku login

# 2. Criar app (substitua NOME_DO_APP pelo identificador desejado)
heroku create NOME_DO_APP

# 3. Garantir que o remote heroku foi adicionado
git remote add heroku https://git.heroku.com/NOME_DO_APP.git

# 4. Fazer deploy
git push heroku main

# 5. (Opcional) Acompanhar logs em tempo real
heroku logs --tail --app NOME_DO_APP
```

> Dica: se quiser configurar variáveis adicionais (ex.: proteger o app com senha), use `heroku config:set VAR=valor` e leia essas variáveis dentro do `streamlit_app.py`.

## Testes

Há um teste simples para a função de processamento de imagem:

```bash
source .venv/bin/activate
pytest
```

## Resolução de problemas

- **`ModuleNotFoundError: No module named 'frontend'` ou erro ao importar `fitz`:**
	Isso acontece quando o pacote antigo `fitz` (relacionado a neuroimagem) está instalado no Python global e intercepta o import do PyMuPDF. Execute:

	```bash
	pip uninstall -y fitz
	```

	Em seguida, reative o ambiente virtual do projeto e confirme:

	```bash
	source .venv/bin/activate
	pip install -r requirements.txt
	python -c "import fitz; print(f'PyMuPDF OK: {fitz.__doc__[:20]}')"
	```

- **A aplicação usa outro Python por engano:** verifique qual `python` está em uso com `which python`. Se não estiver apontando para `.../borradorPDF/.venv/bin/python`, ative o ambiente como mostrado acima antes de rodar o app.

## Limitações e próximos passos

- Páginas com desfoque são convertidas para imagens rasterizadas; se precisar preservar texto pesquisável, seria necessário implementar redactions vetoriais.
- Suporte a múltiplas seleções simultâneas e desfazer/refazer podem ser adicionados futuramente.
