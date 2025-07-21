import requests
import csv
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import json

# Carrega as variáveis de ambiente
load_dotenv()
GITHUB_TOKENS = os.getenv("GITHUB_TOKENS").split(",")  # Lista de tokens
GRAPHQL_URL = "https://api.github.com/graphql"

# Variável global para controlar o token atual
token_index = 0

def get_headers():
    """Retorna os headers com o token atual"""
    global token_index
    return {"Authorization": f"Bearer {GITHUB_TOKENS[token_index]}"}

def rotate_token():
    """Troca para o próximo token disponível"""
    global token_index
    token_index = (token_index + 1) % len(GITHUB_TOKENS)

def query_graphql(query):
    """Faz uma requisição GraphQL, tentando trocar de token caso atinja limites"""
    for _ in range(len(GITHUB_TOKENS)):  # Tenta com cada token uma vez
        response = requests.post(GRAPHQL_URL, json={"query": query}, headers=get_headers(), timeout=60)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 403:  # Erro de limite de requisições
            print("Limite de requisições atingido, trocando token...")
            rotate_token()
            time.sleep(2)  # Aguarda 2 segundos antes de tentar novamente
        else:
            print(f"Erro na consulta GraphQL: {response.status_code} - {response.text}")
            return None
    return None  # Se todos os tokens falharem

def fetch_repositories(query_string, end_cursor=None):
    """Busca repositórios com base em uma string de consulta e um cursor opcional"""
    repositories = []
    
    while True:  # Continua até que não haja mais páginas disponíveis
        query = f"""
        {{
          search(query: "{query_string}", type: REPOSITORY, first: 100, after: {f'"{end_cursor}"' if end_cursor else 'null'}) {{
            pageInfo {{
              endCursor
              hasNextPage
            }}
            nodes {{
              ... on Repository {{
                name
                owner {{
                  login
                }}
                stargazerCount
              }}
            }}
          }}
        }}
        """
        data = query_graphql(query)
        if data:
            search_results = data['data']['search']
            repositories.extend(search_results['nodes'])
            end_cursor = search_results['pageInfo']['endCursor']
            
            if not search_results['pageInfo']['hasNextPage']:  # Sai do loop se não há mais páginas
                break
        else:
            break  # Sai do loop em caso de erro

        time.sleep(2)  # Evita limite de requisições
    
    return repositories, end_cursor

def analyze_repository_files(owner, name, stars):
    """Analisa os arquivos do repositório para verificar se é .NET, tem testes e sua arquitetura"""
    default_branches = ["main", "master"]
    
    for branch in default_branches:
        url = f"https://api.github.com/repos/{owner}/{name}/git/trees/{branch}?recursive=1"
        response = requests.get(url, headers=get_headers(), timeout=60)
        if response.status_code == 200:
            break  
        time.sleep(1)  
    
    if response.status_code != 200:
        return name, owner, stars, False, False, None, None, None

    tree = response.json().get("tree", [])
    is_dotnet = any(f['path'].endswith(('.csproj', '.sln')) for f in tree)
    csproj_files = [f['path'] for f in tree if f['path'].endswith(".csproj")]

    # Verifica a versão do SDK nos arquivos .csproj
    sdk_version = None
    for csproj_path in csproj_files:
        file_url = f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/{csproj_path}"
        file_response = requests.get(file_url, headers=get_headers(), timeout=120)
        if file_response.status_code == 200:
            content = file_response.text

            # Procura pela tag <TargetFramework> ou <TargetFrameworks>
            if "<TargetFramework>" in content or "<TargetFrameworks>" in content:
                # Extrai o valor da tag <TargetFramework> ou <TargetFrameworks>
                if "<TargetFramework>" in content:
                    start = content.find("<TargetFramework>") + len("<TargetFramework>")
                    end = content.find("</TargetFramework>")
                else:
                    start = content.find("<TargetFrameworks>") + len("<TargetFrameworks>")
                    end = content.find("</TargetFrameworks>")

                if start != -1 and end != -1:
                    target_framework = content[start:end].strip()
                    if target_framework.startswith("net6.0"):
                        sdk_version = "6.0.x"  # Define a versão do SDK 
                        break  # Para após encontrar a primeira ocorrência

        time.sleep(1)  # Evitar rate limit

    # Detecta o diretório da solução
    sln_files = [f['path'] for f in tree if f['path'].endswith(".sln")]
    if len(sln_files) == 1:
        sln_directory = os.path.dirname(sln_files[0])
    else:
        return name, owner, stars, False, False, None, None, None  # Ignora repositórios com 0 ou mais de 1 .sln

    # **Análise de Arquitetura**: Verifica pacotes NuGet nos arquivos .csproj
    architecture = None
    mvc_keywords = ["Microsoft.AspNetCore.Mvc", "System.Web.Mvc"]
    mvvm_keywords = ["CommunityToolkit.Mvvm", "MvvmLight", "ReactiveUI"]

    # **Análise de Testes**: Verifica pacotes de teste e nomes de projetos/pastas
    has_tests = False
    test_keywords = ["xunit", "nunit", "mstest", "test"]

    for csproj_path in csproj_files:
        file_url = f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/{csproj_path}"
        file_response = requests.get(file_url, headers=get_headers(), timeout=120)
        if file_response.status_code == 200:
            content = file_response.text

            # Verifica arquitetura
            if any(pkg in content for pkg in mvc_keywords):
                architecture = "MVC"
            elif any(pkg in content for pkg in mvvm_keywords):
                architecture = "MVVM"

            # Verifica testes
            if any(test_keyword in csproj_path.lower() for test_keyword in test_keywords) or \
               any(test_keyword in content.lower() for test_keyword in test_keywords):
                has_tests = True

        time.sleep(1)  # Evitar rate limit

    return name, owner, stars, is_dotnet, has_tests, sdk_version, architecture, sln_directory

