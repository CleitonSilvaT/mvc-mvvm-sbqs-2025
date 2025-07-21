import csv
import os
import subprocess
import re
import shutil
from pathlib import Path

# Configurações - caminhos absolutos
base_dir = Path('C:/Users/')
csv_input_path = base_dir / 'repositoriosTestados.csv'
csv_output_path = base_dir / 'repositoriosTestadosCoverlet.csv'
clone_dir = base_dir / 'repositorios_clonados'

# Versões do .NET a serem verificadas
DOTNET_VERSIONS = ['net9.0', 'net8.0', 'net6.0']

def print_header(message):
    print("\n" + "="*80)
    print(f" {message.center(78)} ")
    print("="*80)

def clean_repo_directory(repo_path):
    """Remove o diretório de um repositório específico se ele existir"""
    try:
        if repo_path.exists():
            print(f"Removendo diretório existente: {repo_path}")
            shutil.rmtree(repo_path)
        return True
    except Exception as e:
        print(f"ERRO ao limpar diretório do repositório: {e}")
        return False

def clone_repo(repo_url, repo_name):
    print_header(f"CLONANDO REPOSITÓRIO: {repo_url}")
    try:
        repo_path = clone_dir / repo_name
        
        # Limpa apenas o repositório específico
        if not clean_repo_directory(repo_path):
            return False
            
        # Garante que o diretório pai existe
        clone_dir.mkdir(parents=True, exist_ok=True)
        
        # Clona o repositório
        result = subprocess.run(
            ['git', 'clone', repo_url, str(repo_path)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("Clone realizado com sucesso!")
            return True
        else:
            print(f"Erro ao clonar repositório:\n{result.stderr}")
            return False
            
    except Exception as e:
        print(f"Erro inesperado ao clonar: {e}")
        return False

def find_dll_in_output(output):
    """Tenta encontrar o caminho do .dll na saída do dotnet test"""
    patterns = [
        r'Execução de teste para (.+\.Tests?\.dll)',
        r'Test execution for (.+\.Tests?\.dll)',
        r'Test results for: (.+\.Tests?\.dll)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            dll_path = Path(match.group(1))
            if dll_path.exists():
                return dll_path
    return None

def find_dll_in_directory(repo_path, dll_name=None):
    """Procura o arquivo .dll manualmente nas pastas bin"""
    search_paths = []
    
    if dll_name:
        for version in DOTNET_VERSIONS:
            search_paths.extend([
                repo_path / 'bin' / 'Debug' / version / dll_name,
                repo_path / 'bin' / 'Release' / version / dll_name
            ])
    else:
        for version in DOTNET_VERSIONS:
            search_paths.extend([
                repo_path / 'bin' / 'Debug' / version,
                repo_path / 'bin' / 'Release' / version
            ])
    
    for path in search_paths:
        if path.exists():
            return path
    
    for path in (repo_path / 'bin').rglob('*.Tests.dll'):
        if path.exists():
            return path
    
    return None

def run_dotnet_test(test_dir):
    print_header(f"EXECUTANDO DOTNET TEST EM: {test_dir}")
    try:
        if not test_dir.exists():
            print(f"ERRO: Diretório {test_dir} não encontrado!")
            return None
            
        has_sln = any(f.name.endswith('.sln') for f in test_dir.glob('*.sln'))
        has_csproj = any(f.name.endswith('.csproj') for f in test_dir.glob('*.csproj'))
        
        if not has_sln and not has_csproj:
            print("ERRO: Nenhum arquivo .sln ou .csproj encontrado!")
            return None
            
        original_dir = Path.cwd()
        os.chdir(test_dir)
        
        result = subprocess.run(
            ['dotnet', 'test'],
            capture_output=True,
            text=True
        )

        print("Saída do dotnet test:")
        print(result.stdout)

        dll_path = find_dll_in_output(result.stdout)
        if dll_path:
            print(f"Arquivo de testes encontrado (saída): {dll_path}")
            os.chdir(original_dir)
            return dll_path
        
        match = re.search(r'(\S+\.Tests?\.dll)', result.stdout)
        if match:
            dll_name = match.group(1)
            print(f"Procurando arquivo: {dll_name}")
            dll_path = find_dll_in_directory(test_dir, dll_name)
            if dll_path:
                print(f"Arquivo de testes encontrado (busca): {dll_path}")
                os.chdir(original_dir)
                return dll_path
        
        print("Procurando qualquer arquivo .Tests.dll...")
        dll_path = find_dll_in_directory(test_dir)
        if dll_path:
            print(f"Arquivo de testes encontrado (genérico): {dll_path}")
            os.chdir(original_dir)
            return dll_path
        
        print("Nenhum arquivo de testes .dll encontrado.")
        os.chdir(original_dir)
        return None
        
    except Exception as e:
        print(f"Erro ao executar dotnet test: {e}")
        os.chdir(original_dir)
        return None

def run_coverlet(dll_path):
    print_header(f"EXECUTANDO COVERLET EM: {dll_path}")
    try:
        if not dll_path.exists():
            print(f"ERRO: Arquivo {dll_path} não encontrado!")
            return None, None
        
        # Encontra o diretório do projeto (subindo até encontrar .csproj)
        project_dir = dll_path.parent
        while project_dir != project_dir.parent:  # Evita loop infinito
            if any(f.suffix == '.csproj' for f in project_dir.iterdir()):
                break
            project_dir = project_dir.parent
        
        original_dir = Path.cwd()
        os.chdir(project_dir)
        
        result = subprocess.run(
            ['coverlet', str(dll_path), '--target', 'dotnet', '--targetargs', f'test "{project_dir}" --no-build'],
            capture_output=True,
            text=True
        )
        
        os.chdir(original_dir)
        
        print("Saída do Coverlet:")
        print(result.stdout)
        
        match = re.search(r'\|\s*Total\s*\|\s*([\d\.]+)%\s*\|\s*[\d\.]+%\s*\|\s*([\d\.]+)%\s*\|', result.stdout)
        if match:
            line_cov = float(match.group(1))
            method_cov = float(match.group(2))
            print(f"Cobertura encontrada - Linhas: {line_cov}%, Métodos: {method_cov}%")
            return line_cov, method_cov
        
        print("ERRO: Padrão de cobertura não encontrado na saída")
        return None, None
        
    except Exception as e:
        print(f"Erro no Coverlet: {e}")
        return None, None

def process_repository(row):
    repo_url = f"https://github.com/{row['Proprietário']}/{row['Nome']}.git"
    repo_name = row['Nome']
    
    # Inicializa os valores
    row.update({
        "Cobertura Linha (%)": "N/A",
        "Cobertura Método (%)": "N/A",
        "Status": "Não processado",
        "Diretório Testado": "N/A"
    })
    
    if not clone_repo(repo_url, repo_name):
        row["Status"] = "Erro ao clonar"
        return row
    
    repo_path = clone_dir / repo_name
    sln_dir = row.get('Diretório SLN', '').strip()
    test_dir = repo_path / sln_dir if sln_dir else repo_path
    row["Diretório Testado"] = str(test_dir.relative_to(base_dir))  # Mostra caminho relativo
    
    dll_path = run_dotnet_test(test_dir)
    
    if not dll_path:
        row.update({
            "Cobertura Linha (%)": "Erro",
            "Cobertura Método (%)": "Erro",
            "Status": "Nenhum teste encontrado"
        })
        return row
    
    line_cov, method_cov = run_coverlet(dll_path)
    
    if line_cov is not None and method_cov is not None:
        row.update({
            "Cobertura Linha (%)": f"{line_cov:.2f}%",
            "Cobertura Método (%)": f"{method_cov:.2f}%",
            "Status": "Sucesso"
        })
    else:
        row.update({
            "Cobertura Linha (%)": "Erro",
            "Cobertura Método (%)": "Erro",
            "Status": "Erro no Coverlet"
        })
    
    return row

def main():
    # Muda para o diretório base onde os arquivos estão
    os.chdir(base_dir)
    print(f"Diretório atual de trabalho: {Path.cwd()}")
    
    # Verifica se o arquivo de entrada existe
    if not csv_input_path.exists():
        print(f"ERRO: Arquivo {csv_input_path} não encontrado!")
        return
    
    # Lê todos os repositórios do CSV
    with open(csv_input_path, 'r', encoding='utf-8') as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    
    if not rows:
        print("Nenhum repositório encontrado no CSV.")
        return
    
    processed_rows = []
    
    for i, row in enumerate(rows, 1):
        print_header(f"PROCESSANDO REPOSITÓRIO {i}/{len(rows)}: {row['Nome']}")
        processed_row = process_repository(row.copy())
        processed_rows.append(processed_row)
        
        with open(csv_output_path, 'w', newline='', encoding='utf-8') as csv_file:
            fieldnames = list(rows[0].keys()) + ["Cobertura Linha (%)", "Cobertura Método (%)", "Status", "Diretório Testado"]
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(processed_rows)
    
    print_header("TESTE CONCLUÍDO")
    print(f"Resultados salvos em: {csv_output_path}")

if __name__ == "__main__":
    main()