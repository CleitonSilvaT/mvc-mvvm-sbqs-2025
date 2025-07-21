import os
import pandas as pd
import requests
from datetime import datetime
from pathlib import Path

# Caminho do CSV de entrada
caminho_csv = Path('Instrumentos/Codigos/repositoriosTestadosCoverletV2.csv')
GITHUB_TOKENS = "xxx"
GRAPHQL_URL = "https://api.github.com/graphql"

# Cabeçalhos da requisição
headers = {
    "Authorization": f"Bearer {GITHUB_TOKENS}"
}

# Leitura do CSV — não converter 'N/A' em NaN
try:
    df = pd.read_csv(caminho_csv, keep_default_na=False)
except Exception as e:
    print(f"Erro ao ler o arquivo CSV: {e}")
    exit()

# Normalizar a coluna Arquitetura
df['Arquitetura'] = df['Arquitetura'].astype(str).str.strip().str.upper()

# Função para obter a idade do repositório
def obter_idade_repositorio(owner, name):
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        createdAt
      }
    }
    """
    variables = {"owner": owner, "name": name}
    response = requests.post(
        GRAPHQL_URL,
        json={'query': query, 'variables': variables},
        headers=headers
    )

    if response.status_code != 200:
        print(f"Erro na API para {owner}/{name}: {response.status_code}")
        return None

    data = response.json()
    try:
        created_at = data['data']['repository']['createdAt']
        created_date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
        idade_dias = (datetime.utcnow() - created_date).days
        idade_anos = round(idade_dias / 365.25, 2)
        return idade_anos
    except Exception as e:
        print(f"Erro ao processar {owner}/{name}: {e}")
        return None

resultados = []

# Iterar sobre os repositórios
for _, row in df.iterrows():
    nome = row['Nome']
    owner = row['Proprietário']
    mutation_score = row.get('Mutation Score', 'N/A') or 'N/A'
    arquitetura = row.get('Arquitetura', 'N/A') or 'N/A'
    
    idade = obter_idade_repositorio(owner, nome)
    
    if idade is not None:
        resultados.append({
            'Nome': nome,
            'Arquitetura': arquitetura,
            'Mutation Score': mutation_score,
            'Idade (anos)': idade
        })

# Criar DataFrame com os resultados
df_resultado = pd.DataFrame(resultados)

# Salvar no novo CSV, sem alterar 'N/A'
df_resultado.to_csv('repositoriosIdade.csv', index=False, na_rep='N/A')
print("Arquivo 'repositoriosIdade.csv' salvo com sucesso.")