def save_checkpoint(current_date, end_cursor):
    """Salva o checkpoint atual em um arquivo JSON"""
    checkpoint = {
        "current_date": current_date.strftime("%Y-%m-%d"),
        "end_cursor": end_cursor
    }
    with open("checkpoint.json", "w") as file:
        json.dump(checkpoint, file)

def load_checkpoint():
    """Carrega o checkpoint de um arquivo JSON"""
    try:
        with open("checkpoint.json", "r") as file:
            checkpoint = json.load(file)
            return datetime.strptime(checkpoint["current_date"], "%Y-%m-%d"), checkpoint["end_cursor"]
    except FileNotFoundError:
        return datetime(2010, 1, 1), None  # Retorna a data inicial se o arquivo não existir

def fetch_all_repositories():
    """Busca repositórios dividindo a consulta por intervalos de tempo menores"""
    all_repositories = []
    start_date, end_cursor = load_checkpoint()  # Carrega o checkpoint
    end_date = datetime(2024, 1, 1)

    current_date = start_date
    while current_date < end_date:
        next_date = current_date + timedelta(days=30)  # Intervalo de 30 dias
        query_string = f'language:C# stars:>100 created:{current_date.strftime("%Y-%m-%d")}..{next_date.strftime("%Y-%m-%d")}'

        while True:
            repositories, end_cursor = fetch_repositories(query_string, end_cursor)
            all_repositories.extend(repositories)
            print(f"Repositórios coletados para {current_date.strftime('%Y-%m-%d')} a {next_date.strftime('%Y-%m-%d')}: {len(repositories)} (Cursor: {end_cursor})")

            if not end_cursor:
                break

            save_checkpoint(current_date, end_cursor)  # Salva o checkpoint após cada página

        current_date = next_date
        end_cursor = None  # Reseta o cursor para o próximo intervalo

    print(f"Total de repositórios coletados: {len(all_repositories)}")
    return all_repositories

def analyze_repositories():
    """Executa a análise dos repositórios e salva os resultados no CSV"""
    all_repos = fetch_all_repositories()
    filtered_repos = []
    lock = Lock()  # Bloqueio para evitar condições de corrida

    # Usando ThreadPoolExecutor para análise em paralelo
    max_workers = 24  # Limita a 32 workers
    with ThreadPoolExecutor(max_workers=max_workers) as executor:  # Ajuste o número de workers conforme necessário
        futures = []
        for repo in all_repos:
            owner, name, stars = repo['owner']['login'], repo['name'], repo['stargazerCount']
            print(f"Submetendo análise: {name}")
            futures.append(executor.submit(analyze_repository_files, owner, name, stars))

        for future in as_completed(futures):
            try:
                name, owner, stars, is_dotnet, has_tests, sdk_version, architecture, sln_directory = future.result()
                print(f"  .NET: {is_dotnet}, Testes: {has_tests}, SDK: {sdk_version}, Arquitetura: {architecture or 'Indefinido'}, SLN: {sln_directory or 'Não encontrado'}")
                
                is_sdk_8 = sdk_version and sdk_version.startswith("6.0.")

                if is_dotnet and has_tests and is_sdk_8 and architecture:
                    with lock:
                        filtered_repos.append([name, owner, stars, sdk_version, architecture, sln_directory])
            except Exception as e:
                print(f"Erro ao analisar repositório: {e}")
    
    os.makedirs("Instrumentos/Codigos", exist_ok=True)
    with open("Instrumentos/Codigos/repositorios.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Nome", "Proprietário", "Estrelas", "SDK", "Arquitetura", "Diretório SLN"])
        writer.writerows(filtered_repos)
    
    print(f"\nTotal de repositórios analisados: {len(all_repos)}")
    print(f"Total de repositórios salvos no CSV: {len(filtered_repos)}")

# Executa a análise
analyze_repositories()