import csv
import os
import stat
import subprocess
import time
import shutil

def load_repositories(csv_path):
    """Carrega todos os repositórios a partir do arquivo CSV."""
    with open(csv_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        return list(reader)  # Retorna todas as linhas do CSV
    return []

def clone_repositories(owner, nome, destino):
    """Clona o repositório para o diretório especificado."""
    if os.path.exists(destino):
        print(f"Repositório {nome} já existe em {destino}. Pulando clonagem.")
        return True, None  

    url = f"https://github.com/{owner}/{nome}.git"
    comand = ["git", "clone", url, destino]

    try:
        process = subprocess.run(comand, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, None
    except subprocess.CalledProcessError as e:
        return False, f"Erro ao clonar {nome}: {e.stderr}"

def execute_stryker(diretorio):
    """Executa o Stryker.NET no diretório especificado e retorna as métricas."""
    try:
        comand = ["dotnet", "stryker", "--verbosity", "info"]
        process = subprocess.Popen(comand, cwd=diretorio, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

        output = []
        for line in process.stdout:
            print(line, end='')  # Exibe a saída do Stryker em tempo real
            output.append(line.strip())  # Salva a saída para análise

        process.wait()  # Aguarda a finalização completa do processo
        saida = "\n".join(output)
        erro = process.stderr.read().strip() if process.stderr else ""
        
        if process.returncode != 0:
            return None, f"Erro ao executar Stryker: {saida + erro}"
        
        # Extrair métricas da saída do Stryker
        killed = survived = timeout = time_elapsed = mutation_score = "N/A"
        total_mutants = mutants_compile_error = mutants_no_coverage = mutants_ignored = mutants_tested = "N/A"
        
        for line in saida.split('\n'):
            if "Killed" in line and ":" in line:
                killed = line.split(":")[-1].strip()
            elif "Survived" in line and ":" in line:
                survived = line.split(":")[-1].strip()
            elif "Timeout" in line and ":" in line:
                timeout = line.split(":")[-1].strip()
            elif "Time Elapsed" in line:
                time_elapsed = line.split()[-1].strip()
            elif "The final mutation score" in line:
                mutation_score = line.split()[-2].strip()
            elif "mutants created" in line:
                total_mutants = line.split("INF]")[-1].strip().split()[0]
            elif "mutants got status CompileError" in line:
                mutants_compile_error = line.split("INF]")[-1].strip().split()[0]
            elif "mutants got status NoCoverage" in line:
                mutants_no_coverage = line.split("INF]")[-1].strip().split()[0]
            elif "mutants got status Ignored" in line:
                mutants_ignored = line.split("INF]")[-1].strip().split()[0]
            elif "total mutants are skipped" in line:
                mutants_tested = line.split("INF]")[-1].strip().split()[0]
        
        return {
            "Killed": killed,
            "Survived": survived,
            "Timeout": timeout,
            "Time Elapsed": time_elapsed,
            "Mutation Score": mutation_score,
            "Total Mutants": total_mutants,
            "Mutants Compile Error": mutants_compile_error,
            "Mutants No Coverage": mutants_no_coverage,
            "Mutants Ignored": mutants_ignored,
            "Mutants Tested": mutants_tested
        }, None
    except Exception as e:
        return None, f"Erro inesperado ao executar Stryker: {str(e)}"
    
def build_project(diretorio):
    """Executa o comando `dotnet build` no diretório especificado."""
    try:
        comand = ["dotnet", "build"]
        process = subprocess.run(comand, cwd=diretorio, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, None
    except subprocess.CalledProcessError as e:
        return False, f"Erro ao compilar o projeto: {e.stderr}"

def save_resultes(csv_path, resultes):
    """Salva os resultados no arquivo CSV (modo append para não sobrescrever)."""
    existe = os.path.exists(csv_path)
    fieldnames = [
        "Nome", "Proprietário", "Estrelas", "SDK", "Arquitetura", "Diretório SLN",
        "Killed", "Survived", "Timeout", "Time Elapsed", "Mutation Score",
        "Total Mutants", "Mutants Compile Error", "Mutants No Coverage", "Mutants Ignored", "Mutants Tested", "Erro"
    ]
    
    with open(csv_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not existe:
            writer.writeheader()  # Escreve o cabeçalho apenas se o arquivo não existir
        writer.writerows(resultes)

def delete_repositorie(diretorio):
    """Remove o diretório do repositório clonado para liberar espaço."""
    def on_error(func, path, exc_info):
        # Altera as permissões do arquivo/diretório 
        os.chmod(path, stat.S_IWRITE)  # Torna o arquivo gravável
        func(path)  # Tenta excluir novamente

    try:
        shutil.rmtree(diretorio, onerror=on_error)
        print(f"Repositório deletado: {diretorio}")
    except Exception as e:
        print(f"Erro ao deletar {diretorio}: {e}")

def load_last_processed_repo(csv_path):
    """Carrega o último repositório processado a partir do arquivo CSV."""
    if not os.path.exists(csv_path):
        return None  # Se o arquivo não existir

    # Aumenta o limite do tamanho do campo para 10 MB
    csv.field_size_limit(10 * 1024 * 1024)  

    with open(csv_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        if not rows:
            return None  # Se o arquivo estiver vazio
        return rows[-1]  # Retorna a última linha do CSV
    
def find_start_index(repositorios, last_repo):
    """Encontra o índice do último repositório processado na lista de repositórios."""
    if not last_repo:
        return 0  # Se não houver último repositório, começa do início

    last_repo_nome = last_repo["Nome"]
    for i, repo in enumerate(repositorios):
        if repo["Nome"] == last_repo_nome:
            return i + 1  # Retorna o índice do próximo repositório
    return 0  # Se o último repositório não for encontrado, começa do início

def main():
    csv_input = "Instrumentos/Codigos/repositorios.csv"
    csv_output = "Instrumentos/Codigos/repositoriosClonados.csv"
    base_dir = "Instrumentos/Codigos/repositoriosClonados"
    
    # Carrega todos os repositórios do CSV de entrada
    repositorios = load_repositories(csv_input)
    if not repositorios:
        print("Nenhum repositório encontrado no CSV.")
        return

    # Carrega o último repositório processado
    last_repo = load_last_processed_repo(csv_output)
    start_index = find_start_index(repositorios, last_repo)

    print(f"Continuando a partir do repositório {start_index + 1} de {len(repositorios)}...")

    results = []
    
    # Processa apenas os repositórios a partir do último processado
    for repo in repositorios[start_index:]:
        nome = repo["Nome"]
        owner = repo["Proprietário"]
        diretorio_sln = repo.get("Diretório SLN", "")
        caminho_repo = os.path.join(base_dir, nome)

        # Clonar repositório
        print(f"Clonando repositório {nome}...")
        sucess, erro_clone = clone_repositories(owner, nome, caminho_repo)
        if not sucess:
            repo["Erro"] = erro_clone
            results.append(repo)
            save_resultes(csv_output, [repo])  # Salva o erro 
            continue

        # Caminho completo do diretório da solução
        caminho_sln = os.path.join(caminho_repo, diretorio_sln)
        
        if not os.path.exists(caminho_sln):
            repo["Erro"] = "Diretório da solução não encontrado"
            results.append(repo)
            save_resultes(csv_output, [repo])  # Salva o erro 
            delete_repositorie(caminho_repo)  # Deleta se não encontrar a solução
            continue

        # Compilar o projeto
        print(f"Compilando o projeto em {caminho_sln}...")
        sucess_build, erro_build = build_project(caminho_sln)
        if not sucess_build:
            repo["Erro"] = erro_build
            results.append(repo)
            save_resultes(csv_output, [repo])  # Salva o erro 
            delete_repositorie(caminho_repo)  # Deleta o repositório após o erro
            continue

        # Executar Stryker
        print(f"Executando Stryker em {caminho_sln}...")
        metricas, erro = execute_stryker(caminho_sln)
        
        if metricas:
            repo.update(metricas)  # Atualiza o dicionário com as métricas do Stryker
        if erro:
            repo["Erro"] = erro
        
        results.append(repo)

        # Salvar os resultados após processar cada repositório
        save_resultes(csv_output, [repo])

        # Apaga o repositório após execução
        print(f"Deletando repositório {caminho_repo}...")
        delete_repositorie(caminho_repo)
        time.sleep(2)

    print("Execução concluída! Resultados salvos em", csv_output)

if __name__ == "__main__":
    main()